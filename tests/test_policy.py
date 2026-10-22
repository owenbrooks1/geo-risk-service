"""Policy tests: the decision rule end to end on hand-written known answers."""

import ast
import csv
import shutil
from pathlib import Path

import pytest

from geo_risk_service.assessment.ingest import load_ip_locations, load_logins
from geo_risk_service.assessment.policy import assess, speed_rule
from geo_risk_service.contracts.config import load_policy
from geo_risk_service.contracts.models import (
    Decision,
    IpLocation,
    Login,
    Policy,
    Reason,
)

SRC = Path(__file__).resolve().parents[1] / "src/geo_risk_service/assessment"
POLICY = Policy(version="test", max_speed_kmh=1000)


def read_csv(path):
    """Read a CSV file as a list of dicts, one per row."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def assess_dir(folder, policy):
    """Load inputs from a folder and assess them, as the service stage will."""
    logins = load_logins(folder / "logins.csv").logins
    return assess(logins, load_ip_locations(folder / "ip_locations.csv"), policy)


@pytest.fixture(scope="module")
def results():
    """Assessments for the hand-written fixture, by login ID."""
    examples = Path(__file__).resolve().parents[1] / "examples"
    policy = load_policy(Path(__file__).resolve().parents[1] / "config/policy.yaml")
    return {a.login_id: a for a in assess_dir(examples / "assess", policy)}


EXPECTED = read_csv(
    Path(__file__).resolve().parents[1] / "examples/assess/expected.csv"
)


@pytest.mark.parametrize(
    "row", EXPECTED, ids=[f"{r['ac']}-{r['login_id']}" for r in EXPECTED]
)
def test_ac02_to_ac08_fixture_known_answers(results, row):
    """Each fixture login gets its expected decision, reason and speed range."""
    got = results[row["login_id"]]
    assert (got.decision, got.reason) == (
        Decision(row["decision"]),
        Reason(row["reason"]),
    )
    for field in ("min_speed_kmh", "max_speed_kmh"):
        expected = row[field]
        actual = getattr(got, field)
        if expected:
            assert actual == pytest.approx(float(expected), abs=0.1), field
        else:
            assert actual is None, field


def test_every_assessment_records_the_policy_version(results):
    assert {a.policy_version for a in results.values()} == {"v1"}


def test_ac08_exactly_at_threshold_clears():
    """1,000 km, zero radii, 1 hour: maximum speed is exactly 1,000, so clear."""
    assert speed_rule(1000, 0, 0, 1, 1000).decision is Decision.CLEAR


def test_ac08_minimum_exactly_at_threshold_does_not_flag():
    """1,010 km with 5 km radii over 1 hour: range 1,000 to 1,020. The minimum
    is not above 1,000 and the maximum is, so the evidence cannot decide."""
    result = speed_rule(1010, 5, 5, 1, 1000)
    assert (result.decision, result.reason) == (Decision.ABSTAIN, Reason.INCONCLUSIVE)
    assert (result.min_speed_kmh, result.max_speed_kmh) == (1000, 1020)


def _login(login_id, time, ip):
    return Login(login_id=login_id, customer_id="C-1", event_time=time, ip=ip)


def _place(ip, lat, lon, kind="residential"):
    return IpLocation(
        ip=ip,
        lat=lat,
        lon=lon,
        accuracy_km=25,
        connection_type=kind,
        valid_from="2026-01-01T00:00:00Z",
    )


PLACES = [
    _place("203.0.113.10", -33.8688, 151.2093),
    _place("203.0.113.20", 51.5074, -0.1278),
    _place("198.51.100.50", 50.1109, 8.6821, "hosting"),
]


def test_qa1_flagged_login_still_becomes_the_baseline():
    """Sydney 09:00, London 09:40 (flag), Sydney 10:30: compared with London."""
    logins = [
        _login("A", "2026-05-01T09:00:00Z", "203.0.113.10"),
        _login("B", "2026-05-01T09:40:00Z", "203.0.113.20"),
        _login("C", "2026-05-01T10:30:00Z", "203.0.113.10"),
    ]
    out = {a.login_id: a for a in assess(logins, PLACES, POLICY)}
    assert out["B"].decision is Decision.FLAG
    assert (out["C"].decision, out["C"].baseline_login_id) == (Decision.FLAG, "B")


def test_qa2_first_login_from_vpn_reports_unreliable_ip():
    out = assess([_login("A", "2026-05-01T09:00:00Z", "198.51.100.50")], PLACES, POLICY)
    assert (out[0].decision, out[0].reason) == (Decision.ABSTAIN, Reason.UNRELIABLE_IP)


def test_q5g_ac08_logins_sorted_by_time_then_login_id():
    """Input out of order, with a same-time pair listed higher ID first.
    Sydney "A" and London "B" at 09:00: A (lower ID) is first, so A has no
    baseline and B flags against it. "C" at 12:00 is listed first but is
    compared with B, the latest earlier login."""
    logins = [
        _login("C", "2026-05-01T12:00:00Z", "203.0.113.20"),
        _login("B", "2026-05-01T09:00:00Z", "203.0.113.20"),
        _login("A", "2026-05-01T09:00:00Z", "203.0.113.10"),
    ]
    out = {a.login_id: a for a in assess(logins, PLACES, POLICY)}
    assert out["A"].reason is Reason.NO_BASELINE
    assert (out["B"].decision, out["B"].baseline_login_id) == (Decision.FLAG, "A")
    assert (out["C"].decision, out["C"].baseline_login_id) == (Decision.CLEAR, "B")


def test_ac10_no_logins_gives_no_assessments():
    assert assess([], PLACES, POLICY) == []


def test_ac12_inv5_decisions_identical_with_or_without_truth(tmp_path, examples):
    """Truth sitting next to the inputs changes nothing. Assessment is never
    given a truth path; this shows its presence has no effect."""
    with_truth = tmp_path / "with"
    without = tmp_path / "without"
    for folder in (with_truth, without):
        shutil.copytree(examples / "assess", folder)
    (with_truth / "truth.csv").write_text(
        "login_id,suspicious,scenario\nL-0202,false,normal\n"
    )
    assert assess_dir(with_truth, POLICY) == assess_dir(without, POLICY)


def _docstrings(tree):
    """The docstring nodes in a module, which may mention truth in prose."""
    nodes = [tree, *ast.walk(tree)]
    return {
        id(n.body[0].value)
        for n in nodes
        if isinstance(n, ast.Module | ast.ClassDef | ast.FunctionDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }


@pytest.mark.parametrize("module", ["ingest", "geo", "enrichment", "policy"])
def test_inv5_assessment_code_never_touches_truth(module):
    """No assessment module uses the Truth model in any form, imports the
    service (where evaluation lives), or has any text naming truth outside
    its docstrings."""
    tree = ast.parse((SRC / f"{module}.py").read_text())
    docstrings = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith("geo_risk_service.service"), (
                module
            )
            assert "Truth" not in [a.name for a in node.names], module
        if isinstance(node, ast.Import):
            assert not any(
                a.name.startswith("geo_risk_service.service") for a in node.names
            ), module
        if isinstance(node, ast.Name):
            assert node.id != "Truth", module
        if isinstance(node, ast.Attribute):
            assert node.attr != "Truth", module
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                assert "truth" not in node.value.lower(), module

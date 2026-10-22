"""API tests: health and single assessment lookup (AC-15, AC-16, INV-4, INV-5)."""

import ast
import os
import stat
from pathlib import Path

import duckdb
import pytest
from fastapi.testclient import TestClient

from geo_risk_service.contracts.config import load_policy
from geo_risk_service.generator.synthetic import generate, write_dataset
from geo_risk_service.service.api import create_app
from geo_risk_service.service.run import process

API_SOURCE = Path(__file__).resolve().parents[1] / "src/geo_risk_service/service/api.py"


@pytest.fixture
def policy(config_dir):
    """Policy v1 from the real config."""
    return load_policy(config_dir / "policy.yaml")


@pytest.fixture
def fixture_client(tmp_path, examples, policy):
    """An API over the hand-written fixture, processed into a temporary database."""
    db = tmp_path / "results.duckdb"
    process(examples / "assess", db, policy, seed=0)
    return TestClient(create_app(db))


def test_ac15_not_ready_without_results(tmp_path):
    missing = tmp_path / "results.duckdb"
    response = TestClient(create_app(missing)).get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready" and str(missing) in body["reason"]


def test_ac15_ready_after_a_run_with_matching_counts(tmp_path, policy):
    write_dataset(generate(seed=42, customers=10, days=5), tmp_path)
    summary = process(tmp_path, tmp_path / "results.duckdb", policy, seed=42)
    response = TestClient(create_app(tmp_path / "results.duckdb")).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["policy_version"], body["seed"]) == ("ready", "v1", 42)
    assert body["loaded"] == summary.loaded
    assert body["decisions_by_outcome"] == summary.decisions_by_outcome


def test_ac16_known_login_returns_decision_evidence_and_version(fixture_client):
    response = fixture_client.get("/assessments/L-0202")
    assert response.status_code == 200
    body = response.json()
    assert (body["decision"], body["reason"]) == ("flag", "impossible_travel")
    assert body["min_speed_kmh"] == pytest.approx(16943.9, abs=0.1)
    assert body["max_speed_kmh"] == pytest.approx(17043.9, abs=0.1)
    assert (body["baseline_login_id"], body["policy_version"]) == ("L-0201", "v1")


def test_inv4_times_returned_as_utc(fixture_client):
    """Item 3: every time the API returns is written the same way, ending in Z."""
    body = fixture_client.get("/assessments/L-0202").json()
    assert body["event_time"] == "2026-05-01T10:00:00Z"
    run_at = fixture_client.get("/health").json()["run_at"]
    assert run_at.endswith("Z") and "+" not in run_at


def test_ac16_every_stored_field_round_trips(fixture_client, examples, policy):
    """Reviewer: the bulk load must not swap columns. The API returns exactly
    what assess produced, field by field."""
    from geo_risk_service.assessment.ingest import load_ip_locations, load_logins
    from geo_risk_service.assessment.policy import assess

    logins = load_logins(examples / "assess/logins.csv").logins
    places = load_ip_locations(examples / "assess/ip_locations.csv")
    expected = {a.login_id: a for a in assess(logins, places, policy)}["L-0202"]
    body = fixture_client.get("/assessments/L-0202").json()
    assert body == expected.model_dump(mode="json")


def test_item2_database_without_results_tables_is_not_ready(tmp_path):
    """An empty or damaged database file gives 503 with a reason, not a 500."""
    db = tmp_path / "results.duckdb"
    duckdb.connect(str(db)).close()
    client = TestClient(create_app(db))
    for path in ("/health", "/assessments/L-0202"):
        response = client.get(path)
        assert response.status_code == 503, path
        assert "not readable" in response.json()["reason"]


def test_api_opens_the_database_read_only(tmp_path, examples, policy):
    """Reviewer: with the file read-only on disk, the API still works. A
    read-write connection would fail here."""
    db = tmp_path / "results.duckdb"
    process(examples / "assess", db, policy, seed=0)
    os.chmod(db, stat.S_IRUSR)
    try:
        client = TestClient(create_app(db))
        assert client.get("/health").status_code == 200
        assert client.get("/assessments/L-0202").status_code == 200
    finally:
        os.chmod(db, stat.S_IRUSR | stat.S_IWUSR)


def test_ac16_unknown_login_is_404(fixture_client):
    assert fixture_client.get("/assessments/NOPE").status_code == 404


def test_ac16_lookup_before_any_run_is_not_ready(tmp_path):
    client = TestClient(create_app(tmp_path / "results.duckdb"))
    assert client.get("/assessments/L-0202").status_code == 503


def test_inv5_api_never_touches_truth():
    """No name, attribute or text in the API mentions truth (docstrings aside),
    and it imports neither evaluation nor the run module."""
    tree = ast.parse(API_SOURCE.read_text())
    docstrings = {
        id(n.body[0].value)
        for n in [tree, *ast.walk(tree)]
        if isinstance(n, ast.Module | ast.FunctionDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            assert "truth" not in name.lower()
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) not in docstrings:
                assert "truth" not in node.value.lower()
        if isinstance(node, ast.ImportFrom | ast.Import):
            names = [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            names += [a.name for a in node.names]
            for name in names:
                assert not name.endswith(("evaluation", "service.run")), name
                assert name not in ("evaluation", "run"), name

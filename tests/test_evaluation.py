"""Evaluation tests: metrics against hidden truth (AC-13, Q-S2, Q-S3)."""

import csv

import pytest

from geo_risk_service.assessment.ingest import InputDataError
from geo_risk_service.contracts.models import Scenario, Truth
from geo_risk_service.service.evaluation import evaluate, load_truth


def read_csv(path):
    """Read a CSV file as a list of dicts, one per row."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture
def fixture_report(examples):
    """The AC-13 fixture: 2 flagged (1 suspicious), 3 cleared, 1 abstained."""
    decisions = read_csv(examples / "evaluation/assessments.csv")
    return evaluate(decisions, load_truth(examples / "evaluation/truth.csv"))


def test_ac13_counts(fixture_report):
    assert fixture_report.decisions == {"flag": 2, "clear": 3, "abstain": 1}


def test_ac13_precision_and_recall_count_an_abstain_as_a_miss(fixture_report):
    assert fixture_report.precision == 0.5
    assert fixture_report.recall == 0.5
    assert fixture_report.recall_decided_only == 1.0


def test_ac13_false_clears_and_abstains(fixture_report):
    assert fixture_report.false_clears == 0
    assert fixture_report.abstain_rate == pytest.approx(1 / 6)
    assert fixture_report.suspicious_abstained == 1


def truth(login_id, suspicious):
    """A truth row for a small hand-built case."""
    scenario = Scenario.IMPOSSIBLE_JUMP if suspicious else Scenario.NORMAL
    return Truth(login_id=login_id, suspicious=suspicious, scenario=scenario)


def test_qs3_nothing_flagged_means_precision_not_defined():
    report = evaluate([{"login_id": "A", "decision": "clear"}], [truth("A", False)])
    assert report.precision is None
    assert report.recall is None  # no suspicious logins either


def test_qs2_unassessed_logins_reported_separately(examples):
    decisions = read_csv(examples / "evaluation/assessments.csv")
    rows = load_truth(examples / "evaluation/truth.csv") + [truth("E-99", True)]
    report = evaluate(decisions, rows)
    assert (report.not_assessed, report.not_assessed_suspicious) == (1, 1)
    assert (report.precision, report.recall) == (0.5, 0.5)


def test_inv5_missing_truth_file_is_a_clear_error(tmp_path):
    with pytest.raises(InputDataError, match="truth.csv"):
        load_truth(tmp_path / "truth.csv")


def test_item4_decision_without_truth_counted_not_scored_as_genuine(examples):
    """A decision with no truth row must not hide a false clear."""
    decisions = read_csv(examples / "evaluation/assessments.csv") + [
        {"login_id": "E-77", "decision": "clear"}
    ]
    report = evaluate(decisions, load_truth(examples / "evaluation/truth.csv"))
    assert report.no_truth == 1
    assert (report.precision, report.recall, report.false_clears) == (0.5, 0.5, 0)


def test_ac13_breakdown_by_scenario(fixture_report):
    """Each planted scenario against the decisions it got (owner request)."""
    assert fixture_report.by_scenario == {
        "genuine_travel": {"clear": 1, "flag": 1},
        "impossible_jump": {"abstain": 1, "flag": 1},
        "normal": {"clear": 2},
    }

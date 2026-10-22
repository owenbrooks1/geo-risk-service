"""Score decisions against hidden truth. The only module that reads truth (INV-5).

Recall counts every suspicious login, so an abstain on one is a miss: abstaining
cannot raise recall (AC-13). Precision and false clears can look better when the
policy abstains, so read them with suspicious_abstained, reported alongside.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from geo_risk_service.assessment.ingest import InputDataError
from geo_risk_service.contracts.models import Truth


@dataclass
class EvaluationReport:
    """How the decisions compare with truth. None means "not defined" (Q-S3)."""

    assessed: int
    decisions: dict[str, int]
    abstain_by_reason: dict[str, int]
    precision: float | None
    recall: float | None
    recall_decided_only: float | None
    false_clears: int
    abstain_rate: float | None
    suspicious_abstained: int
    not_assessed: int
    not_assessed_suspicious: int
    no_truth: int
    by_scenario: dict[str, dict[str, int]]


def load_truth(path: Path) -> list[Truth]:
    """Read truth.csv, or stop with a clear error if it is missing or broken."""
    path = Path(path)
    if not path.is_file():
        raise InputDataError(f"input file not found: {path}")
    with open(path, newline="") as f:
        try:
            return [Truth.model_validate(row) for row in csv.DictReader(f)]
        except ValidationError as error:
            raise InputDataError(f"{path}: {error.errors()[0]['msg']}") from None


def _ratio(part: int, whole: int) -> float | None:
    """part / whole, or None when there is nothing to divide by (Q-S3)."""
    return part / whole if whole else None


def evaluate(decisions: list[dict], truth: list[Truth]) -> EvaluationReport:
    """Compare decisions (rows with login_id, decision and optional reason)
    with truth. Logins with truth but no decision are counted as not assessed
    (Q-S2), and decisions with no truth row as no truth, so data problems are
    visible but do not distort the policy's numbers."""
    suspicious = {t.login_id: t.suspicious for t in truth}
    scenario = {t.login_id: str(t.scenario) for t in truth}
    by_scenario: dict[str, dict[str, int]] = {}
    counts = {"flag": 0, "clear": 0, "abstain": 0}
    by_reason: dict[str, int] = {}
    hits = false_clears = suspicious_abstained = no_truth = 0
    for row in decisions:
        decision = str(row["decision"])
        counts[decision] += 1
        if row["login_id"] not in suspicious:
            # Truth and results have drifted apart. Count it, so it is visible,
            # rather than scoring the login as genuine.
            no_truth += 1
            continue
        bad = suspicious[row["login_id"]]
        # Which planted scenario got which decision, to show each behaved as designed.
        cell = by_scenario.setdefault(scenario[row["login_id"]], {})
        cell[decision] = cell.get(decision, 0) + 1
        if decision == "abstain":
            reason = str(row.get("reason") or "unknown")
            by_reason[reason] = by_reason.get(reason, 0) + 1
            suspicious_abstained += bad
        elif decision == "flag":
            hits += bad
        else:
            false_clears += bad
    assessed_ids = {row["login_id"] for row in decisions}
    unassessed = [t for t in truth if t.login_id not in assessed_ids]
    total_suspicious = sum(t.suspicious for t in truth if t.login_id in assessed_ids)
    return EvaluationReport(
        assessed=len(decisions),
        decisions=counts,
        abstain_by_reason=by_reason,
        precision=_ratio(hits, counts["flag"]),
        recall=_ratio(hits, total_suspicious),
        recall_decided_only=_ratio(hits, hits + false_clears),
        false_clears=false_clears,
        abstain_rate=_ratio(counts["abstain"], len(decisions)),
        suspicious_abstained=suspicious_abstained,
        not_assessed=len(unassessed),
        not_assessed_suspicious=sum(t.suspicious for t in unassessed),
        no_truth=no_truth,
        by_scenario={
            name: dict(sorted(cells.items()))
            for name, cells in sorted(by_scenario.items())
        },
    )

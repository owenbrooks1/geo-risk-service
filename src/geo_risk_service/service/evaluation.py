"""Score decisions against hidden truth. The only module that reads truth (INV-5).

Abstaining can never make the numbers look better: recall counts every
suspicious login, so an abstain on one is a miss (AC-13).
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
    with truth. Logins with truth but no decision are counted separately as
    not assessed (Q-S2), so data problems are visible but do not distort the
    policy's numbers."""
    suspicious = {t.login_id: t.suspicious for t in truth}
    counts = {"flag": 0, "clear": 0, "abstain": 0}
    by_reason: dict[str, int] = {}
    hits = false_clears = suspicious_abstained = 0
    for row in decisions:
        decision = str(row["decision"])
        counts[decision] += 1
        bad = suspicious.get(row["login_id"], False)
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
    )

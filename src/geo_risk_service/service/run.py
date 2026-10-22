"""Run the workflow: generate, process, evaluate. Entry point for `make demo`.

Processing never receives a truth path (INV-5); only evaluate_run reads truth.
Every run logs one JSON summary line, and a stopped run logs its cause (AC-17).
"""

import csv
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from geo_risk_service.assessment.ingest import (
    load_ip_locations,
    load_logins,
)
from geo_risk_service.assessment.policy import assess
from geo_risk_service.contracts.config import load_policy, load_settings
from geo_risk_service.contracts.models import Assessment, Policy
from geo_risk_service.contracts.schema import create_tables, to_db_time
from geo_risk_service.generator.synthetic import generate, write_dataset
from geo_risk_service.service.evaluation import EvaluationReport, evaluate, load_truth

log = logging.getLogger("geo_risk_service")


def _log(event: str, **fields) -> None:
    """Write one JSON log line, so monitoring can parse it (Q-S4)."""
    log.info(json.dumps({"event": event, **fields}, default=str))


@dataclass
class RunSummary:
    """What one processing run loaded, rejected and decided."""

    seed: int
    policy_version: str
    loaded: int
    rejected_by_reason: dict[str, int]
    decisions_by_outcome: dict[str, int]


def _count(values) -> dict[str, int]:
    """Count occurrences of each value, in first-seen order."""
    counts: dict[str, int] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return counts


def process(data_dir: Path, db_path: Path, policy: Policy, seed: int) -> RunSummary:
    """Load inputs, assess every login and store the results in DuckDB.

    Results from any earlier run are replaced. Any failure is logged with its
    cause and stops the run; an input fault is an InputDataError (AC-11).
    """
    data_dir, db_path = Path(data_dir), Path(db_path)
    try:
        loaded = load_logins(data_dir / "logins.csv")
        ip_locations = load_ip_locations(data_dir / "ip_locations.csv")
        assessments = assess(loaded.logins, ip_locations, policy)
        summary = RunSummary(
            seed=seed,
            policy_version=policy.version,
            loaded=len(loaded.logins),
            rejected_by_reason=_count(r.reason for r in loaded.rejected),
            decisions_by_outcome=_count(a.decision for a in assessments),
        )
        _store(db_path, assessments, summary, rejected=len(loaded.rejected))
    except Exception as error:
        # Any failure, expected or not, is logged before it stops the run.
        _log("run_stopped", error=type(error).__name__, cause=str(error))
        raise
    _log("run_complete", **asdict(summary))
    return summary


def _csv_values(assessment: Assessment, columns: list[str]) -> list:
    """One assessment as CSV values: UTC time without offset, empty for None."""
    values = []
    for column in columns:
        value = getattr(assessment, column)
        if column == "event_time":
            value = to_db_time(value).isoformat(sep=" ")
        values.append("" if value is None else str(value))
    return values


def _store(db_path: Path, assessments: list[Assessment], summary, rejected: int):
    """Replace the results tables with this run's assessments and summary.

    All in one transaction: if anything fails, the previous run's results stay
    in place and keep being served, rather than a half-written database.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(Assessment.model_fields)
    with duckdb.connect(str(db_path)) as con:
        con.begin()
        try:
            _replace_results(con, db_path, columns, assessments, summary, rejected)
        except Exception:
            con.rollback()
            raise
        con.commit()


def _replace_results(con, db_path, columns, assessments, summary, rejected):
    """The statements of one store, run inside the caller's transaction."""
    con.execute("DROP TABLE IF EXISTS assessments")
    con.execute("DROP TABLE IF EXISTS run_summary")
    create_tables(con)
    if assessments:
        # One bulk load from a temporary CSV: inserting row by row is far
        # too slow in DuckDB for a few thousand rows.
        staging = db_path.with_suffix(".staging.csv")
        with open(staging, "w", newline="") as f:
            writer = csv.writer(f, lineterminator="\n")
            writer.writerow(columns)
            for a in assessments:
                writer.writerow(_csv_values(a, columns))
        try:
            # COPY cannot take the path as a parameter, so quote it safely.
            quoted = str(staging).replace("'", "''")
            names = ", ".join(columns)
            con.execute(f"COPY assessments ({names}) FROM '{quoted}' (HEADER)")
        finally:
            staging.unlink()
    con.execute(
        "INSERT INTO run_summary VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            to_db_time(datetime.now(UTC)),
            summary.seed,
            summary.policy_version,
            summary.loaded,
            rejected,
            json.dumps(summary.rejected_by_reason),
            json.dumps(summary.decisions_by_outcome),
        ],
    )


def evaluate_run(data_dir: Path, db_path: Path) -> EvaluationReport:
    """Score the stored decisions against truth.csv and save evaluation.json."""
    data_dir = Path(data_dir)
    try:
        truth = load_truth(data_dir / "truth.csv")
        with duckdb.connect(str(db_path), read_only=True) as con:
            rows = con.execute(
                "SELECT login_id, decision, reason FROM assessments ORDER BY login_id"
            ).fetchall()
        decisions = [{"login_id": i, "decision": d, "reason": r} for i, d, r in rows]
        report = evaluate(decisions, truth)
        (data_dir / "evaluation.json").write_text(json.dumps(asdict(report), indent=2))
    except Exception as error:
        _log("run_stopped", error=type(error).__name__, cause=str(error))
        raise
    return report


def run_demo(settings_path: Path, policy_path: Path) -> EvaluationReport:
    """Generate with the configured seed, process, then evaluate."""
    try:
        settings = load_settings(settings_path)
        policy = load_policy(policy_path)
        dataset = generate(settings.seed, settings.customers, settings.days)
        write_dataset(dataset, settings.data_dir)
    except Exception as error:
        _log("run_stopped", error=type(error).__name__, cause=str(error))
        raise
    process(settings.data_dir, settings.db_path, policy, settings.seed)
    return evaluate_run(settings.data_dir, settings.db_path)


def format_report(report: EvaluationReport) -> str:
    """The evaluation report as plain text for the terminal."""

    def show(value):
        return "not defined" if value is None else f"{value:.3f}"

    return "\n".join(
        [
            "Evaluation against hidden truth",
            f"  assessed logins:      {report.assessed}",
            f"  decisions:            {report.decisions}",
            f"  abstains by reason:   {report.abstain_by_reason}",
            f"  precision:            {show(report.precision)}",
            f"  recall:               {show(report.recall)}  (abstain = miss)",
            f"  recall, decided only: {show(report.recall_decided_only)}  (secondary)",
            f"  false clears:         {report.false_clears}",
            f"  abstain rate:         {show(report.abstain_rate)}",
            f"  suspicious abstained: {report.suspicious_abstained}",
            f"  not assessed:         {report.not_assessed}"
            f" (suspicious: {report.not_assessed_suspicious})",
            f"  no truth label:       {report.no_truth}",
            "",
            "By planted scenario (decisions each scenario received)",
            *[f"  {name:<16}{cells}" for name, cells in report.by_scenario.items()],
        ]
    )


def main() -> int:
    """`make demo`: run with config/ and print the report. Exit 1 if stopped."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    try:
        report = run_demo(Path("config/settings.yaml"), Path("config/policy.yaml"))
    except Exception:  # already logged as run_stopped with its cause
        return 1
    print(format_report(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())

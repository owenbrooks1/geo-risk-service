"""Run tests: end-to-end demo, logging and truth isolation (AC-14, AC-17, INV-5)."""

import ast
import inspect
import json
import logging
import re
import textwrap
from datetime import UTC, datetime, timedelta

import pytest

from geo_risk_service.assessment.ingest import InputDataError
from geo_risk_service.contracts.config import ConfigError, load_policy
from geo_risk_service.generator.synthetic import generate, write_dataset
from geo_risk_service.service import run
from geo_risk_service.service.run import evaluate_run, process, run_demo

# A fixed run time, for tests that control the clock.
T0 = datetime(2026, 10, 22, 10, 0, 0, tzinfo=UTC)


def write_settings(tmp_path, customers=100, days=30):
    """Settings pointing every path into a temporary folder."""
    data = tmp_path / "data"
    path = tmp_path / "settings.yaml"
    path.write_text(
        f"seed: 42\ncustomers: {customers}\ndays: {days}\n"
        f"data_dir: {data}\ndb_path: {data / 'results.duckdb'}\n"
    )
    return path


def events(caplog, name):
    """The JSON log entries with the given event name."""
    entries = [json.loads(r.getMessage()) for r in caplog.records]
    return [e for e in entries if e.get("event") == name]


@pytest.fixture(scope="module")
def demo(tmp_path_factory, config_dir_module):
    """A full seed 42 demo run (100 customers, 30 days) in a temporary folder."""
    tmp = tmp_path_factory.mktemp("demo")
    report = run_demo(write_settings(tmp), config_dir_module / "policy.yaml")
    return tmp, report


@pytest.fixture(scope="module")
def config_dir_module(request):
    """The real config folder, for module-scoped fixtures."""
    return request.config.rootpath / "config"


def test_ac14_seed_42_has_no_false_clears(demo):
    _, report = demo
    assert report.false_clears == 0


def test_ac18_demo_writes_results_and_evaluation(demo):
    tmp, _ = demo
    assert (tmp / "data/results.duckdb").is_file()
    assert json.loads((tmp / "data/evaluation.json").read_text())["false_clears"] == 0


def test_ac17_one_summary_line_per_run(tmp_path, config_dir, caplog):
    caplog.set_level(logging.INFO, logger="geo_risk_service")
    run_demo(write_settings(tmp_path, customers=10, days=5), config_dir / "policy.yaml")
    [summary] = events(caplog, "run_complete")
    assert (summary["seed"], summary["policy_version"]) == (42, "v1")
    assert summary["loaded"] > 0 and summary["rejected_by_reason"] == {}
    assert set(summary["decisions_by_outcome"]) <= {"flag", "clear", "abstain"}
    assert sum(summary["decisions_by_outcome"].values()) == summary["loaded"]


def test_ac17_ac11_missing_ip_table_logs_cause_and_stops(tmp_path, config_dir, caplog):
    caplog.set_level(logging.INFO, logger="geo_risk_service")
    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    (tmp_path / "ip_locations.csv").unlink()
    policy = load_policy(config_dir / "policy.yaml")
    with pytest.raises(InputDataError):
        process(tmp_path, tmp_path / "results.duckdb", policy, seed=42)
    [stopped] = events(caplog, "run_stopped")
    assert stopped["error"] == "InputDataError"
    assert "ip_locations.csv" in stopped["cause"]


def test_ac17_ac11_bad_policy_logs_cause_and_stops(tmp_path, caplog):
    caplog.set_level(logging.INFO, logger="geo_risk_service")
    bad = tmp_path / "policy.yaml"
    bad.write_text("version: v1\nmax_speed_kmh: -5\n")
    with pytest.raises(ConfigError):
        run_demo(write_settings(tmp_path, customers=5, days=5), bad)
    [stopped] = events(caplog, "run_stopped")
    assert stopped["error"] == "ConfigError" and "max_speed_kmh" in stopped["cause"]


def test_inv5_process_works_without_truth(tmp_path, config_dir):
    """Processing never needs truth; only evaluation does, and says so clearly."""
    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    (tmp_path / "truth.csv").unlink()
    policy = load_policy(config_dir / "policy.yaml")
    summary = process(tmp_path, tmp_path / "results.duckdb", policy, seed=42)
    assert summary.loaded > 0
    with pytest.raises(InputDataError, match="truth.csv"):
        evaluate_run(tmp_path, tmp_path / "results.duckdb")


def test_inv5_process_code_never_mentions_truth():
    """The process function (not its docstring) has no reference to truth."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(run.process)))
    body = tree.body[0].body[1:]  # skip the docstring
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            assert "truth" not in name.lower()
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "truth" not in node.value.lower()


def test_item1_failed_store_keeps_previous_results(tmp_path, config_dir, monkeypatch):
    """A write that fails halfway rolls back: the earlier run is still there."""
    import duckdb

    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    db = tmp_path / "results.duckdb"
    policy = load_policy(config_dir / "policy.yaml")
    monkeypatch.setattr(run, "_now", lambda: T0)
    first = process(tmp_path, db, policy, seed=42)

    def broken(*args):
        raise RuntimeError("disk full")

    # A later clock, so the second run gets past the run order check.
    monkeypatch.setattr(run, "_now", lambda: T0 + timedelta(seconds=1))
    monkeypatch.setattr(run, "_csv_values", broken)
    with pytest.raises(RuntimeError):
        process(tmp_path, db, policy, seed=7)
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM assessments").fetchone()[0] == (
            first.loaded
        )
        assert con.execute("SELECT seed FROM run_summary").fetchall() == [(42,)]


def test_item5_unexpected_failure_is_logged_once(
    tmp_path, config_dir, caplog, monkeypatch
):
    caplog.set_level(logging.INFO, logger="geo_risk_service")

    def broken(*args):
        raise RuntimeError("generator bug")

    monkeypatch.setattr(run, "generate", broken)
    with pytest.raises(RuntimeError):
        run_demo(
            write_settings(tmp_path, customers=5, days=5), config_dir / "policy.yaml"
        )
    [stopped] = events(caplog, "run_stopped")
    assert (stopped["error"], stopped["cause"]) == ("RuntimeError", "generator bug")


def test_item5_missing_truth_at_evaluation_is_logged(tmp_path, config_dir, caplog):
    caplog.set_level(logging.INFO, logger="geo_risk_service")
    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    process(
        tmp_path,
        tmp_path / "results.duckdb",
        load_policy(config_dir / "policy.yaml"),
        42,
    )
    (tmp_path / "truth.csv").unlink()
    with pytest.raises(InputDataError):
        evaluate_run(tmp_path, tmp_path / "results.duckdb")
    [stopped] = events(caplog, "run_stopped")
    assert "truth.csv" in stopped["cause"]


def test_staging_path_with_a_quote_is_safe(tmp_path, config_dir):
    """The bulk-load path is quoted safely inside the SQL text."""
    folder = tmp_path / "it's here"
    write_dataset(generate(seed=42, customers=5, days=5), folder)
    summary = process(
        folder, folder / "results.duckdb", load_policy(config_dir / "policy.yaml"), 42
    )
    assert summary.loaded > 0


def test_ac17_item6_evaluation_names_the_run_it_scored(demo):
    """evaluation.json carries the seed, policy version and run_at of the run."""
    import duckdb

    tmp, _ = demo
    stored = json.loads((tmp / "data/evaluation.json").read_text())["run"]
    with duckdb.connect(str(tmp / "data/results.duckdb"), read_only=True) as con:
        [(run_at,)] = con.execute("SELECT run_at FROM run_summary").fetchall()
    assert stored == {
        "seed": 42,
        "policy_version": "v1",
        "run_at": run_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    assert run_at.microsecond == 0


def test_ac17_item7_run_at_matches_in_log_report_and_health(
    tmp_path, config_dir, caplog
):
    """One run_at string links the log line, evaluation.json and /health."""
    from fastapi.testclient import TestClient

    from geo_risk_service.service.api import create_app

    caplog.set_level(logging.INFO, logger="geo_risk_service")
    run_demo(write_settings(tmp_path, customers=5, days=5), config_dir / "policy.yaml")
    [summary] = events(caplog, "run_complete")
    report = json.loads((tmp_path / "data/evaluation.json").read_text())
    health = TestClient(create_app(tmp_path / "data/results.duckdb")).get("/health")
    assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", summary["run_at"])
    assert summary["run_at"] == report["run"]["run_at"] == health.json()["run_at"]


def test_ac17_item9_each_successful_run_adds_a_summary_row(
    tmp_path, config_dir, monkeypatch
):
    """run_summary keeps one row per successful run, as an audit history."""
    import duckdb

    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    db = tmp_path / "results.duckdb"
    policy = load_policy(config_dir / "policy.yaml")
    monkeypatch.setattr(run, "_now", lambda: T0)
    process(tmp_path, db, policy, seed=42)
    monkeypatch.setattr(run, "_now", lambda: T0 + timedelta(seconds=1))
    process(tmp_path, db, policy, seed=42)
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute("SELECT count(*) FROM run_summary").fetchone()[0] == 2


def test_ac17_item6_evaluation_without_a_run_stops_clearly(tmp_path):
    """Evaluating a database with no completed run names the problem."""
    import duckdb

    from geo_risk_service.contracts.schema import create_tables

    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    db = tmp_path / "results.duckdb"
    with duckdb.connect(str(db)) as con:
        create_tables(con)
    with pytest.raises(InputDataError, match="no completed run"):
        evaluate_run(tmp_path, db)


def test_ac17_item6_evaluation_names_the_newest_of_several_runs(tmp_path, config_dir):
    """An older run stored first must not be the one evaluation.json names."""
    import duckdb

    from geo_risk_service.contracts.schema import create_tables

    db = tmp_path / "results.duckdb"
    with duckdb.connect(str(db)) as con:
        create_tables(con)
        con.execute(
            "INSERT INTO run_summary VALUES "
            "('2000-01-01 00:00:00', 99, 'v0', 0, 0, '{}', '{}')"
        )
    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    summary = process(tmp_path, db, load_policy(config_dir / "policy.yaml"), 42)
    evaluate_run(tmp_path, db)
    stored = json.loads((tmp_path / "evaluation.json").read_text())["run"]
    assert stored == {"seed": 42, "policy_version": "v1", "run_at": summary.run_at}


@pytest.mark.parametrize("later_by", [timedelta(0), timedelta(hours=-1)])
def test_ac17_review1_run_not_later_than_newest_is_refused(
    tmp_path, config_dir, caplog, monkeypatch, later_by
):
    """Same second or a clock gone backwards: refused, logged, previous run kept.

    This keeps run_at unique and makes the newest run_at the last stored run.
    """
    import duckdb

    caplog.set_level(logging.INFO, logger="geo_risk_service")
    write_dataset(generate(seed=42, customers=5, days=5), tmp_path)
    db = tmp_path / "results.duckdb"
    policy = load_policy(config_dir / "policy.yaml")
    monkeypatch.setattr(run, "_now", lambda: T0)
    first = process(tmp_path, db, policy, seed=42)
    monkeypatch.setattr(run, "_now", lambda: T0 + later_by)
    with pytest.raises(run.RunOrderError):
        process(tmp_path, db, policy, seed=7)
    [stopped] = events(caplog, "run_stopped")
    assert stopped["error"] == "RunOrderError"
    assert "2026-10-22T10:00:00Z" in stopped["cause"]
    with duckdb.connect(str(db), read_only=True) as con:
        assert con.execute("SELECT seed FROM run_summary").fetchall() == [(42,)]
        assert con.execute("SELECT count(*) FROM assessments").fetchone()[0] == (
            first.loaded
        )

"""Run tests: end-to-end demo, logging and truth isolation (AC-14, AC-17, INV-5)."""

import ast
import inspect
import json
import logging
import textwrap

import pytest

from geo_risk_service.assessment.ingest import InputDataError
from geo_risk_service.contracts.config import ConfigError, load_policy
from geo_risk_service.generator.synthetic import generate, write_dataset
from geo_risk_service.service import run
from geo_risk_service.service.run import evaluate_run, process, run_demo


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
    first = process(tmp_path, db, policy, seed=42)

    def broken(*args):
        raise RuntimeError("disk full")

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

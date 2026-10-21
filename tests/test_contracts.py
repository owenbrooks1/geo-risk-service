"""Contract tests: shapes, config and fixtures shared by every component."""

import csv
import ipaddress
from datetime import UTC, datetime

import duckdb
import pytest
from pydantic import ValidationError

from geo_risk_service.config import ConfigError, load_policy, load_settings
from geo_risk_service.models import (
    Assessment,
    Decision,
    IpLocation,
    Login,
    Reason,
    RejectReason,
    Truth,
)
from geo_risk_service.schema import create_tables, from_db_time, to_db_time

DOC_RANGES = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
]


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text)
    return path


# AC-11: config loads, or the run stops with a clear error naming the problem.


def test_ac11_policy_v1_loads(config_dir):
    policy = load_policy(config_dir / "policy.yaml")
    assert policy.version == "v1"
    assert policy.max_speed_kmh == 1000.0


def test_ac11_missing_policy_file_stops(tmp_path):
    with pytest.raises(ConfigError, match="missing.yaml"):
        load_policy(tmp_path / "missing.yaml")


def test_ac11_negative_threshold_stops(tmp_path):
    with pytest.raises(ConfigError, match="max_speed_kmh"):
        load_policy(write(tmp_path, "version: v1\nmax_speed_kmh: -5\n"))


def test_ac11_missing_policy_version_stops(tmp_path):
    with pytest.raises(ConfigError, match="version"):
        load_policy(write(tmp_path, "max_speed_kmh: 1000\n"))


def test_ac11_settings_load(config_dir):
    settings = load_settings(config_dir / "settings.yaml")
    assert (settings.seed, settings.customers, settings.days) == (42, 100, 30)


def test_ac11_zero_customers_stops(tmp_path):
    with pytest.raises(ConfigError, match="customers"):
        load_settings(
            write(
                tmp_path,
                "seed: 42\ncustomers: 0\ndays: 30\ndata_dir: d\ndb_path: d/r.duckdb\n",
            )
        )


# AC-09 (model part) and INV-4: a login row is valid only with a usable time and IP.


def login(**overrides):
    row = {
        "login_id": "L-1",
        "customer_id": "C-1",
        "event_time": "2026-05-01T10:00:00Z",
        "ip": "203.0.113.10",
    }
    return Login(**{**row, **overrides})


def test_ac09_naive_time_rejected():
    with pytest.raises(ValidationError):
        login(event_time="2026-05-01T10:00:00")


def test_ac09_invalid_ip_rejected():
    with pytest.raises(ValidationError):
        login(ip="999.1.1.1")


def test_ac09_missing_ip_rejected():
    with pytest.raises(ValidationError):
        login(ip="")


def test_inv4_offset_converted_to_utc():
    assert login(event_time="2026-05-01T10:00:00+10:00").event_time == datetime(
        2026, 5, 1, 0, 0, tzinfo=UTC
    )


# INV-6 contract: validity windows are well formed; blank valid_to is open-ended.


def ip_location(**overrides):
    row = {
        "ip": "203.0.113.10",
        "lat": -33.8688,
        "lon": 151.2093,
        "accuracy_km": 25,
        "connection_type": "residential",
        "valid_from": "2026-01-01T00:00:00Z",
        "valid_to": "",
    }
    return IpLocation(**{**row, **overrides})


def test_inv6_blank_valid_to_is_open_ended():
    assert ip_location().valid_to is None


def test_inv6_valid_to_must_follow_valid_from():
    with pytest.raises(ValidationError):
        ip_location(valid_to="2026-01-01T00:00:00Z")


def test_ip_location_rejects_impossible_coordinates():
    with pytest.raises(ValidationError):
        ip_location(lat=91)
    with pytest.raises(ValidationError):
        ip_location(accuracy_km=-1)


# Results schema matches the Assessment model, so stored results lose nothing.


def test_assessments_table_matches_model():
    con = duckdb.connect()
    create_tables(con)
    columns = [row[0] for row in con.execute("DESCRIBE assessments").fetchall()]
    assert columns == list(Assessment.model_fields)


def test_inv4_stored_time_round_trips_as_utc():
    """10:00+10:00 is stored and read back as 00:00 UTC, whatever the local zone."""
    con = duckdb.connect()
    con.execute("SET TimeZone = 'Australia/Sydney'")
    create_tables(con)
    sent = datetime.fromisoformat("2026-05-01T10:00:00+10:00")
    con.execute(
        "INSERT INTO run_summary VALUES (?, 42, 'v1', 0, 0, '{}', '{}')",
        [to_db_time(sent)],
    )
    stored = con.execute("SELECT run_at FROM run_summary").fetchone()[0]
    assert from_db_time(stored) == datetime(2026, 5, 1, 0, 0, tzinfo=UTC)


# Fixture integrity: the known answers are well formed and cover AC-02 to AC-08.


def test_fixture_rows_parse(examples):
    for row in read_csv(examples / "assess/logins.csv"):
        Login(**row)
    for row in read_csv(examples / "assess/ip_locations.csv"):
        IpLocation(**row)
    for row in read_csv(examples / "evaluation/truth.csv"):
        Truth(**row)


def test_expected_answers_cover_ac02_to_ac08(examples):
    expected = read_csv(examples / "assess/expected.csv")
    assert {r["ac"] for r in expected} >= {f"AC-0{n}" for n in range(2, 9)}
    for r in expected:
        Decision(r["decision"])
        Reason(r["reason"])
    logins = {r["login_id"] for r in read_csv(examples / "assess/logins.csv")}
    assert logins == {r["login_id"] for r in expected}


def test_ac09_fixture_has_one_rejection_per_reason(examples):
    reasons = [
        r["reason"] for r in read_csv(examples / "bad_rows/expected_rejections.csv")
    ]
    assert sorted(reasons) == sorted(
        ["missing_value", "invalid_ip", "missing_timezone", "duplicate_login_id"]
    )
    for reason in reasons:
        RejectReason(reason)


def test_inv1_fixture_ips_are_documentation_addresses(examples):
    paths = [
        "assess/logins.csv",
        "assess/ip_locations.csv",
        "ip_overlap/ip_locations.csv",
    ]
    for path in paths:
        for row in read_csv(examples / path):
            ip = ipaddress.ip_address(row["ip"])
            assert any(ip in net for net in DOC_RANGES), (path, row["ip"])

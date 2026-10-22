"""Ingest tests: bad rows rejected and counted, bad reference data stops the run."""

from datetime import UTC, datetime

import pytest

from geo_risk_service.assessment.ingest import (
    InputDataError,
    Rejection,
    load_ip_locations,
    load_logins,
)
from geo_risk_service.contracts.models import RejectReason

IP_HEADER = "ip,lat,lon,accuracy_km,connection_type,valid_from,valid_to\n"


def test_ac09_bad_rows_rejected_one_per_reason(examples):
    result = load_logins(examples / "bad_rows/logins.csv")
    assert result.rejected == [
        Rejection(3, "B-02", RejectReason.MISSING_VALUE),
        Rejection(4, "B-03", RejectReason.INVALID_IP),
        Rejection(5, "B-04", RejectReason.MISSING_TIMEZONE),
        Rejection(6, "B-01", RejectReason.DUPLICATE_LOGIN_ID),
    ]
    assert [x.login_id for x in result.logins] == ["B-01", "B-06"]


def test_ac09_inv4_kept_offset_time_is_stored_as_utc(examples):
    b06 = load_logins(examples / "bad_rows/logins.csv").logins[1]
    assert b06.event_time == datetime(2026, 4, 30, 23, 50, tzinfo=UTC)


def test_ac09_unparseable_time_rejected_as_invalid_value(tmp_path):
    path = tmp_path / "logins.csv"
    path.write_text(
        "login_id,customer_id,event_time,ip\nX-1,C-1,yesterday,203.0.113.10\n"
    )
    result = load_logins(path)
    assert result.rejected == [Rejection(2, "X-1", RejectReason.INVALID_VALUE)]


def test_ac10_empty_logins_file_gives_nothing_and_no_error(tmp_path):
    path = tmp_path / "logins.csv"
    path.write_text("login_id,customer_id,event_time,ip\n")
    result = load_logins(path)
    assert result.logins == [] and result.rejected == []


def test_ac11_missing_logins_file_stops_the_run(tmp_path):
    with pytest.raises(InputDataError, match="logins.csv"):
        load_logins(tmp_path / "logins.csv")


@pytest.mark.parametrize("text", ["", "id,who,when,where\n"])
def test_ac11_missing_or_wrong_logins_header_stops_the_run(tmp_path, text):
    """No header, or the wrong columns, means we never got the logins."""
    path = tmp_path / "logins.csv"
    path.write_text(text)
    with pytest.raises(InputDataError, match="expected columns"):
        load_logins(path)


def test_ac09_rejected_row_does_not_make_a_later_row_a_duplicate(tmp_path):
    """Decision B: the first valid row with an ID is kept."""
    path = tmp_path / "logins.csv"
    path.write_text(
        "login_id,customer_id,event_time,ip\n"
        "X-1,C-1,2026-05-01T09:00:00Z,\n"
        "X-1,C-1,2026-05-01T10:00:00Z,203.0.113.10\n"
    )
    result = load_logins(path)
    assert result.rejected == [Rejection(2, "X-1", RejectReason.MISSING_VALUE)]
    assert [x.login_id for x in result.logins] == ["X-1"]


def test_ac11_open_ended_mapping_followed_by_another_stops_the_run(tmp_path):
    path = tmp_path / "ip_locations.csv"
    path.write_text(
        IP_HEADER
        + "203.0.113.10,-33.8688,151.2093,25,residential,2026-01-01T00:00:00Z,\n"
        + "203.0.113.10,51.5074,-0.1278,25,residential,2026-05-01T00:00:00Z,\n"
    )
    with pytest.raises(InputDataError, match="203.0.113.10"):
        load_ip_locations(path)


def test_ac11_missing_ip_table_stops_the_run(tmp_path):
    with pytest.raises(InputDataError, match="ip_locations.csv"):
        load_ip_locations(tmp_path / "ip_locations.csv")


def test_ac11_empty_ip_table_stops_the_run(tmp_path):
    path = tmp_path / "ip_locations.csv"
    path.write_text(IP_HEADER)
    with pytest.raises(InputDataError, match="no rows"):
        load_ip_locations(path)


def test_ac11_invalid_ip_table_row_stops_the_run(tmp_path):
    path = tmp_path / "ip_locations.csv"
    path.write_text(
        IP_HEADER + "203.0.113.10,91,0,25,residential,2026-01-01T00:00:00Z,\n"
    )
    with pytest.raises(InputDataError, match="line 2"):
        load_ip_locations(path)


def test_ac11_overlapping_mappings_stop_the_run(examples):
    with pytest.raises(InputDataError, match="203.0.113.10"):
        load_ip_locations(examples / "ip_overlap/ip_locations.csv")


def test_reassigned_ip_is_not_an_overlap(examples):
    """192.0.2.50 moves from Sydney to London at 12:00: back to back, no overlap."""
    rows = load_ip_locations(examples / "assess/ip_locations.csv")
    assert sum(1 for r in rows if str(r.ip) == "192.0.2.50") == 2

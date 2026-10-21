"""DuckDB tables for results. Inputs and truth stay in CSV files (INV-5).

Times are stored as plain TIMESTAMP values holding UTC (INV-4). Convert with
to_db_time and from_db_time at the boundary, so the database's local time
zone setting never affects stored or returned times.
"""

from datetime import UTC, datetime

import duckdb

ASSESSMENTS = """
CREATE TABLE IF NOT EXISTS assessments (
    login_id VARCHAR PRIMARY KEY,
    customer_id VARCHAR NOT NULL,
    event_time TIMESTAMP NOT NULL,
    decision VARCHAR NOT NULL,
    reason VARCHAR NOT NULL,
    policy_version VARCHAR NOT NULL,
    baseline_login_id VARCHAR,
    lat DOUBLE,
    lon DOUBLE,
    accuracy_km DOUBLE,
    baseline_lat DOUBLE,
    baseline_lon DOUBLE,
    baseline_accuracy_km DOUBLE,
    centre_km DOUBLE,
    min_km DOUBLE,
    max_km DOUBLE,
    gap_hours DOUBLE,
    min_speed_kmh DOUBLE,
    max_speed_kmh DOUBLE
)
"""

RUN_SUMMARY = """
CREATE TABLE IF NOT EXISTS run_summary (
    run_at TIMESTAMP NOT NULL,
    seed INTEGER NOT NULL,
    policy_version VARCHAR NOT NULL,
    loaded INTEGER NOT NULL,
    rejected INTEGER NOT NULL,
    rejected_by_reason JSON NOT NULL,
    decisions_by_outcome JSON NOT NULL
)
"""


def to_db_time(value: datetime) -> datetime:
    """Aware time to the naive UTC value stored in the database."""
    return value.astimezone(UTC).replace(tzinfo=None)


def from_db_time(value: datetime) -> datetime:
    """Stored naive UTC value back to an aware UTC time."""
    return value.replace(tzinfo=UTC)


def create_tables(con: duckdb.DuckDBPyConnection) -> None:
    """Create the results tables if they do not exist yet."""
    con.execute(ASSESSMENTS)
    con.execute(RUN_SUMMARY)

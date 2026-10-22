"""Load the input files safely.

Two different failure rules (agreed in intent):
- a bad login row is rejected with a reason and counted, and the rest carry on
  (AC-09);
- missing or broken reference data stops the run, because a broken setup must
  not look like normal output full of abstains (AC-11).
"""

import csv
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from geo_risk_service.contracts.models import IpLocation, Login, RejectReason


class InputDataError(Exception):
    """An input file is missing, empty or broken. The run must stop."""


@dataclass(frozen=True)
class Rejection:
    """One rejected login row: its line in the file, its ID and why."""

    line: int
    login_id: str
    reason: RejectReason


@dataclass
class LoadResult:
    """Logins kept, and the rows rejected."""

    logins: list[Login]
    rejected: list[Rejection]


LOGIN_COLUMNS = ["login_id", "customer_id", "event_time", "ip"]
IP_COLUMNS = [
    "ip", "lat", "lon", "accuracy_km", "connection_type", "valid_from", "valid_to"
]  # fmt: skip


def _read_rows(path: Path, columns: list[str]) -> list[tuple[int, dict]]:
    """Read a CSV file as (line number, row) pairs. Line 1 is the header.

    A missing file, or a missing or wrong header, means we never got the data,
    which is a fault, not an empty batch.
    """
    path = Path(path)
    if not path.is_file():
        raise InputDataError(f"input file not found: {path}")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None or sorted(reader.fieldnames) != sorted(columns):
            raise InputDataError(
                f"{path}: expected columns {', '.join(columns)}, "
                f"got {', '.join(reader.fieldnames or ['nothing'])}"
            )
        return list(enumerate(reader, start=2))


def _reject_reason(error: ValidationError) -> RejectReason:
    """Turn a validation error into one reason code for the report."""
    first = error.errors()[0]
    field = first["loc"][0] if first["loc"] else None
    if first["type"] == "missing" or first.get("input") in ("", None):
        return RejectReason.MISSING_VALUE
    if field == "ip":
        return RejectReason.INVALID_IP
    if first["type"] == "timezone_aware":
        return RejectReason.MISSING_TIMEZONE
    return RejectReason.INVALID_VALUE


def load_logins(path: Path) -> LoadResult:
    """Load logins, rejecting bad rows.

    For a duplicate ID the first valid row wins. A row that was rejected never
    entered, so it does not make a later valid row with that ID a duplicate.
    """
    kept, rejected, seen = [], [], set()
    for line, row in _read_rows(path, LOGIN_COLUMNS):
        login_id = row.get("login_id") or ""
        try:
            login = Login.model_validate(row)
        except ValidationError as error:
            rejected.append(Rejection(line, login_id, _reject_reason(error)))
            continue
        if login.login_id in seen:
            rejected.append(Rejection(line, login_id, RejectReason.DUPLICATE_LOGIN_ID))
            continue
        seen.add(login.login_id)
        kept.append(login)
    return LoadResult(logins=kept, rejected=rejected)


def load_ip_locations(path: Path) -> list[IpLocation]:
    """Load the IP table, or stop the run if it is missing, empty or broken."""
    rows = _read_rows(path, IP_COLUMNS)
    if not rows:
        raise InputDataError(f"{path}: no rows")
    table = []
    for line, row in rows:
        try:
            table.append(IpLocation.model_validate(row))
        except ValidationError as error:
            problems = "; ".join(e["msg"] for e in error.errors())
            raise InputDataError(f"{path} line {line}: {problems}") from None
    _check_no_overlaps(path, table)
    return table


def _check_no_overlaps(path: Path, table: list[IpLocation]) -> None:
    """Stop if one IP has two mappings in force at the same moment.

    Picking one would be a silent guess about where the customer was.
    Back-to-back mappings (one ends exactly when the next starts) are fine.
    """
    by_ip: dict[str, list[IpLocation]] = {}
    for row in table:
        by_ip.setdefault(str(row.ip), []).append(row)
    for ip, rows in by_ip.items():
        rows.sort(key=lambda r: r.valid_from)
        for earlier, later in zip(rows, rows[1:], strict=False):
            if earlier.valid_to is None or earlier.valid_to > later.valid_from:
                raise InputDataError(
                    f"{path}: IP {ip} has two mappings in force from "
                    f"{later.valid_from.isoformat()}"
                )

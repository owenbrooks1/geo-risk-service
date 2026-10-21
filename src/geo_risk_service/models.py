"""Shared data models. Every component reads or writes these shapes.

Validation here is the first line of the guarded failure paths: a row that
does not fit its model is rejected at load (AC-09). All times are stored in
UTC and all distances are kilometres (INV-4).
"""

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    BeforeValidator,
    Field,
    IPvAnyAddress,
    model_validator,
)


class ConnectionType(StrEnum):
    RESIDENTIAL = "residential"
    MOBILE = "mobile"
    HOSTING = "hosting"


class Decision(StrEnum):
    FLAG = "flag"
    CLEAR = "clear"
    ABSTAIN = "abstain"


class Reason(StrEnum):
    IMPOSSIBLE_TRAVEL = "impossible_travel"
    POSSIBLE_TRAVEL = "possible_travel"
    INCONCLUSIVE = "inconclusive"
    NO_BASELINE = "no_baseline"
    UNRELIABLE_IP = "unreliable_ip"
    NO_IP_LOCATION = "no_ip_location"


class RejectReason(StrEnum):
    MISSING_VALUE = "missing_value"
    INVALID_IP = "invalid_ip"
    MISSING_TIMEZONE = "missing_timezone"
    DUPLICATE_LOGIN_ID = "duplicate_login_id"
    INVALID_VALUE = "invalid_value"


class Scenario(StrEnum):
    NORMAL = "normal"
    GENUINE_TRAVEL = "genuine_travel"
    IMPOSSIBLE_JUMP = "impossible_jump"
    VPN = "vpn"


def _blank_to_none(value):
    return None if value == "" else value


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


Text = Annotated[str, Field(min_length=1)]
UtcTime = Annotated[AwareDatetime, AfterValidator(_to_utc)]


class Login(BaseModel):
    login_id: Text
    customer_id: Text
    event_time: UtcTime
    ip: IPvAnyAddress


class IpLocation(BaseModel):
    """Where an IP address was located, and when that mapping was in force.

    In force from valid_from (inclusive) up to valid_to (exclusive). A blank
    valid_to means still in force (INV-6).
    """

    ip: IPvAnyAddress
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    accuracy_km: float = Field(ge=0)
    connection_type: ConnectionType
    valid_from: UtcTime
    valid_to: Annotated[UtcTime | None, BeforeValidator(_blank_to_none)] = None

    @model_validator(mode="after")
    def _window_is_positive(self):
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError("valid_to must be after valid_from")
        return self


class Truth(BaseModel):
    """Hidden truth for one login. Read by evaluation only (INV-5)."""

    login_id: Text
    suspicious: bool
    scenario: Scenario


class Assessment(BaseModel):
    """One decision with its evidence. Evidence is None where not reached."""

    login_id: str
    customer_id: str
    event_time: UtcTime
    decision: Decision
    reason: Reason
    policy_version: str
    baseline_login_id: str | None = None
    lat: float | None = None
    lon: float | None = None
    accuracy_km: float | None = None
    baseline_lat: float | None = None
    baseline_lon: float | None = None
    baseline_accuracy_km: float | None = None
    centre_km: float | None = None
    min_km: float | None = None
    max_km: float | None = None
    gap_hours: float | None = None
    min_speed_kmh: float | None = None
    max_speed_kmh: float | None = None


class Policy(BaseModel):
    """Versioned decision rules. Every assessment records the version."""

    version: Text
    max_speed_kmh: float = Field(gt=0)


class Settings(BaseModel):
    """Run settings. Logged in the run summary; not part of the policy."""

    seed: int
    customers: int = Field(gt=0)
    days: int = Field(gt=0)
    data_dir: Path
    db_path: Path

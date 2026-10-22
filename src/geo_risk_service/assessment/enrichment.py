"""Gather point-in-time evidence for each login.

Only evidence in force at the login's own time is used (INV-6), and this module
is never given hidden truth (INV-5). It gathers evidence; it does not decide.
"""

from dataclasses import dataclass
from datetime import datetime

from geo_risk_service.contracts.models import ConnectionType, IpLocation, Login

IpIndex = dict[str, list[IpLocation]]


@dataclass(frozen=True)
class Evidence:
    """What is known about one login at its own time.

    `place` is where its IP mapped at that moment (None if unmapped).
    `baseline` is the customer's most recent earlier usable login, if any.
    """

    login: Login
    place: IpLocation | None
    baseline: Login | None
    baseline_place: IpLocation | None


def build_index(ip_locations: list[IpLocation]) -> IpIndex:
    """Group IP mappings by address for fast lookup."""
    index: IpIndex = {}
    for row in ip_locations:
        index.setdefault(str(row.ip), []).append(row)
    return index


def locate(index: IpIndex, ip, at: datetime) -> IpLocation | None:
    """The mapping for `ip` in force at time `at`, or None.

    In force from valid_from (inclusive) up to valid_to (exclusive), so a
    mapping that starts after the login can never be used (INV-6).
    """
    for row in index.get(str(ip), []):
        if row.valid_from <= at and (row.valid_to is None or at < row.valid_to):
            return row
    return None


def _usable(place: IpLocation | None) -> bool:
    """A login can be a baseline only if its IP was mapped and not a data centre."""
    return place is not None and place.connection_type is not ConnectionType.HOSTING


def enrich(logins: list[Login], ip_locations: list[IpLocation]) -> list[Evidence]:
    """Evidence for every login, in event-time order.

    Logins are taken in (event_time, login_id) order, so "previous" means
    earlier in time, and same-time ties go to the lower login ID. Every usable
    login becomes the next baseline, whatever its decision (Q-A1).
    """
    index = build_index(ip_locations)
    last_usable: dict[str, tuple[Login, IpLocation]] = {}
    evidence = []
    for login in sorted(logins, key=lambda x: (x.event_time, x.login_id)):
        place = locate(index, login.ip, login.event_time)
        baseline, baseline_place = last_usable.get(login.customer_id, (None, None))
        evidence.append(Evidence(login, place, baseline, baseline_place))
        if _usable(place):
            last_usable[login.customer_id] = (login, place)
    return evidence

"""The decision rule: flag, clear or abstain, with a reason and the evidence.

Weak or unreliable evidence abstains; it never produces a reassuring answer
(INV-7). The threshold comes from versioned policy config, and every decision
records the version that made it.
"""

from dataclasses import dataclass

from geo_risk_service.assessment.enrichment import Evidence, enrich
from geo_risk_service.assessment.geo import distance_km
from geo_risk_service.contracts.models import (
    Assessment,
    ConnectionType,
    Decision,
    IpLocation,
    Login,
    Policy,
    Reason,
)


@dataclass(frozen=True)
class SpeedResult:
    """Outcome of the speed rule, with the distance and speed ranges used."""

    decision: Decision
    reason: Reason
    min_km: float
    max_km: float
    min_speed_kmh: float | None
    max_speed_kmh: float | None


def speed_rule(
    centre_km: float,
    radius_a: float,
    radius_b: float,
    gap_hours: float,
    max_speed_kmh: float,
) -> SpeedResult:
    """Decide from the most and least generous readings of the distance.

    Flag only if even the minimum speed is above the limit; clear only if even
    the maximum speed is at or below it; otherwise the evidence cannot decide.
    """
    min_km = max(0.0, centre_km - radius_a - radius_b)
    max_km = centre_km + radius_a + radius_b
    if gap_hours == 0:
        # Two places at the same instant is impossible; the same place tells
        # us nothing. Speeds are left empty rather than infinite.
        if min_km > 0:
            return SpeedResult(
                Decision.FLAG, Reason.IMPOSSIBLE_TRAVEL, min_km, max_km, None, None
            )
        return SpeedResult(
            Decision.ABSTAIN, Reason.INCONCLUSIVE, min_km, max_km, None, None
        )
    min_speed = min_km / gap_hours
    max_speed = max_km / gap_hours
    if min_speed > max_speed_kmh:
        decision, reason = Decision.FLAG, Reason.IMPOSSIBLE_TRAVEL
    elif max_speed <= max_speed_kmh:
        decision, reason = Decision.CLEAR, Reason.POSSIBLE_TRAVEL
    else:
        decision, reason = Decision.ABSTAIN, Reason.INCONCLUSIVE
    return SpeedResult(decision, reason, min_km, max_km, min_speed, max_speed)


def decide(evidence: Evidence, policy: Policy) -> Assessment:
    """Assess one login.

    Problems with this login's own IP are reported first, then a missing
    baseline, then the speed rule (Q-A2).
    """
    login, place = evidence.login, evidence.place
    fields = {
        "login_id": login.login_id,
        "customer_id": login.customer_id,
        "event_time": login.event_time,
        "policy_version": policy.version,
    }
    if place is not None:
        fields.update(lat=place.lat, lon=place.lon, accuracy_km=place.accuracy_km)

    def abstain(reason: Reason) -> Assessment:
        return Assessment(**fields, decision=Decision.ABSTAIN, reason=reason)

    if place is None:
        return abstain(Reason.NO_IP_LOCATION)
    if place.connection_type is ConnectionType.HOSTING:
        return abstain(Reason.UNRELIABLE_IP)
    if evidence.baseline is None:
        return abstain(Reason.NO_BASELINE)

    base = evidence.baseline_place
    centre_km = distance_km((base.lat, base.lon), (place.lat, place.lon))
    gap_hours = (login.event_time - evidence.baseline.event_time).total_seconds() / 3600
    result = speed_rule(
        centre_km, base.accuracy_km, place.accuracy_km, gap_hours, policy.max_speed_kmh
    )
    return Assessment(
        **fields,
        decision=result.decision,
        reason=result.reason,
        baseline_login_id=evidence.baseline.login_id,
        baseline_lat=base.lat,
        baseline_lon=base.lon,
        baseline_accuracy_km=base.accuracy_km,
        centre_km=centre_km,
        min_km=result.min_km,
        max_km=result.max_km,
        gap_hours=gap_hours,
        min_speed_kmh=result.min_speed_kmh,
        max_speed_kmh=result.max_speed_kmh,
    )


def assess(
    logins: list[Login], ip_locations: list[IpLocation], policy: Policy
) -> list[Assessment]:
    """Gather evidence for every login, then decide each one."""
    return [decide(e, policy) for e in enrich(logins, ip_locations)]

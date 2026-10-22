"""Enrichment tests: point-in-time IP lookup (INV-6) and distance (INV-4)."""

from datetime import datetime

import pytest

from geo_risk_service.assessment.enrichment import build_index, locate
from geo_risk_service.assessment.geo import distance_km
from geo_risk_service.assessment.ingest import load_ip_locations

SYDNEY = (-33.8688, 151.2093)
LONDON = (51.5074, -0.1278)


@pytest.fixture
def index(examples):
    """The fixture IP table, indexed for lookup."""
    return build_index(load_ip_locations(examples / "assess/ip_locations.csv"))


def at(text):
    """Parse an ISO time with a Z suffix."""
    return datetime.fromisoformat(text)


def test_inv4_distance_sydney_to_london_km():
    assert distance_km(SYDNEY, LONDON) == pytest.approx(16993.9, abs=0.1)


def test_inv4_distance_to_same_place_is_zero():
    assert distance_km(SYDNEY, SYDNEY) == 0


def test_inv6_mapping_in_force_just_before_reassignment(index):
    assert locate(index, "192.0.2.50", at("2026-05-01T11:59:59Z")).lat == SYDNEY[0]


def test_inv6_new_mapping_from_its_start_time(index):
    """Start inclusive, end exclusive: at exactly 12:00 the London mapping applies."""
    assert locate(index, "192.0.2.50", at("2026-05-01T12:00:00Z")).lat == LONDON[0]


def test_inv6_mapping_not_in_force_at_its_end_time(index):
    """The Sydney mapping on its own: not in force at exactly 12:00 (end
    exclusive). Checked alone so the result cannot depend on file order."""
    sydney_only = build_index(
        [r for r in index["192.0.2.50"] if r.valid_to is not None]
    )
    assert locate(sydney_only, "192.0.2.50", at("2026-05-01T11:59:59Z")) is not None
    assert locate(sydney_only, "192.0.2.50", at("2026-05-01T12:00:00Z")) is None


def test_inv6_mapping_starting_after_the_login_is_not_used(index):
    assert locate(index, "192.0.2.60", at("2026-05-01T09:00:00Z")) is None
    assert locate(index, "192.0.2.60", at("2026-05-01T09:00:01Z")) is not None


def test_unknown_ip_has_no_location(index):
    assert locate(index, "192.0.2.99", at("2026-05-01T09:00:00Z")) is None

"""Generator tests (AC-01, INV-1, INV-3, INV-4, INV-5).

Scenario checks use a distance formula written here, not the generator's own,
so the generator cannot pass by agreeing with itself.
"""

import csv
import hashlib
import ipaddress
from collections import defaultdict
from datetime import datetime
from math import asin, cos, radians, sin, sqrt

import pytest

from geo_risk_service.generator import generate, write_dataset
from geo_risk_service.models import IpLocation, Login, Scenario, Truth

DOC_RANGES = [
    ipaddress.ip_network(n)
    for n in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
]
MAX_SPEED_KMH = 1000


def km(a, b):
    """Great-circle distance in km, written here independently of the generator."""
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * asin(sqrt(h))


def read_csv(path):
    """Read a CSV file as a list of dicts, one per row."""
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """A seed 42 dataset written once and shared by the tests in this file."""
    out = tmp_path_factory.mktemp("seed42")
    write_dataset(generate(seed=42, customers=20, days=10), out)
    return out


@pytest.fixture(scope="module", params=[42, 1, 2, 3])
def scenario_rows(request, tmp_path_factory):
    """Datasets for the scenario checks: seed 42 plus three others, so a
    generator change cannot quietly break the scenarios for other seeds."""
    out = tmp_path_factory.mktemp(f"seed{request.param}")
    write_dataset(generate(seed=request.param, customers=50, days=30), out)
    return {
        name: read_csv(out / f"{name}.csv")
        for name in ("logins", "ip_locations", "truth")
    }


@pytest.fixture(scope="module")
def rows(written):
    """The written dataset read back from CSV, by table name."""
    return {
        name: read_csv(written / f"{name}.csv")
        for name in ("logins", "ip_locations", "truth")
    }


def test_ac01_inv3_same_seed_gives_identical_files(tmp_path, written):
    write_dataset(generate(seed=42, customers=20, days=10), tmp_path)
    for name in ("logins.csv", "ip_locations.csv", "truth.csv"):
        assert (tmp_path / name).read_bytes() == (written / name).read_bytes(), name


# Checksum of seed 42 (20 customers, 10 days), computed in a separate process
# with a different hash seed. Pins the output across processes and machines on
# Python 3.12 (.python-version). Update it only for an intended generator change.
SEED_42_SHA256 = "85181a609e3ecfeb1e36631479e7131847f55dc37481d0f53d467d70abc6b723"


def test_ac01_inv3_seed_42_output_matches_recorded_checksum(written):
    digest = hashlib.sha256()
    for name in ("logins.csv", "ip_locations.csv", "truth.csv"):
        digest.update((written / name).read_bytes())
    assert digest.hexdigest() == SEED_42_SHA256


def test_ac01_inv3_different_seed_gives_different_logins(tmp_path, written):
    write_dataset(generate(seed=43, customers=20, days=10), tmp_path)
    assert (tmp_path / "logins.csv").read_bytes() != (
        written / "logins.csv"
    ).read_bytes()


def test_ac01_every_login_has_exactly_one_truth_label(rows):
    login_ids = [r["login_id"] for r in rows["logins"]]
    truth_ids = [r["login_id"] for r in rows["truth"]]
    assert len(login_ids) == len(set(login_ids)) > 0
    assert sorted(truth_ids) == sorted(login_ids)


def test_ac01_all_four_scenarios_appear_with_four_customers():
    dataset = generate(seed=42, customers=4, days=10)
    assert {t.scenario for t in dataset.truth} == set(Scenario)


def test_ac01_inv4_every_row_parses_and_times_are_utc(rows):
    for r in rows["logins"]:
        assert r["event_time"].endswith("Z")
        Login(**r)
    for r in rows["ip_locations"]:
        assert r["valid_from"].endswith("Z")
        IpLocation(**r)
    for r in rows["truth"]:
        Truth(**r)


def test_inv5_truth_is_not_in_the_inputs(written):
    with open(written / "logins.csv", newline="") as f:
        assert next(csv.reader(f)) == ["login_id", "customer_id", "event_time", "ip"]
    with open(written / "ip_locations.csv", newline="") as f:
        header = next(csv.reader(f))
    assert "suspicious" not in header and "scenario" not in header


def test_inv1_every_ip_is_a_documentation_address(rows):
    for r in rows["logins"] + rows["ip_locations"]:
        ip = ipaddress.ip_address(r["ip"])
        assert any(ip in net for net in DOC_RANGES), r["ip"]


def test_ip_table_has_one_mapping_per_ip(rows):
    """No IP has two mappings in force at once (that would stop the run, AC-11)."""
    ips = [r["ip"] for r in rows["ip_locations"]]
    assert len(ips) == len(set(ips))


def test_ac01_only_planted_jumps_are_suspicious(scenario_rows):
    for r in scenario_rows["truth"]:
        assert (r["suspicious"] == "true") == (r["scenario"] == "impossible_jump"), r


def _timelines(rows):
    """Each customer's logins in time order, with location, radius and truth."""
    places = {r["ip"]: r for r in rows["ip_locations"]}
    truth = {r["login_id"]: r for r in rows["truth"]}
    by_customer = defaultdict(list)
    for r in rows["logins"]:
        place = places[r["ip"]]
        by_customer[r["customer_id"]].append(
            {
                "id": r["login_id"],
                "time": datetime.fromisoformat(r["event_time"]),
                "at": (float(place["lat"]), float(place["lon"])),
                "radius": float(place["accuracy_km"]),
                "hosting": place["connection_type"] == "hosting",
                "scenario": truth[r["login_id"]]["scenario"],
                "suspicious": truth[r["login_id"]]["suspicious"] == "true",
            }
        )
    for logins in by_customer.values():
        logins.sort(key=lambda x: (x["time"], x["id"]))
    return by_customer.values()


def test_ac01_planted_jumps_are_impossible(scenario_rows):
    """Each jump is at least 3,000 km and 30 to 90 minutes from the previous login."""
    jumps = 0
    for logins in _timelines(scenario_rows):
        for prev, cur in zip(logins, logins[1:], strict=False):
            if cur["scenario"] == "impossible_jump":
                jumps += 1
                minutes = (cur["time"] - prev["time"]).total_seconds() / 60
                assert cur["suspicious"]
                assert km(prev["at"], cur["at"]) >= 3000
                assert 30 <= minutes <= 90
    assert jumps > 0


def test_ac01_genuine_logins_are_reachable_from_last_usable_login(scenario_rows):
    """Every genuine, non-VPN login is reachable at 1,000 km/h even with both
    radii added, from the customer's previous non-VPN login. This covers home
    logins, travel arrivals and returns, and the login after a jump (Q-G1)."""
    checked = {"home": 0, "travel_away": 0, "after_jump": 0}
    for logins in _timelines(scenario_rows):
        last = None
        for cur in logins:
            if cur["hosting"]:
                assert cur["scenario"] == "vpn" and not cur["suspicious"]
                continue
            if last is not None and not cur["suspicious"]:
                hours = (cur["time"] - last["time"]).total_seconds() / 3600
                distance = km(last["at"], cur["at"])
                worst_km = distance + last["radius"] + cur["radius"]
                assert hours > 0, cur["id"]
                assert worst_km / hours <= MAX_SPEED_KMH, cur["id"]
                # Count what was really checked, so the test cannot pass on
                # home logins alone.
                if last["suspicious"]:
                    checked["after_jump"] += 1
                elif cur["scenario"] == "genuine_travel" and distance > 0:
                    checked["travel_away"] += 1
                else:
                    checked["home"] += 1
            last = cur
    assert all(n > 0 for n in checked.values()), checked

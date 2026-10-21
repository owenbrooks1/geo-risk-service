"""Seeded synthetic data: customers' logins, the IP location table and hidden truth.

Synthetic only (INV-1): IPs come from the address ranges reserved for
documentation, and customers are invented. The same seed always gives the same
data (INV-3). Truth is written to its own file and never to the inputs (INV-5).
"""

import csv
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_network
from math import asin, cos, radians, sin, sqrt
from pathlib import Path
from random import Random

from geo_risk_service.models import ConnectionType, IpLocation, Login, Scenario, Truth

# Fixed start date, so output never depends on when the generator runs (INV-3).
START = datetime(2026, 5, 1, tzinfo=UTC)
# Accuracy radius given to every generated IP location.
RADIUS_KM = 25.0
# Spacing target for logins that must look reachable. Kept separate from the
# policy on purpose: the planted truth must not be shaped by the rule it tests.
MAX_SPEED_KMH = 1000.0
# Assumed flight speed for genuine trips, well under the 1,000 km/h limit.
FLIGHT_KMH = 800.0
# A planted jump is at least this far, so it is impossible in 90 minutes.
MIN_JUMP_KM = 3000.0

# Public city coordinates. Not customer data.
CITIES = {
    "Sydney": (-33.8688, 151.2093),
    "Melbourne": (-37.8136, 144.9631),
    "Brisbane": (-27.4698, 153.0251),
    "Perth": (-31.9505, 115.8605),
    "Auckland": (-36.8485, 174.7633),
    "Singapore": (1.3521, 103.8198),
    "Hong Kong": (22.3193, 114.1694),
    "Tokyo": (35.6762, 139.6503),
    "Mumbai": (19.0760, 72.8777),
    "Dubai": (25.2048, 55.2708),
    "London": (51.5074, -0.1278),
    "Paris": (48.8566, 2.3522),
    "Berlin": (52.5200, 13.4050),
    "Johannesburg": (-26.2041, 28.0473),
    "New York": (40.7128, -74.0060),
    "Toronto": (43.6532, -79.3832),
    "Chicago": (41.8781, -87.6298),
    "Los Angeles": (34.0522, -118.2437),
    "Sao Paulo": (-23.5505, -46.6333),
    "Mexico City": (19.4326, -99.1332),
}
# Data centres where VPN exit servers sit. A VPN login appears to come from here.
DATA_CENTRES = {
    "Frankfurt": (50.1109, 8.6821),
    "Ashburn": (39.0438, -77.4874),
    "Dallas": (32.7767, -96.7970),
}
# Every usable address in the three ranges reserved for documentation, so a
# generated IP can never belong to a real host (INV-1).
DOC_ADDRESSES = [
    str(ip)
    for net in ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24")
    for ip in ip_network(net).hosts()
]
IPS_PER_CITY = 10
IPS_PER_DATA_CENTRE = 5
VPN_LOGINS = 3


@dataclass
class Dataset:
    """The three generated tables, as contract models."""

    logins: list[Login]
    ip_locations: list[IpLocation]
    truth: list[Truth]


def _km(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great-circle distance in km between two (lat, lon) points.

    The generator's own copy: it must not share code with the assessment it
    will be used to judge.
    """
    lat1, lon1, lat2, lon2 = map(radians, (*a, *b))
    h = (
        sin((lat2 - lat1) / 2) ** 2
        + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    )
    return 2 * 6371.0 * asin(sqrt(h))


def _reachable_after(a, b) -> timedelta:
    """Shortest gap at which b is reachable from a, even with both radii added."""
    return timedelta(hours=(_km(a, b) + 2 * RADIUS_KM) / MAX_SPEED_KMH)


def _ip_table(rng: Random):
    """Build the IP location table.

    Each city gets a pool of residential IPs and each data centre a pool of
    hosting IPs. All are valid from the start and never reassigned, so no IP
    has two mappings in force at once. Returns the table rows, the city pools
    and the hosting IPs.
    """
    # Shuffle once, then hand out addresses in order, so no IP is used twice.
    addresses = DOC_ADDRESSES[:]
    rng.shuffle(addresses)
    pool = iter(addresses)
    city_ips = {c: [next(pool) for _ in range(IPS_PER_CITY)] for c in CITIES}
    rows = [
        IpLocation(
            ip=ip,
            lat=CITIES[c][0],
            lon=CITIES[c][1],
            accuracy_km=RADIUS_KM,
            connection_type=ConnectionType.RESIDENTIAL,
            valid_from=START,
        )
        for c, ips in city_ips.items()
        for ip in ips
    ]
    hosting_ips = []
    for lat, lon in DATA_CENTRES.values():
        for _ in range(IPS_PER_DATA_CENTRE):
            ip = next(pool)
            hosting_ips.append(ip)
            rows.append(
                IpLocation(
                    ip=ip,
                    lat=lat,
                    lon=lon,
                    accuracy_km=RADIUS_KM,
                    connection_type=ConnectionType.HOSTING,
                    valid_from=START,
                )
            )
    return rows, city_ips, hosting_ips


def _scenario_plan(rng: Random, customers: int) -> list[Scenario]:
    """One scenario per customer: 70% normal, 10% each of the others.

    At least one of each, so any run of 4 or more customers has all four. The counts are
    fixed; the seeded shuffle decides which customer gets which.
    """
    special = max(1, round(customers * 0.1))
    plan = [Scenario.GENUINE_TRAVEL, Scenario.IMPOSSIBLE_JUMP, Scenario.VPN] * special
    plan = plan[:customers] + [Scenario.NORMAL] * max(0, customers - len(plan))
    if Scenario.NORMAL not in plan:
        plan[-1] = Scenario.NORMAL
    rng.shuffle(plan)
    return plan


def _home_times(rng: Random, days: int) -> list[datetime]:
    """0 to 3 home login times a day.

    Each falls in its own 6-hour block and before the block's last 30 minutes,
    so two home logins are always at least 30 minutes apart.
    """
    times = []
    for day in range(days):
        blocks = sorted(rng.sample(range(4), rng.randint(0, 3)))
        for block in blocks:
            minute = rng.randint(0, 6 * 60 - 31)
            times.append(START + timedelta(days=day, hours=6 * block, minutes=minute))
    return times


def generate(seed: int, customers: int, days: int) -> Dataset:
    """Generate a full synthetic dataset. The same arguments always give the
    same result (INV-3)."""
    rng = Random(seed)
    ip_rows, city_ips, hosting_ips = _ip_table(rng)
    city_names = list(CITIES)
    events = []  # (time, customer_id, ip, scenario, suspicious)

    for n, scenario in enumerate(_scenario_plan(rng, customers), start=1):
        customer = f"C-{n:04d}"
        home = rng.choice(city_names)
        home_ip = rng.choice(city_ips[home])
        times = _home_times(rng, days)
        if len(times) < 2:  # every scenario needs a home login before and after
            last_day = START + timedelta(days=days - 1)
            times = [last_day + timedelta(hours=9), last_day + timedelta(hours=21)]
        # Start with home logins only; a scenario is then planted after one of
        # them (the anchor), and later home logins are kept or dropped to fit.
        timeline = [(t, home_ip, home, Scenario.NORMAL, False) for t in times]
        anchor = rng.randrange(len(timeline) - 1)
        base_time = timeline[anchor][0]
        later = timeline[anchor + 1 :]

        if scenario is Scenario.IMPOSSIBLE_JUMP:
            # A login from a far city 30 to 90 minutes after the anchor: no one
            # could travel that fast, so it is the one suspicious login.
            far = [c for c in city_names if _km(CITIES[home], CITIES[c]) >= MIN_JUMP_KM]
            city = rng.choice(far)
            jump_time = base_time + timedelta(minutes=rng.randint(30, 90))
            jump = (jump_time, rng.choice(city_ips[city]), city, scenario, True)
            # Drop home logins until home is reachable from the jump city again,
            # so only the jump itself looks impossible (Q-G1).
            back = jump_time + _reachable_after(CITIES[city], CITIES[home])
            timeline = (
                timeline[: anchor + 1] + [jump] + [x for x in later if x[0] >= back]
            )

        elif scenario is Scenario.GENUINE_TRAVEL:
            # A real trip: fly out at airliner speed plus an hour, stay 1 to 3
            # days, fly home the same way. Every step is reachable, so genuine.
            city = rng.choice([c for c in city_names if c != home])
            flight = timedelta(
                hours=(_km(CITIES[home], CITIES[city]) + 2 * RADIUS_KM) / FLIGHT_KMH + 1
            )
            arrive = base_time + flight
            stay = timedelta(days=rng.randint(1, 3))
            depart = arrive + stay
            home_again = depart + flight
            trip = [
                (arrive, rng.choice(city_ips[city]), city, scenario, False),
                (depart, rng.choice(city_ips[city]), city, scenario, False),
                (home_again, home_ip, home, scenario, False),
            ]
            # Home logins during the trip are dropped; the customer was away.
            timeline = (
                timeline[: anchor + 1]
                + trip
                + [x for x in later if x[0] > home_again + timedelta(minutes=30)]
            )

        elif scenario is Scenario.VPN:
            # The real customer on a privacy VPN: a few logins at random times
            # that appear to come from a data centre. Genuine (Q-G2); the
            # policy should abstain on them.
            for _ in range(VPN_LOGINS):
                t = START + timedelta(minutes=rng.randrange(days * 24 * 60))
                timeline.append((t, rng.choice(hosting_ips), "vpn", scenario, False))

        for t, ip, _place, scen, suspicious in timeline:
            events.append((t, customer, ip, scen, suspicious))

    # Sort all customers' logins together, then number them, so login IDs
    # follow time order and are the same on every run.
    events.sort(key=lambda e: (e[0], e[1], e[2]))
    logins, truth = [], []
    for i, (t, customer, ip, scenario, suspicious) in enumerate(events, start=1):
        login_id = f"L-{i:06d}"
        logins.append(
            Login(login_id=login_id, customer_id=customer, event_time=t, ip=ip)
        )
        truth.append(Truth(login_id=login_id, suspicious=suspicious, scenario=scenario))
    return Dataset(logins=logins, ip_locations=ip_rows, truth=truth)


def _utc(t: datetime) -> str:
    """Format a time as UTC with a Z suffix, e.g. 2026-05-01T09:00:00Z (INV-4)."""
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path: Path, header: list[str], rows) -> None:
    """Write one CSV file.

    A fixed "\\n" line ending keeps the bytes identical on every operating
    system, which the determinism test relies on.
    """
    with open(path, "w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


def write_dataset(dataset: Dataset, data_dir: Path) -> None:
    """Write the three CSV files. Truth goes only to truth.csv (INV-5)."""
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    _write(
        data_dir / "logins.csv",
        ["login_id", "customer_id", "event_time", "ip"],
        [(x.login_id, x.customer_id, _utc(x.event_time), x.ip) for x in dataset.logins],
    )
    _write(
        data_dir / "ip_locations.csv",
        [
            "ip",
            "lat",
            "lon",
            "accuracy_km",
            "connection_type",
            "valid_from",
            "valid_to",
        ],
        [
            (
                x.ip,
                x.lat,
                x.lon,
                x.accuracy_km,
                x.connection_type,
                _utc(x.valid_from),
                "",  # never reassigned, so every mapping is still in force
            )
            for x in dataset.ip_locations
        ],
    )
    _write(
        data_dir / "truth.csv",
        ["login_id", "suspicious", "scenario"],
        [(x.login_id, str(x.suspicious).lower(), x.scenario) for x in dataset.truth],
    )

# Plan: assessment (ingest, point-in-time evidence, decision rule)

## Context

Contracts (`207a4da`) and generator (`f81ed4b`) are done. Assessment is the core of the product. It loads logins and the IP table safely, gathers point-in-time evidence for each login, and decides flag, clear or abstain. It owns AC-02 to AC-12, and it's where INV-5, INV-6 and INV-7 are most at risk. The hand-written fixtures in `examples/` already hold the known answers.

## Paths
- **Touch:**
  - `src/geo_risk_service/{ingest,geo,enrichment,policy}.py`;
  - `tests/test_{ingest,enrichment,policy}.py`.
- **Do not touch:** contracts files, `examples/`, `config/`, `generator.py`, or anything under service (`run.py`, `api.py`, `evaluation.py`).

## Design: four small modules, plain functions

| Module | Function | What it does |
|---|---|---|
| `ingest.py` | `load_logins(path) -> LoadResult` | Reads `logins.csv`. Each bad row is rejected with its line number and a reason code. For a duplicate ID, the first row is kept. Returns the logins kept and the rejections. Header-only input gives 0 and 0, with no error (AC-09, AC-10). |
| `ingest.py` | `load_ip_locations(path) -> list[IpLocation]` | Reads the IP table. A missing file, an empty file, an invalid row, or two mappings for one IP in force at once all stop the run with `ReferenceDataError`, naming the file and the problem (AC-11). |
| `geo.py` | `distance_km(a, b)` | Great-circle distance on a 6,371 km radius (INV-4). |
| `enrichment.py` | `locate(ip, at, index)` | Finds the mapping in force at time `at`: start inclusive, end exclusive (INV-6). Nothing after the login time can be used. |
| `enrichment.py` | `enrich(logins, ip_locations) -> list[Evidence]` | Goes through each customer's logins in (event_time, login_id) order. For each login it records the current location (or none), plus the most recent earlier **usable** login (mapped and not hosting) as the baseline (AC-05, AC-06, AC-07). It never sees truth (INV-5). |
| `policy.py` | `decide(evidence, policy) -> Assessment` | Applies the rule (below) and records the reason, the evidence and the policy version. |
| `policy.py` | `assess(logins, ip_locations, policy)` | `enrich`, then `decide` on each login. This is the one call the service stage will use. |

**Decision rule** (agreed in intent; the order is set by Q-A2):
1. No mapping in force at the login time: abstain, `no_ip_location`.
2. Hosting IP: abstain, `unreliable_ip`.
3. No usable earlier login: abstain, `no_baseline`.
4. Minimum distance = max(0, centre distance minus both radii). Maximum distance = centre distance plus both radii.
   - If the time gap is 0: flag if the minimum distance is above 0, otherwise abstain `inconclusive`.
   - Otherwise: flag if minimum speed is above the threshold; clear if maximum speed is at or below it; abstain `inconclusive` if neither.

## Tests first, with known answers
- **`test_policy.py`, end to end from the fixtures:** every row of `examples/assess/expected.csv` matches its decision, its reason and its speed range to within 0.1 km/h. This covers AC-02 to AC-08: flag 16,943.9 to 17,043.9; clear 331.7 to 381.7; inconclusive 884.6 to 1,017.9; VPN comparing with Sydney rather than the VPN login; 11:59 versus 12:00 IP reassignment; zero time gap.
- **`test_policy.py`, AC-08 threshold, with evidence built directly:**
  - 1,000 km, zero radii, 1 hour gives clear;
  - 1,010 km with 5 km radii (range 1,000 to 1,020) over 1 hour gives abstain `inconclusive`, because a minimum of exactly 1,000 does not flag.
- **`test_ingest.py`:**
  - AC-09: the bad-rows fixture matches `expected_rejections.csv` exactly by line, ID and reason. 2 rows are kept, and `B-06` (`+10:00`) is stored as UTC.
  - AC-10: header-only input gives 0 and 0.
  - AC-11: a missing, empty, invalid or overlapping IP table each raise `ReferenceDataError`. The overlap fixture names `203.0.113.10`.
- **`test_enrichment.py`:**
  - INV-6: `locate` at exactly a mapping's end time returns the next mapping, and 1 second before its start returns nothing.
  - `distance_km` from Sydney to London is 16,993.9 km.
- **AC-12 and INV-5:**
  - deciding with no truth file present gives the same results as with `truth.csv` sitting next to the inputs;
  - a structural test: no assessment module mentions `truth` or imports `Truth`.

## Hard rules at risk, and mutation checks (proposed at close)
- **INV-6:** change `at < valid_to` to `<=`. The 12:00 fixture should then fail.
- **INV-7:** change "clear if maximum speed is at or below" to use the minimum speed instead. AC-04 should then fail.
- **INV-5:** the structural test.

## Not built here
Writing to DuckDB, the run summary and logging (service), the API, evaluation, `POST /assess`, and the order-independence test (AC-21, ENHANCE). Sorting by event time is built here anyway, as Q5 g requires.

## Decisions from the grill
- **Q-A1, baseline:** every usable login (mapped and not hosting) becomes the next baseline, whatever its decision.
  - Gathering evidence never depends on the decision, which keeps enrichment and policy separate.
  - A genuine login soon after an attack may also flag. A false alarm never causes a chain of later flags.
  - Known answer, added to the tests with evidence built directly: Sydney 09:00, London 09:40 (flag), then Sydney 10:30. The 10:30 login is compared with London and flags.
- **Q-A2, reason order:** problems with this login's own IP come first: `no_ip_location`, then `unreliable_ip`, then `no_baseline`, then the speed rule. Known answer: a customer whose first login is from a VPN gets `unreliable_ip`.
- **Q-A3, missing logins file:** the run stops with `ReferenceDataError` naming the path. An empty file is still 0 logins, with no error. This tells "no logins" (fine) apart from "never got the logins" (a fault).

## Record on approval
- Save as `docs/plans/assessment-decision-rule.md`.
- Mark assessment "in progress" on `main`.
- Remove the open question from `docs/components.md`, now that it's answered.

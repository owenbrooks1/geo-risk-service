# Plan: contracts (shared layout, data models, config, fixtures)

## Context

Intent and AC-01 to AC-22 are agreed (`evidence/intent.md`, decisions in `docs/plans/intent-acceptance-criteria.md`). Before the three components (generator, assessment, service) are built, the shared contracts must exist on `main`, so each builds on fixed shapes:
- the package layout and who owns which path;
- the data models every component reads or writes;
- the config files;
- the hand-written fixtures (known answers) the component tests will use.

Contracts holds no decision logic. It defines shapes and validates them. Built on `main` in the lead session.

## Package layout and ownership

| Path | Owner | Purpose |
|---|---|---|
| `src/geo_risk_service/models.py` | contracts | Data models |
| `src/geo_risk_service/config.py` | contracts | Load and validate both config files |
| `src/geo_risk_service/schema.py` | contracts | DuckDB table definitions for results |
| `config/policy.yaml`, `config/settings.yaml` | contracts | Policy v1; run settings |
| `examples/` | contracts | Hand-written fixtures and expected answers |
| `tests/test_contracts.py`, `tests/conftest.py` | contracts | Contract tests; shared fixture paths |
| `generator.py`, `tests/test_generator.py` | generator | |
| `ingest.py`, `geo.py`, `enrichment.py`, `policy.py`, with matching `tests/test_*.py` | assessment | Row loading and rejection, IP table checks, distance, point-in-time evidence, decision rule |
| `evaluation.py`, `run.py`, `api.py`, with matching tests; the `Makefile` `demo` target; the README run section | service | |
| `data/` (gitignored) | written at run time | |

Source paths are under `src/geo_risk_service/`. A change to the contracts during a later stage is raised with the owner first. `docs/components.md` is updated with these paths.

## Decisions from the grill
- **Q-C1, times:** any explicit offset is accepted and converted to UTC. Naive times are rejected (INV-4, AC-09).
- **Q-C2, data flow:**
  - CSV for `logins.csv`, `ip_locations.csv` and `truth.csv`. Results go in DuckDB.
  - `config/policy.yaml` holds the versioned decision rules, which are stamped on every decision.
  - `config/settings.yaml` holds the seed, sizes and paths, which are logged in the run summary.
  - Only the evaluation function is ever passed the truth path (INV-5).
- **Q-C3, IP table:**
  - One row per exact IP. `valid_from` is inclusive; `valid_to` is exclusive, and blank means still in force.
  - Two rows for the same IP in force at the same moment are a reference-data fault, and the run stops. Implemented in assessment's `ingest.py`. AC-11's known answer is extended to cover it.
  - Fixture IPs use the ranges reserved for documentation (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), so they can never be real hosts (INV-1).

## Data models (`models.py`, pydantic)
- **Enums:**
  - `ConnectionType`: residential, mobile, hosting.
  - `Decision`: flag, clear, abstain.
  - `Reason`: `impossible_travel`, `possible_travel`, `inconclusive`, `no_baseline`, `unreliable_ip`, `no_ip_location`.
  - `Scenario`: normal, genuine_travel, impossible_jump, vpn.
- **`Login`:** `login_id`, `customer_id`, `event_time` (must carry an offset, stored as UTC) and `ip` (IPv4 or IPv6).
- **`IpLocation`:** `ip`, `lat` (-90 to 90), `lon` (-180 to 180), `accuracy_km` (0 or more), `connection_type`, `valid_from`, and `valid_to` (optional, must be after `valid_from`).
- **`Truth`:** `login_id`, `suspicious`, `scenario`.
- **`Assessment`:** `login_id`, `customer_id`, `event_time`, `decision`, `reason` and `policy_version`. Evidence fields are null when not reached: `baseline_login_id`, current and baseline lat, lon and accuracy, `centre_km`, `min_km`, `max_km`, `gap_hours`, `min_speed_kmh` and `max_speed_kmh`.
- **`Policy`:** `version` (non-empty), `max_speed_kmh` (above 0).
- **`Settings`:** `seed` (int), `customers` (above 0), `days` (above 0), `data_dir`, `db_path`.

## Fixtures (`examples/`)
- `examples/assess/`: `logins.csv`, `ip_locations.csv` and `expected.csv` (`login_id`, decision, reason, speed range). One customer per case, covering AC-02 to AC-08 with the known answers from `intent.md`.
- `examples/bad_rows/logins.csv`: AC-09. A missing IP, an invalid IP, a naive time and a duplicate ID, plus valid rows.
- `examples/ip_overlap/ip_locations.csv`: AC-11 overlap case.
- `examples/evaluation/`: `assessments.csv` and `truth.csv` for AC-13.

## Tests first (`tests/test_contracts.py`), with known answers
- **AC-11 (config):**
  - `config/policy.yaml` loads as version `v1`, 1000.0.
  - A missing file, `max_speed_kmh: -5` or a missing version each raise a clear error naming the problem.
  - `settings.yaml` with `customers: 0` raises.
- **AC-09 (models):** `Login` rejects naive `2026-05-01T10:00:00`, IP `999.1.1.1`, and a missing IP.
- **INV-4:** `2026-05-01T10:00:00+10:00` is stored as `2026-05-01T00:00:00Z`.
- **Q-C3:** an `IpLocation` whose `valid_to` is not after `valid_from` is rejected. A blank `valid_to` loads as open-ended.
- **Fixture integrity:**
  - every valid fixture row parses under the models;
  - `expected.csv` covers each of AC-02 to AC-08 at least once;
  - every expected decision and reason is a valid enum value.

## Hard rules at risk
- **INV-4:** the offset conversion test above.
- **INV-5:** the truth path appears only in `Settings`, and is passed only to evaluation. This is enforced in the assessment and service stages (AC-12).
- **INV-6:** the inclusive/exclusive validity contract is fixed here and tested in assessment (AC-07).
- **INV-1:** fixture IPs come from the documentation ranges only.

## Not built here
Decision logic, distance maths, the generator, ingestion with row counting, the overlap check, evaluation, the API and the demo target.

## Record on approval
- Save this plan as `docs/plans/contracts-shared-layout.md`.
- Mark contracts "in progress" on `main` in `docs/components.md`, with the owned paths filled in.
- Extend the AC-11 known answer in `evidence/intent.md` to include the overlap case.

## Verification
- `make verify` is green, with tests citing AC-09, AC-11 and INV-4.
- The contract tests are written first, shown failing, then made to pass.

# Geospatial Risk Intelligence Service

A small, locally runnable service that checks each login for impossible travel, using only the IP location evidence available at that moment. It explains every decision and abstains when the evidence is weak. Built with Python, DuckDB and FastAPI, on synthetic data only.

**Status:** complete for the agreed core scope: all 18 core acceptance criteria are built and tested.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and `make`. uv installs the pinned Python 3.12 and all dependencies. No network access, accounts or credentials are needed to run the service.

```sh
uv sync
```

## Verify

```sh
make verify
```

Runs lint, format and lock checks, then the tests. The same command runs in CI.

## Run

```sh
make demo    # generate seed 42 data, assess every login, evaluate, print the report
make serve   # serve the results on http://127.0.0.1:8000 (local only)
```

`make demo` logs one JSON summary line and prints the evaluation (excerpt):

```
{"event": "run_complete", "run_at": "2026-10-22T00:35:53Z", "seed": 42, "policy_version": "v1", "loaded": 4480, "rejected_by_reason": {}, "decisions_by_outcome": {"abstain": 130, "clear": 4340, "flag": 10}}
Evaluation against hidden truth
  precision:            1.000
  recall:               1.000  (abstain = miss)
  false clears:         0
  abstain rate:         0.029

By planted scenario (decisions each scenario received)
  genuine_travel  {'clear': 30}
  impossible_jump {'flag': 10}
  normal          {'abstain': 100, 'clear': 4310}
  vpn             {'abstain': 30}
```

Every planted scenario received the decision it was designed to get. The 100 `normal` abstains are each customer's first login, which has no earlier location to compare with.

These numbers show the policy behaves as designed on planted scenarios. They are not a measure of real-world performance.

## Example

A login from Johannesburg 40 minutes after one from Sydney:

```sh
curl http://127.0.0.1:8000/assessments/L-000633
```

```json
{"login_id": "L-000633", "customer_id": "C-0081", "event_time": "2026-05-05T09:53:00Z",
 "decision": "flag", "reason": "impossible_travel", "policy_version": "v1",
 "baseline_login_id": "L-000628", "gap_hours": 0.667,
 "min_km": 10990.5, "max_km": 11090.5,
 "min_speed_kmh": 16485.8, "max_speed_kmh": 16635.8, "...": "..."}
```

Even the most generous reading of the two IP locations needs 16,486 km/h, so the login is flagged. `GET /health` returns 503 with a reason until `make demo` has run. An unknown login ID returns 404.

## Code map

| Folder | What it does |
|---|---|
| `src/geo_risk_service/contracts/` | Shared data models, config loading, result tables |
| `src/geo_risk_service/generator/` | Seeded synthetic logins, IP table and hidden truth |
| `src/geo_risk_service/assessment/` | Safe loading, point-in-time IP evidence, the flag, clear or abstain rule |
| `src/geo_risk_service/service/` | Run and logging, evaluation against truth, the read-only API |
| `config/` | `policy.yaml` (versioned decision rules) and `settings.yaml` (seed, sizes, paths) |
| `examples/` | Hand-written fixtures with known answers, used by the tests |
| `tests/` | One test file per module; each test names the criterion or rule it checks |

## Known limitations

- **Synthetic, clean scenarios.** Precision and recall of 1.0 show that the rule behaves as designed on planted cases. They are not a measure of real-world accuracy. Harder scenarios (attackers using VPNs, coarse IP locations, attackers close enough to reach) are the next step and would show the method's limits.
- **IP location is the only signal.** VPN logins abstain rather than being resolved. Card-present merchant and ATM data would close that gap.
- **Batch only.** No streaming ingestion; the per-login function is ready for it (see `evidence/decisions.md`, D4).
- **Local only.** The API has no authentication and listens on 127.0.0.1. The production approach is in `evidence/operate.md`.
- **Optional extras not built:** list filters, an evaluation endpoint, and live single-login assessment.

## Links

- Working method and hard rules: [`AGENTS.md`](AGENTS.md)
- Evidence pack: [`evidence/`](evidence/): intent, design, decisions, verification, operation and agentic workflow
- Component status: [`docs/components.md`](docs/components.md)

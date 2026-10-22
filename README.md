# Geospatial Risk Intelligence Service

A small, locally runnable service that checks each login for impossible travel, using only the IP location evidence available at that moment. It explains every decision and abstains when the evidence is weak. Built with Python, DuckDB and FastAPI, on synthetic data only.

**Status:** in progress.

## Setup

Requires [uv](https://docs.astral.sh/uv/) and `make`.

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
{"event": "run_complete", "seed": 42, "policy_version": "v1", "loaded": 4480, "rejected_by_reason": {}, "decisions_by_outcome": {"abstain": 130, "clear": 4340, "flag": 10}}
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

## Links

- Working method and hard rules: [`AGENTS.md`](AGENTS.md)
- Evidence pack: [`evidence/`](evidence/)
- Component status: [`docs/components.md`](docs/components.md)

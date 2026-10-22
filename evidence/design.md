# Design

## Architecture overview

A small Python package in four components, each a folder (subpackage) with one job. The important logic is ordinary functions, tested without the web layer. FastAPI is a thin, read-only layer on top.

```
src/geo_risk_service/
  contracts/   models.py config.py schema.py        shared shapes, config loading, result tables
  generator/   synthetic.py                         seeded synthetic logins, IP table, hidden truth
  assessment/  ingest.py geo.py enrichment.py       load safely, point-in-time evidence,
               policy.py                            flag / clear / abstain
  service/     run.py evaluation.py api.py          run and log, score against truth, serve
```

## Data flow

1. **Generate** (`make demo`): seed 42 gives `logins.csv`, `ip_locations.csv` and a separate `truth.csv`.
2. **Ingest:** each login row is validated. Bad rows are rejected and counted; broken reference data stops the run.
3. **Enrich:** each customer's logins are taken in time order. Each login is located using the IP mapping **in force at its own time** (INV-6), and paired with the customer's last usable earlier login.
4. **Decide:** the speed-range rule (decision D1) gives flag, clear or abstain, with a reason, the evidence and the policy version.
5. **Store:** all results are written to DuckDB in one transaction, with a run summary and one JSON log line.
6. **Evaluate:** only now is `truth.csv` read, to score the stored decisions and write `evaluation.json`.
7. **Serve** (`make serve`): the read-only API gives `/health` and `/assessments/{login_id}`.

## Component boundaries

| Component | Owns | Never touches |
|---|---|---|
| contracts | data models, config validation, table definitions | decision logic |
| generator | synthetic data and truth | the policy (planted truth must not be shaped by the rule it tests) |
| assessment | ingest, distance, point-in-time lookup, the decision rule | truth (checked by a structural test) |
| service | orchestration, logging, evaluation, the API | truth outside `evaluation.py`; the API opens the database read-only |

## Key trade-offs

- **Speed range, not a single speed:** this costs some abstains, but no clear rests on imprecise evidence (D1).
- **Abstain on VPNs:** analysts aren't flooded with false alarms, and attackers aren't waved through. The cost is a gap, to be filled by other signals (D2).
- **Stop on broken reference data:** a run may fail loudly, but it never produces a misleading quiet result (D3).
- **Batch:** simple and deterministic now; the per-login function is ready for a stream (D4).
- **Hand-written fixtures for known answers:** more setup, but expected answers never come from the code under test.
- **One lead session, components in order:** less parallelism, no merge overhead, and one consistent set of contracts.

## Security and privacy

- **Synthetic only (INV-1):** invented customers, public city coordinates, and IPs only from the ranges reserved for documentation, so no address can belong to a real host.
- **No network calls or credentials (INV-2):** the API listens on 127.0.0.1 only, and no secrets are needed.
- **Truth isolation (INV-5):** truth sits in its own file. Only evaluation reads it, and tests fail if assessment or the API ever reference it.
- **Least privilege:** the API opens the database read-only, tested with the file read-only on disk, so it cannot change any decision. The only query that takes request input passes it as a bound parameter, so the input can never change the query itself (the defence against SQL injection).
- **Explainability:** every decision carries its reason, evidence and policy version, ready for audit.

## Technology choices

- **Python 3.12** (pinned), managed with **uv**. A lock file pins every dependency version, and every run checks it (`--locked`), so builds are repeatable.
- **Pydantic** for the data models, so input validation and rejection reasons come from one place.
- **DuckDB:** an embedded analytical database. Nothing to install or run, it supports transactions, and it handles a bulk load in well under a second.
- **FastAPI** with **Uvicorn** for a small, documented API (interactive docs at `/docs`).
- **pytest** and **ruff**, wrapped in `make verify`, the same check locally, before every agent commit and in CI.

## Likely production and cloud shape

- **Ingestion:** logins arrive on an event stream. A consumer calls the same per-login assessment function and keeps each customer's last usable location in a state store, with a stated rule for late events.
- **Storage:** DuckDB is replaced by a managed relational store for decisions and run state, and a warehouse for analysis and evaluation. Truth labels sit in a separate store that the assessment service has no access to (INV-5).
- **IP data:** a licensed IP geolocation feed, loaded as time-versioned reference data with the same validity rules as the synthetic table.
- **API:** behind the enterprise gateway, with identity from enterprise single sign-on and access checked by role.
- **Policy:** versioned config, promoted through the same pipeline as code, so every decision can be traced to the rule that made it.
- **Next signals:** card-present merchant and ATM data to tell a VPN user from an attacker, then harder evaluation scenarios (attackers on VPNs, coarse IPs, nearby attackers) to measure the method's limits.

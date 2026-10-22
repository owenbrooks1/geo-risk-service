# Plan: service (evaluation, run, API, logging, demo)

## Context

Contracts, generator and assessment are done (`cb2e94a`). Service joins them into the end-to-end workflow a reviewer can run:
- **generate** with the seed;
- **process**: load, assess and store in DuckDB, without ever seeing truth;
- **evaluate** against truth;
- **serve** the results through a read-only API.

It owns AC-13 to AC-18. Once it's done, every CORE criterion is built. AC-19 to AC-22 (ENHANCE) are only built if time allows, in cut order.

## Paths
- **Touch:**
  - `src/geo_risk_service/service/{evaluation,run,api}.py`;
  - `tests/test_{evaluation,run,api}.py`;
  - the `Makefile` (`demo` and `serve` targets);
  - the README run section, with a real example request and response.
- **Do not touch:** contracts, generator, assessment, `config/`, `examples/`.

## Design

**`evaluation.py`** (AC-13, AC-14):
- `evaluate(assessments, truth) -> EvaluationReport`, joined on `login_id`. It reports:
  - counts of flag, clear and abstain;
  - **precision**: suspicious logins flagged, out of all flagged;
  - **recall**: suspicious logins flagged, out of *all* suspicious logins, so an abstain counts as a miss;
  - recall among decided logins only, labelled as secondary;
  - **false clears**: suspicious logins that were cleared;
  - the **abstain rate**, abstains by reason, and suspicious logins abstained.
- `load_truth(path)` exists only here (INV-5).

**`run.py`** (AC-17, AC-18): plain functions, plus `python -m geo_risk_service.service.run`.
- `process(data_dir, db_path, policy, seed) -> RunSummary`:
  - loads `logins.csv` and `ip_locations.csv` using assessment's loaders, so the overlap check runs;
  - calls `assess`;
  - replaces the `assessments` and `run_summary` tables in DuckDB;
  - **never receives a truth path** (INV-5).
- `evaluate_run(data_dir, db_path) -> EvaluationReport`: reads `truth.csv` and the stored decisions, and writes `evaluation.json` to `data_dir`.
- `run_demo(settings_path, policy_path)`: loads config, generates with the seed, processes, evaluates, logs and prints the report.
- **Logging:** standard library `logging`. One summary line per run with the seed, policy version, loaded, rejected by reason and decisions by outcome. A stopped run logs its cause (Q-S4 sets the format).

**`api.py`** (AC-15, AC-16): FastAPI, read-only. `create_app(db_path)`, so tests can point it at a temporary database. `app` is built from `config/settings.yaml` for `make serve`.
- `GET /health`:
  - **ready:** policy version, seed, and loaded, rejected and decision counts from `run_summary`;
  - **not ready:** the reason, for example "no results database at data/results.duckdb; run make demo" (Q-S1 sets the status code).
- `GET /assessments/{login_id}`: the stored assessment with its evidence and policy version, or 404 if the ID is unknown.
- Each request opens DuckDB **read-only**, so the API can never change results.

**`Makefile`:**
- `demo`: `uv run python -m geo_risk_service.service.run`;
- `serve`: `uv run uvicorn geo_risk_service.service.api:app` (localhost:8000).

## Tests first, with known answers
- **AC-13** (`examples/evaluation/`): precision 0.5, recall 0.5, recall among decided 1.0, false clears 0, abstain rate 1/6, suspicious abstained 1, and counts of 2 flag, 3 clear and 1 abstain.
- **AC-14:** the full demo run with seed 42 into a temporary folder gives false clears = 0.
- **Q-S3:** with nothing flagged, precision is reported as "not defined", not 0.
- **AC-17:**
  - the run's log has exactly one summary line containing seed 42, policy `v1`, the loaded count, rejected by reason and decisions by outcome;
  - a run with the IP table deleted logs the path and stops with `InputDataError`;
  - a bad policy logs and stops with `ConfigError`.
- **INV-5:** `process` works with `truth.csv` deleted; `evaluate_run` then fails with a clear error naming `truth.csv`.
- **AC-15:**
  - with no database: not ready, and the reason names the path;
  - after a run: ready, policy `v1`, seed 42, and counts that match the run summary.
- **AC-16:**
  - fixture-based: process `examples/assess` into a temporary database. `GET /assessments/L-0202` returns flag, `impossible_travel`, a speed range of 16,943.9 to 17,043.9, baseline `L-0201` and policy `v1`;
  - `GET /assessments/NOPE` returns 404.

## Hard rules at risk
- **INV-5:** `process` and the API never receive the truth path, and only `evaluation.py` reads truth. The structural test is extended to `run.process` and `api`.
- **INV-4:** times are returned as UTC with `Z`.
- **INV-2:** the API listens on localhost only.
- **INV-7:** AC-14.

## Not built here (ENHANCE, if time allows)
AC-19 (list filters), AC-20 (`GET /evaluation`), AC-21 (order independence), AC-22 (`POST /assess`).

## Decisions from the grill
- **Q-S1:**
  - `/health` returns **503** with `{status: not_ready, reason}` when there are no results. Load balancers and readiness checks read the status code, so they won't send traffic to an instance with nothing to serve.
  - Ready returns 200.
- **Q-S2:**
  - Logins rejected at load have truth but no assessment. They're **reported separately**, as "not assessed: N, of which suspicious: M".
  - Precision and recall cover assessed logins only.
  - Test: a truth row with no matching assessment gives not assessed 1, and the other metrics are unchanged.
- **Q-S3:** a metric with nothing to divide by is **null** ("not defined"), never 0 or 1.
- **Q-S4:**
  - Run logs are **JSON lines**, one object per entry: `event`, `seed`, `policy_version`, `loaded`, `rejected_by_reason` and `decisions_by_outcome`. A stopped run logs `event: run_stopped`, `error` and `cause`.
  - The human-readable evaluation report is printed separately.

## Changes during the stage
- The bulk load of assessments uses a temporary CSV with `COPY`. Row-by-row inserts took 79 seconds for the full demo.
- **Owner-raised issues, all fixed:**
  - results are replaced in one transaction;
  - a damaged, empty or locked database gives 503;
  - `run_at` ends in Z;
  - decisions with no truth row are counted as `no_truth`;
  - any failure logs `run_stopped`.
- **Reviewer findings, all fixed:**
  - the docstring now states that only recall is protected from abstaining;
  - `COPY` names its columns;
  - quotes in the staging path are escaped;
  - the API's truth test is stronger;
  - a test checks read-only access;
  - stored decisions are read in login ID order.
- The service code was committed (`c071a56`) before close-stage, so the owner could test it by hand.
- **Owner review, items 6 to 9 (decided 2026-10-22):**
  - `run_at` is UTC in whole seconds, created once per run. The same `YYYY-MM-DDTHH:MM:SSZ` string appears in the `run_complete` log line, the `run_summary` row, `evaluation.json` and `/health`, so they can be linked;
  - `evaluation.json` starts with a `run` block: seed, policy version and `run_at`;
  - `run_summary` keeps one row per successful run, as an audit history. Only the latest run's assessments are kept, and `/health` reports the newest row;
  - the seed is the configured seed, recorded as given and not checked against the data (fixture runs record 0). Documented in `operate.md`, not fixed.
- **Run linkage review (accepted by owner):**
  - `run_at` was not unique, so "newest run" could be ambiguous. Owner decision: a run whose `run_at` is not later than the newest stored one is refused with `RunOrderError`, logged, and the previous results stay. Chosen over a `run_id` column, which would change the contracts;
  - added a test that `evaluation.json` names the newest of several runs; fixed the `process` docstring; new tests cite AC-15 or AC-17; `evaluate_run` converts the stored time with `from_db_time`, as the API does. The API's copy of the format string stays, so the API does not import processing code.
- **Suggestions, not built:** have the generator write a manifest with its seed, so processing records the seed that actually produced the data; store `run_at` on assessment rows, so each decision links to its run; in production, an increasing run ID as the link instead of a timestamp.

## Record on approval
- Save as `docs/plans/service-end-to-end.md`.
- Mark the service "in progress" on `main`.

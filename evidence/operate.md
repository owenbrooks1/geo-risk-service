# Operate

To be completed.

## How to run

- `uv sync`, then `make demo` (generate, assess, evaluate, print the report), then `make serve` (API on 127.0.0.1:8000). Run from the repository root.

## Logs and status

- One JSON line per event on stderr: `run_complete` (seed, policy version, loaded, rejected by reason, decisions by outcome) or `run_stopped` (error, cause).
- `GET /health`: 200 with the latest run's details, or 503 with the reason (no database, no completed run, or database not readable).

## Configuration and secrets

- `config/policy.yaml`: decision rules (`version`, `max_speed_kmh`); every assessment records the version.
- `config/settings.yaml`: seed, sizes and paths; logged in the run summary.
- No secrets are needed; the slice uses synthetic local data only.

## Failure modes

| Failure | Behaviour | Criterion |
|---|---|---|
| Config file missing or invalid | Run stops with `ConfigError` naming the file and every problem | AC-11 |
| Bad login row (missing value, invalid IP, no timezone, bad time, duplicate ID) | Row rejected with line, ID and reason; the rest carry on | AC-09 |
| Logins file missing, or header missing or wrong | Run stops with `InputDataError` | AC-11 |
| IP table missing, empty, invalid, or one IP with two mappings in force at once | Run stops with `InputDataError` naming the file, line or IP | AC-11 |
| Results write fails part-way | Transaction rolls back; previous run's results stay and keep being served; `run_stopped` logged | AC-15, AC-17 |
| Any other failure during a run | `run_stopped` logged with error and cause; `make demo` exits 1 | AC-17 |
| Results database missing, empty, damaged or locked | API returns 503 with the reason, never a server error | AC-15 |
| `truth.csv` missing at evaluation | Processing still completes; evaluation stops with `InputDataError`, logged | INV-5, AC-17 |

## Rollback and degrade

- A failed run leaves the previous results in place and served (results are replaced in one transaction). A stale but complete result is served rather than a partial one.

## Local to cloud

- **Pull request:** CI runs `make verify` on every push. In production this gates merges to the protected main branch.
- **Merge:** build a container image tagged with the commit ID and publish it to a private registry. Deploy to a test environment, run the demo as a smoke test, then promote to production with an approval step.
- **Config and secrets:** locally, settings come from `config/settings.yaml` and policy from `config/policy.yaml`. In production, environment-specific values override the settings file. Secrets come from a managed secrets service and are never stored in the repository.
- **Access control:** the local API has no authentication. In production it sits behind the enterprise gateway, with identity from single sign-on and access checked by role.
- **Logs and audit:** run logs go to central monitoring. Decision records go to durable storage that cannot be edited after it is written.
- **Rollback:** redeploy the previous image with its pinned policy version. Database changes are forward-only and backward-compatible.

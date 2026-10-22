# Operate

How to run, monitor and recover the service, and how it would move to the cloud.

## How to run

- From the repository root: `uv sync`, then `make demo` (generate data, assess every login, evaluate, print the report), then `make serve` (API on 127.0.0.1:8000).
- Rerunning `make demo` is safe. It regenerates the same seeded data, replaces the stored decisions in one transaction and adds a new run record.

## Logs and status

- Each run writes one JSON line to standard error: `run_complete` (run time, seed, policy version, rows loaded, rejected rows by reason, decisions by outcome) or `run_stopped` (the error and its cause).
- `run_at`, the run's start time in UTC to the second, links that log line to the run's database record, `evaluation.json` and `/health`. Every successful run is kept in `run_summary`; only the latest run's decisions are kept.
- `GET /health` returns 200 with the latest run's details, or 503 with the reason (no database, no completed run, or database unreadable).

## Configuration and secrets

- `config/policy.yaml`: the decision rule (`version`, `max_speed_kmh`). Every decision records the version.
- `config/settings.yaml`: seed, sizes and paths. The logged seed is the configured one; it is not checked against the data on disk.
- No secrets are needed: the slice uses synthetic local data only.

## Failure modes

| Failure | What the service does | What to do | Criterion |
|---|---|---|---|
| Config file missing or invalid | Run stops; `ConfigError` names the file and every problem | Fix the file named and rerun | AC-11 |
| Bad login row (missing value, invalid IP, time with no UTC offset, unreadable time, duplicate ID) | Row rejected; the rest are assessed; counts by reason are logged | Check `rejected_by_reason`; investigate the source if it is unexpected | AC-09 |
| Logins file missing, or header missing or wrong | Run stops with `InputDataError` | Restore the file or fix its header, then rerun | AC-11 |
| IP table missing, empty, invalid, or one IP with two mappings in force at once | Run stops; `InputDataError` names the file, line or IP | Fix the reference data. Running without it would make every login abstain, which looks like a quiet day | AC-11 |
| Results write fails part-way | Write undone; previous results kept and served; `run_stopped` logged | Check disk space and the database file, then rerun | AC-15, AC-17 |
| Run time not later than the newest stored run (two runs in one second, or the clock moved back) | Run refused with `RunOrderError`; previous results kept; logged | Check the machine clock; rerun once it is past the newest run | AC-17 |
| Any other failure during a run | `run_stopped` logged with error and cause; `make demo` exits with code 1 | Read the cause in the log | AC-17 |
| Results database missing, empty, damaged or locked | API returns 503 with the reason, never a server error | Run `make demo`, or wait for a running one to finish | AC-15 |
| `truth.csv` missing at evaluation | Decisions are still stored; evaluation stops with `InputDataError`, logged | Regenerate the data. Decisions do not depend on truth (INV-5) | INV-5, AC-17 |

## Degrade and rollback

- **Weak evidence degrades to abstain,** never to a reassuring clear (INV-7). Each abstain carries its reason, so other controls can pick it up.
- **A failed run leaves the previous complete results in place and served.** A stale but complete result is preferred to a partial one.

## Local to cloud

- **Pull request:** CI runs `make verify` on every push. In production this gates merges to the protected main branch.
- **Merge:** build a container image tagged with the commit ID and publish it to a private registry. Deploy to a test environment, run the demo as a smoke test, then promote to production with an approval step.
- **Config and secrets:** locally, settings come from `config/settings.yaml` and policy from `config/policy.yaml`. In production, environment-specific values override the settings file. Secrets come from a managed secrets service and are never stored in the repository.
- **Access control:** the local API has no authentication. In production it sits behind the enterprise gateway, with identity from single sign-on and access checked by role.
- **Logs and audit:** run logs go to central monitoring, with an alert on `run_stopped`. Decision records go to durable storage that cannot be edited after it is written.
- **Rollback:** redeploy the previous image with its pinned policy version. Database changes are forward-only and backward-compatible.

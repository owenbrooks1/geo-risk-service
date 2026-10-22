# Operate

To be completed.

## How to run

## Logs and status

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

## Rollback and degrade

## Local to cloud

- **Pull request:** CI runs `make verify` on every push. In production this gates merges to the protected main branch.
- **Merge:** build a container image tagged with the commit ID and publish it to a private registry. Deploy to a test environment, run the demo as a smoke test, then promote to production with an approval step.
- **Config and secrets:** locally, settings come from `config/settings.yaml` and policy from `config/policy.yaml`. In production, environment-specific values override the settings file. Secrets come from a managed secrets service and are never stored in the repository.
- **Access control:** the local API has no authentication. In production it sits behind the enterprise gateway, with identity from single sign-on and access checked by role.
- **Logs and audit:** run logs go to central monitoring. Decision records go to durable storage that cannot be edited after it is written.
- **Rollback:** redeploy the previous image with its pinned policy version. Database changes are forward-only and backward-compatible.

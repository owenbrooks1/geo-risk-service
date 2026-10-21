# Components

Draft. Each row is confirmed or changed when its `/start` runs. A component session edits only its owned paths.

Status values: planned, in progress, ready to merge, merged.

| Component | Owned paths | Depends on | Branch | Status | Criteria |
|---|---|---|---|---|---|
| contracts | schema, data models, config | - | `main` | planned | - |
| generator | seeded synthetic data and hidden truth | contracts | - | planned | - |
| enrichment | point-in-time geospatial evidence | contracts | - | planned | - |
| policy | versioned decision rules, abstention | contracts | - | planned | - |
| evaluation | metrics against hidden truth | generator, policy | - | planned | - |
| api | FastAPI routes over domain functions | contracts, then each domain component | - | planned | - |
| ops | demo, logs, status, runbook | api | - | planned | - |

Exact paths are filled in when the contracts component sets the package layout.

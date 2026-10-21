# Components

Each row is confirmed or changed when its `/start` runs. A component session edits only its owned paths.

Status values: planned, in progress, ready to merge, merged.

| Component | Owned paths | Depends on | Branch | Status | Criteria |
|---|---|---|---|---|---|
| contracts | schema, data models, policy config, `examples/` fixtures | - | `main` | planned | shared by all |
| generator | seeded synthetic data and hidden truth | contracts | - | planned | AC-01 |
| assessment | enrichment (point-in-time IP evidence) and policy (decision rule, abstention), as separate modules | contracts | - | planned | AC-02 to AC-12 |
| service | evaluation, API, demo command, run logging | generator, assessment | - | planned | AC-13 to AC-18; ENHANCE AC-19 to AC-22 |

Exact paths are filled in when the contracts component sets the package layout.

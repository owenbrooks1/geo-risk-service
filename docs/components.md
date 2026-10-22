# Components

Each row is confirmed or changed when its `/start` runs. Each stage edits only its component's owned paths.

Status values: planned, in progress, done.

| Component | Owned paths | Depends on | Branch | Status | Criteria |
|---|---|---|---|---|---|
| contracts | `contracts/` (`models.py`, `config.py`, `schema.py`), `config/`, `examples/`, `tests/test_contracts.py`, `tests/conftest.py` | - | `main` | done | shared by all; config and model parts of AC-09, AC-11 |
| generator | `generator/` (`synthetic.py`), `tests/test_generator.py` | contracts | `main` | done | AC-01 |
| assessment | `assessment/` (`ingest.py`, `geo.py`, `enrichment.py`, `policy.py`), with matching `tests/test_*.py` | contracts | `main` | done | AC-02 to AC-12 |
| service | `service/` (`evaluation.py`, `run.py`, `api.py`), with matching tests; `Makefile` `demo` and `serve` targets; README run section | generator, assessment | `main` | done | AC-13 to AC-18; ENHANCE AC-19 to AC-22 |

Source paths are under `src/geo_risk_service/`, one subpackage per component (owner decision during assessment planning; modules moved before assessment code was written). Tests stay flat in `tests/`, one file per module. Generated data goes in `data/` (gitignored). A change to the contracts during a later stage is raised with the owner first.

## Build order and cut list

- **Order:** contracts, generator, assessment, service. Each is built one after another on `main` in the lead session, one stage per commit. No parallel worktrees: at this size the merge overhead costs more than it saves.
- **Hard stop at 2:30 elapsed:** no new features after this point. The remaining time is for the independent review, the evidence pack, the README and a clean-checkout run.
- **Cut order if behind** (first cut first): any STRETCH item, then AC-22, AC-21, AC-19, AC-20.
- **Never cut:** the end-to-end demo, abstention, truth isolation, the point-in-time IP check, guarded failures, the tests citing them, the evidence pack and incremental commits.

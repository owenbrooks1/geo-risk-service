# Verification

`make verify` is the single check. It runs the linter, the format and lock-file checks, then all 157 tests, which pass. It runs locally, automatically before every agent commit, and in CI on every push.

Two terms used below:

- **Known answer:** the expected result, worked out from the criteria, separately from the product code, before the code was written. A test then checks the code against it, rather than repeating what the code does.
- **Deliberate break (mutation check):** the code is broken on purpose, a test is shown to fail, and the change is reverted. This shows the test would catch that fault.

## Tests

| Area | Criteria and rules | What the tests show | Tests |
|---|---|---|---|
| Contracts (`test_contracts.py`) | AC-09, AC-11 (model and config parts), INV-1, INV-4, INV-6 | Config loads, or stops with an error naming the file and every problem. Login rows need a time with a UTC offset and a valid IP. IP mapping windows are well formed. Times stay UTC through the database whatever the machine's time zone. Fixtures use documentation-only IPs. | 20 |
| Generator (`test_generator.py`) | AC-01, INV-1, INV-3, INV-4, INV-5 | The same seed gives byte-identical files, checked against a checksum computed in a separate process; another seed differs. One truth label per login, kept out of the inputs. All four scenarios appear. On four seeds, using a distance formula written in the test, every planted jump is at least 3,000 km in 30 to 90 minutes, and every genuine non-VPN login is reachable at 1,000 km/h. | 21 |
| Assessment (`test_ingest.py`, `test_enrichment.py`, `test_policy.py`) | AC-02 to AC-12, INV-4 to INV-7 | All 20 hand-written fixture logins get the expected decision, reason and speed range. Threshold boundaries. Each login uses the IP mapping in force at its own time (start inclusive, end exclusive). Bad rows are rejected with line, ID and reason; broken reference data stops the run. No assessment code uses truth. | 53 |
| Service (`test_evaluation.py`, `test_run.py`, `test_api.py`) | AC-13 to AC-18, INV-4, INV-5, INV-7 | Exact AC-13 metrics, including by planted scenario. Seed 42 gives 0 false clears. One JSON log line per run; every failure logs its cause. A failed write keeps the previous results. Each run is linked by its `run_at` time across the log, the database, `evaluation.json` and `/health`; an out-of-order run is refused. `/health` returns 503 with a reason when not ready; `/assessments` returns the stored decision, or 404. The API works with the database read-only. Processing and the API never touch truth. | 37 |
| Commit gate (`test_commit_gate.py`) | Commit rules in `AGENTS.md` | Each message rule rejects a message that breaks it; message forms the gate cannot read are blocked. | 25 |
| Package (`test_package.py`) | none | The tooling runs against the installed package. | 1 |

## Deliberate breaks

Each was actually run, made the named test fail, and was reverted with `make verify` green again.

| Rule | Break | Result |
|---|---|---|
| INV-4 UTC times | Stored run time switched to a type that follows the machine's time zone (`TIMESTAMPTZ`) | Round-trip test failed |
| INV-5 truth isolation | `suspicious` column added to `logins.csv` | Truth-not-in-inputs test failed |
| INV-5 | `Truth` imported into the decision rule, two different ways | Structural test failed each time |
| INV-5 | Processing made to read `truth.csv` | 2 tests failed |
| INV-6 time cut-off | Mapping end made inclusive (`<` changed to `<=`) | 2 tests failed |
| INV-7 abstention | Clear decided on the minimum speed instead of the maximum | Fixture `L-0402` failed |
| AC-08 ordering | Sort by time and login ID removed | Ordering test failed |
| AC-13 recall | Recall counted over decided logins only | Test failed (1.0 instead of 0.5) |
| AC-15, AC-16 read-only API | Read-only database flag removed | Read-only test failed |
| AC-15, AC-17 all-or-nothing write | Transaction removed | Rollback test failed |
| AC-17 run order | Order check disabled | Both refusal tests failed |

The tooling was broken on purpose too: an unused import made the commit gate block the commit, and an unlisted dependency made the lock check fail.

## Independent reviews

A separate read-only reviewer checked each stage containing logic against INV-1 to INV-8. The owner accepted or rejected each finding.

- **Generator:** no rule breaches. Six test weaknesses found and fixed, for example a reachability test that could pass on home logins alone.
- **Assessment:** no high-severity findings. Four test gaps fixed; one finding rejected after checking. Owner decisions: a wrong header stops the run, the first valid row wins for duplicates, and times are parsed strictly.
- **Service:** no rule breaches. The owner also put nine issues to the build, chosen from a separate review session's list, including unlogged failures, a write that was not all-or-nothing, a server error instead of 503, decisions without truth scored as genuine, and runs that could not be linked for audit. Eight were fixed and tested; the seed limitation is documented.

## Other checks

- **Lint and format (`ruff`):** no undefined names, unused imports or common bug patterns; one consistent format.
- **Lock check (`--locked`):** dependencies must match the lock file, so nothing is added without approval.
- **Commit gate:** blocks an agent commit if its message breaks the conventions or `make verify` fails.
- **CI:** the same `make verify` on a clean machine, from the lock file. It has passed on every push (latest checked: `c00cfaa`).
- **By hand:** `make demo` gave 4,480 logins, 10 flags, 4,340 clears, 130 abstains and 0 false clears. The API answered `/health`, a flagged login and a 404.

## Known gaps

**Limits on what the results show**

- AC-14 (no false clears) holds by construction on generated data: every generated login is clearly possible, clearly impossible, or VPN. The "inconclusive" path is tested only with hand-written fixtures (AC-04).
- The generator spaces genuine travel for 1,000 km/h, the same as policy v1. It deliberately does not read the policy, so a lower threshold could make some genuine trips abstain.
- The runtime truth-isolation test (AC-12) passes by construction, because assessment is never given truth. The structural test, which fails if assessment code refers to truth, is the main control.
- Truth is kept apart by code and tests, not by file permissions: `truth.csv` sits in the folder that processing reads.

**Process controls**

- The commit gate covers only commits made by the agent; the owner's own commits rely on CI. It recognises commit commands by pattern, so an unusual form could slip past, and its imperative-mood check catches common forms only.

**Minor**

- A run keeps rejected-row counts by reason, not each row's line and ID.
- A bad login row reports only its first problem. A row with more values than the header is not tested.
- Identical output for the same seed is promised on Python 3.12 only (pinned).
- The newest-run tests insert an older run first, so they would very likely, though not certainly, catch a missing sort.
- `make serve` must run from the repository root.
- The test client prints a deprecation warning; fixing it needs a new dependency, so it was left.

## Local, pull request and pipeline

- **Local:** `make verify` on demand, and automatically before each agent commit.
- **Push and pull request:** CI runs `uv sync --locked` then `make verify`.
- **Pipeline:** none deployed. In production this check would gate merges to the protected main branch, followed by the promotion steps in `operate.md`.

# Verification

`make verify` is the single check. It runs locally, before every agent commit and in CI.

## Checks and what each proves

| Check | Criteria or rule | What it proves | Result |
|---|---|---|---|
| `ruff check` (lint) | Engineering rules | Code has no undefined names, unused imports or common bug patterns, and imports are ordered. | Green |
| `ruff format --check` | Engineering rules | Code follows one consistent format, so diffs show only real changes. | Green |
| `--locked` on every `uv run` | No new dependencies without approval | `uv.lock` matches `pyproject.toml`. A dependency added without updating the lock fails the check. Shown by adding an unlisted package: verify failed, then passed after revert. | Green |
| `tests/test_package.py::test_package_imports` | Harness only | `make verify` runs real tests against the installed package. It does not cover any AC or INV rule. | Green |
| Commit gate (`.claude/hooks/verify_before_commit.py`) | Stage done only when verify passes | An agent `git commit` is blocked when its message breaks the conventions or verify fails. Shown by adding an unused import: the hook exited 2 with the lint failure; after revert it exited 0. Non-commit commands pass without running verify. | Green |
| `tests/test_commit_gate.py` (25 known-answer cases) | Commit conventions in `AGENTS.md` | Good messages pass. Each convention rejects a message that breaks it: multi-line, over 72 characters, emoji, attribution, full stop, lower-case start, too vague, not imperative. The message is read correctly from the supported command forms; message files, heredocs and multiple `-m` are blocked; non-commit commands are ignored. | Green |
| `tests/test_contracts.py` (19 tests) | AC-09 and AC-11 (model and config parts), INV-1, INV-4, INV-6 contract | Config loads, or stops with an error naming the file and every problem. Login rows need an offset time and a real IP; offsets convert to UTC. IP mapping windows are well formed. Results table matches the `Assessment` model. Times round-trip through DuckDB as UTC whatever the local zone. Fixtures parse, cover AC-02 to AC-08, and use documentation-only IPs. It does not prove any decision is correct; that is the assessment stage. | Green |
| Mutation: time storage (INV-4) | INV-4 | Switching `run_summary.run_at` back to `TIMESTAMPTZ` made the round-trip test fail with a missing `pytz` error; reverted, verify green. | Done |
| `tests/test_generator.py` | AC-01, INV-1, INV-3, INV-4, INV-5 | Same seed gives byte-identical files and a recorded checksum computed in a separate process; another seed differs. One truth label per login; only planted jumps are suspicious. All four scenarios appear from 4 customers. Every IP is a documentation address; times are UTC. No truth in the inputs. On four seeds, using a distance formula written in the test: every jump is at least 3,000 km in 30 to 90 minutes, and every genuine non-VPN login, including travel and the login after a jump, is reachable at 1,000 km/h with both radii added. | Green |
| Mutation: truth leak (INV-5) | INV-5 | Adding `suspicious` to `logins.csv` made `test_inv5_truth_is_not_in_the_inputs` fail; reverted, verify green. | Done |
| Independent review: generator | INV-1 to INV-8 | No rule breaches. Six test and robustness weaknesses found and fixed: label check, per-scenario check counts, cross-process checksum and Python pin, one-day fallback spacing, docstring overclaim, UTC check on IP times. | Done |
| `tests/test_ingest.py`, `test_enrichment.py`, `test_policy.py` (53 tests) | AC-02 to AC-12, INV-4 to INV-7 | All 20 fixture logins get the expected decision, reason and speed range (AC-02 to AC-08). Threshold boundaries. Flagged logins still become baselines (Q-A1); own-IP reasons first (Q-A2). Logins sorted by time, ties by login ID. Mapping in force from start (inclusive) to end (exclusive), checked on a lone mapping. Bad rows rejected with exact line, ID and reason; unparseable and number-only times rejected. Missing file, missing or wrong header, empty, invalid or overlapping IP table stop the run. No assessment module uses `Truth`, imports the service or names truth outside docstrings. | Green |
| Mutation: INV-6 cut-off | INV-6 | `at < valid_to` changed to `<=`: 2 tests failed (12:00 lookup, `L-0722`); reverted, verify green. | Done |
| Mutation: INV-7 abstain | INV-7 | Clearing on minimum speed instead of maximum: `L-0402` failed; reverted, verify green. | Done |
| Mutation: INV-5 isolation | INV-5 | `Truth` imported into `policy.py`, and separately `models.Truth` used: the structural test failed for `policy` each time; reverted, verify green. | Done |
| Mutation: time order | Q5 g, AC-08 | Removing the sort by (time, login ID): the ordering test failed; reverted, verify green. | Done |
| Independent review: assessment | INV-1 to INV-8 | No high-severity findings. Accepted and fixed: untested sort and tie-break, narrow truth-isolation test, file-order-dependent boundary test, untested open-ended overlap. Owner decisions: wrong header stops the run; first valid row wins for duplicates; times parsed strictly as ISO-8601 (number-only times were accepted before). One finding rejected (import order: checked, passing). | Done |
| CI (`.github/workflows/verify.yml`) | Same check off the developer machine | The pushed code passes `make verify` on a clean machine from the lock file. First run on `a934734`: lint, format and 26 tests passed. | Green |

## Known gaps

- The import test proves only that the tooling runs. Product behaviour is not yet tested; AC tests arrive with each component.
- The commit gate covers commits made by the agent only. Commits the owner makes in their own terminal are not gated; CI is the backstop.
- The imperative-mood check only catches common past and present forms ("Added", "Adding"); it cannot prove a verb is imperative.
- The gate matches `git ... commit` by pattern. An unusual command form could slip past it; CI still catches the failure after push.

- AC-14 is met by construction on generated data: every generated login is clearly a flag, clearly a clear, or VPN, so the `inconclusive` path is never reached there. That path is covered by the hand-written fixtures (AC-04), not by generated data.
- The generator spaces genuine logins for 1,000 km/h, the same figure as policy v1. It deliberately does not read the policy. A lower threshold could make some genuine trips abstain.
- Byte-identical generated output is promised on Python 3.12 only (`.python-version`); Python does not promise identical random sequences across versions.
- Trips near the end of the period can run a few days past the 30-day window. Harmless; nothing assumes the window.

- AC-12's runtime test is true by construction: assessment is never given a truth path. The structural test is the main INV-5 control.
- A bad login row reports only its first problem.
- The IP overlap check runs when the table is loaded; the service must pass `load_ip_locations` output to `assess`.
- A login row with more values than the header is not tested.

## Local versus pull request versus pipeline

- **Local:** `make verify` on demand, and automatically before each agent commit.
- **Pull request and push:** CI runs `uv sync --locked` then `make verify` on every push and pull request.
- **Pipeline:** no deployment pipeline. In production this check would gate merges to the protected main branch.

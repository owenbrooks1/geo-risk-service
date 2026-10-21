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
| CI (`.github/workflows/verify.yml`) | Same check off the developer machine | The pushed code passes `make verify` on a clean machine from the lock file. First run on `a934734`: lint, format and 26 tests passed. | Green |

## Known gaps

- The import test proves only that the tooling runs. Product behaviour is not yet tested; AC tests arrive with each component.
- The commit gate covers commits made by the agent only. Commits the owner makes in their own terminal are not gated; CI is the backstop.
- The imperative-mood check only catches common past and present forms ("Added", "Adding"); it cannot prove a verb is imperative.
- The gate matches `git ... commit` by pattern. An unusual command form could slip past it; CI still catches the failure after push.

## Local versus pull request versus pipeline

- **Local:** `make verify` on demand, and automatically before each agent commit.
- **Pull request and push:** CI runs `uv sync --locked` then `make verify` on every push and pull request.
- **Pipeline:** no deployment pipeline. In production this check would gate merges to the protected main branch.

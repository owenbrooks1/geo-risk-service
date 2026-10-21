# Plan: Commit 1, working method

## Context

The repository is empty apart from `.gitignore`, `pyproject.toml` and `uv.lock`. Before any product code, we commit the working method: the rules every agent session follows, the workflow skills, an independent reviewer, the component status table and evidence stubs. The history then shows that the method came before the implementation.

This commit is documents and settings only. Verification tooling (`make verify`, CI, the commit-gate hook) is commit 2. Acceptance criteria are commit 3.

Writing rules for every file in this commit:
- Plain terms for a mixed review audience, UK spelling, no emojis.
- Self-contained: no references to anything outside the committed repo.

## Files

### 1. `AGENTS.md` (the only instruction file; no `CLAUDE.md`)

Short sections:
1. **Purpose:** a small, locally runnable geospatial risk intelligence service (Python, DuckDB, FastAPI), built as a thin, credible vertical slice for a regulated enterprise.
2. **Roles:** the owner holds product intent, data meaning, risk decisions, acceptance criteria and final judgement. The agent implements, explains, and raises risks and simpler options.
3. **Hard rules (INV-1 to INV-8):**
   - INV-1: synthetic data only.
   - INV-2: no network calls or external credentials.
   - INV-3: deterministic, seeded generation.
   - INV-4: UTC and kilometres only.
   - INV-5: enrichment and policy never read synthetic truth.
   - INV-6: no future physical or IP evidence enters enrichment.
   - INV-7: weak or unreliable evidence abstains rather than reassures.
   - INV-8: material behaviour has a test.

   This file is the single source for these rules, and tests and reviews cite these IDs.
4. **Engineering rules:**
   - FastAPI is a thin adapter over ordinary Python functions.
   - No dependency injection, custom middleware, repository or service layers, or async without a stated requirement.
   - No new dependencies without approval.
   - No scope expansion.
5. **Scope bands:**
   - CORE: the assessed workflow.
   - ENHANCE: only once the CORE behaviour it depends on is green.
   - STRETCH: only when the owner says we are ahead.
6. **Stage loop:**
   1. `/start`
   2. plan approval
   3. tests first, from the owner's known answers
   4. build
   5. `/defend`
   6. `/close-stage`
   7. owner evidence review and commit approval
   8. `/integrate`
7. **Staying on track:**
   - Every reply at a stage boundary ends with the suggested next step.
   - If the owner skips a step, say so once.
   - Flag harness problems as proposed changes.
   - "OWNER DECISION NEEDED": on questions of data meaning or risk, stop, give options and a recommendation, then record the answer in `evidence/decisions.md`.
8. **Changing documents:**
   - Harness changes (`AGENTS.md`, `.claude/`) need owner approval and are made only in the lead session on `main`.
   - Other docs (evidence, plans, status) are updated as we go, with a one-line note.
9. **Parallel sessions:**
   - One session per component, started with `claude -w <component>`.
   - The lead session stays on `main`.
   - Shared contracts are built on `main` before work splits.
   - Each component edits only its own paths.
10. **Where things live:** a table of rules, plans (`docs/plans/`), status (`docs/components.md`), criteria (`evidence/intent.md`), decisions and evidence.
11. **Verification:**
    - `make verify` is the single check (arrives in commit 2).
    - Tests name the AC or INV ID they check.
    - High-risk logic gets a mutation check: break it on purpose, show the test fails, then revert.
12. **Commits:**
    - One short line, no attribution or co-author lines.
    - Commit only with owner approval.
    - Never squash or rewrite history.
13. **Checkpoints:** the owner gives elapsed time, check status and obligations. The agent returns a ranked table (action, band, depends on, assessment value, risk to working code). No time estimates.

### 2. `.claude/settings.json`

- `"plansDirectory": "docs/plans"`
- Allow: `make verify`, `uv run pytest`, `uv run ruff`, `git diff`, `git log`.
- Ask: `uv add`/`uv remove`/`pip install`, `curl`/`wget`, WebFetch/WebSearch, `git commit`/`git push`/`git merge`.
- No hooks yet (commit 2).

### 3. Skills: `.claude/skills/<name>/SKILL.md`

| Skill | Invoked by | Steps |
|---|---|---|
| `start` | owner only | Confirm worktree and branch. Read `AGENTS.md` and the status table, and stop if dependencies are not merged. Enter plan mode. Draft this component's criteria and known answers. Call `grill`. Save the approved plan to `docs/plans/<component>-<topic>.md`. Mark the component in progress. |
| `grill` | owner or agent | One question at a time, each tied to an INV or AC ID, with a recommended answer. State each engineering concept in plain terms when first relied on, and name the risk it controls. Record outcomes in `intent.md` and `decisions.md`. |
| `defend` | owner or agent | For the diff: what each meaningful part does, why it is here, what happens when it fails, how it is tested, and what changes in production. Flag anything hard to justify and propose simplifications. |
| `close-stage` | owner only | Run `make verify`. Run `guardrail-reviewer` if the generator, enrichment, policy or evaluation code changed. Run a mutation check on high-risk logic. Run `defend`. Draft evidence updates. Propose a one-line commit message. Stop for the owner's evidence review and commit approval. |
| `integrate` | owner only | Lead session: merge the component branch into `main` without squashing. Run `make verify` on `main`. Update the status table. Suggest the next component. |
| `checkpoint` | owner only | Read the status table, criteria status and the last verify result, then return the ranked table. |

`disable-model-invocation: true` on the four owner-only skills.

### 4. `.claude/agents/guardrail-reviewer.md`

- Read-only tools (Read, Grep, Glob, Bash for `git diff`/`git log`).
- Fresh context, and it does not edit.
- Checks a diff against INV-1 to INV-8 and the engineering rules.
- Output: findings with INV ID, `file:line`, evidence and severity, or "no findings" with what was checked.

### 5. `docs/components.md`

Draft table, to be confirmed as each component starts. Columns: component, owned paths, depends on, branch, status, criteria. Draft components:
- contracts (schema, config, data models)
- generator
- enrichment
- policy
- evaluation
- api
- ops (demo, logs, runbook)

### 6. `docs/plans/harness-working-method.md`

This plan, copied in so the first plan is committed with the work it describes.

### 7. Evidence stubs: `evidence/{intent,design,agentic-workflow,verify,operate,decisions}.md`

- Each file gets a heading and section headings taken from the brief's guidance for that file, with "To be completed".
- `intent.md` has an empty criteria table (ID, band, criterion, known answer, status) for commit 3, and points to `AGENTS.md` for INV IDs.

### 8. `README.md`

A few lines: what this is, current status, and where the evidence pack and working method live.

## Not in this commit

`pyproject.toml`, `uv.lock`, Makefile, verify script, tests, CI and hooks (all commit 2). Acceptance criteria (commit 3).

## Verification before committing

1. Run `python3 -m json.tool .claude/settings.json` to check the settings file is valid JSON.
2. Search the new files for references to anything outside the committed repo. Expect no matches.
3. Run `git check-ignore` to confirm ignored local folders stay out.
4. Stage the named files only, then show `git diff --cached --stat` for your review. You approve the commit, then I push, after asking.
5. After the push, open a fresh session and confirm it:
   - quotes an INV rule from `AGENTS.md`;
   - lists the six skills.

Suggested commit message: `Add working method: agent rules, workflow skills, reviewer, evidence stubs`

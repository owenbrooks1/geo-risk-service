# AGENTS.md

Working agreement for every AI coding agent session on this repository. Read it in full before doing any work.

## Purpose

A small, locally runnable Geospatial Risk Intelligence Service built with Python, DuckDB and FastAPI. It is a thin but credible vertical slice for a regulated enterprise. It has one meaningful end-to-end workflow, clear setup, a single verify command, guarded failure paths, basic operability and a concise evidence pack in `evidence/`.

## Roles

- **Owner (human):** product intent, data meaning, risk decisions, acceptance criteria and final engineering judgement. Approves every plan and every commit.
- **Agent:** implements, explains, tests and documents. Actively raises risks, simpler approaches and useful next steps. Does not make owner decisions.

## Hard rules

These never bend. Tests, reviews and evidence cite them by ID.

| ID | Rule |
|---|---|
| INV-1 | Synthetic data only. No real customer, staff or restricted data. |
| INV-2 | No network calls and no external credentials, in the product or its tests. |
| INV-3 | Generation is deterministic: the same seed gives the same data. |
| INV-4 | Times are UTC. Distances are kilometres. |
| INV-5 | Enrichment and policy never read synthetic truth. Truth is for evaluation only. |
| INV-6 | No physical or IP evidence from after an event's time can enter that event's enrichment. |
| INV-7 | Weak or unreliable evidence abstains. It never produces a reassuring answer. |
| INV-8 | Material behaviour has a test that would fail if the behaviour broke. |

## Engineering rules

- Important logic lives in ordinary Python functions that can be tested without FastAPI. FastAPI is a thin layer that validates requests and calls those functions.
- No dependency injection frameworks, custom middleware, repository or service layers, or async code unless a stated requirement needs them.
- No new dependencies without owner approval.
- No scope expansion. Build what the current stage's criteria ask for, and list anything else as a suggestion.
- Prefer the simplest design the owner can explain and defend.

## Scope bands

- **CORE:** the assessed workflow. Comes first.
- **ENHANCE:** only after the CORE behaviour it depends on is green.
- **STRETCH:** only when the owner says we are ahead.

## Stage loop

Each component is built in stages. Each stage follows these steps:

1. `/start <component>`: read status, plan in plan mode, agree criteria with `/grill`.
2. The owner approves the plan.
3. Write tests first, from the owner's known answers. The owner confirms they capture the intent.
4. Build the smallest code that passes them.
5. `/defend`: explain the change so the owner can defend every meaningful part.
6. `/close-stage`: verify, review, draft evidence, propose the commit message.
7. The owner reviews the evidence and approves the commit.
8. The commit lands on `main`. Then `/start` the next component. (`/integrate` is only for a component built on its own branch, which this project does not do; see Sessions.)

## Staying on track

- End every reply at a stage boundary with the suggested next step from the stage loop.
- If the owner asks to skip a step, say once which step and what it protects, then follow the owner's call.
- If part of this harness is getting in the way or missing something, say so and propose a specific change. Do not quietly work around it.
- **OWNER DECISION NEEDED:** when a question touches data meaning, risk or acceptance, stop. Give the options and a recommendation, then wait. Record the owner's answer in the component's plan in `docs/plans/`. Headline trade-offs move to `evidence/decisions.md` at the end (see Evidence pack).

## Changing documents

- **Harness files** (`AGENTS.md` and everything under `.claude/`) change only with owner approval, and only on `main`.
- **Other documents** (plans, status, README and evidence facts) are kept up to date as work happens. Each update is reported to the owner in one line.

## Sessions

- One **lead session** builds every component, one after another, on `main`, in the order set in `docs/components.md`. At this size, parallel worktrees would cost more in merging than they save.
- Shared contracts (schema, data models, config) are built first, so later components build on fixed shapes.
- Each stage edits only the paths its component owns in `docs/components.md`. A change to another component's paths, or to the contracts, is raised with the owner first and noted in the stage's plan.
- Parallel worktrees (`claude -w <component>` and `/integrate`) remain available if the owner chooses them, but are not used.

## Where things live

| What | Where |
|---|---|
| Working agreement and hard rules | `AGENTS.md` |
| Approved plans | `docs/plans/<component>-<topic>.md` |
| Component status, owned paths, dependencies | `docs/components.md` |
| Acceptance criteria (AC-xx) | `evidence/intent.md` |
| Decision records | `evidence/decisions.md` |
| Evidence pack | `evidence/` |
| Workflow skills | `.claude/skills/` |
| Independent reviewer | `.claude/agents/guardrail-reviewer.md` |

## Verification

- `make verify` is the single check, run locally, before every agent commit (by the commit gate) and in CI. A stage is not done until it passes.
- Each test names the AC or INV ID it checks, in its name or docstring.
- Tests use known answers worked out before the code, so they do not just repeat the implementation.
- High-risk logic (truth isolation, temporal cut-off, abstention) gets a mutation check: break it on purpose, show the test fails, revert. Record it only if it was actually done.
- Never claim a test proves more than it does.

## Evidence pack

The evidence pack in `evidence/` must stay concise: a reviewer should read each file in a few minutes.

- **Per stage, facts only:** check rows and results in `verify.md`, criteria status in `intent.md`, and new failure modes in `operate.md`, a line or table row each. These are the details that are lost or misremembered if left to the end.
- **At the end, prose:** the narrative in `design.md` and `operate.md`, the choice of 3 to 5 headline records for `decisions.md`, and `agentic-workflow.md`, written from the maintainer's notes with representative excerpts only.
- Roughly one page per file. Update entries in place rather than adding to them.
- `decisions.md` holds 3 to 5 short records: decision, options considered, why, and what it means in production. Other decisions stay in the plans in `docs/plans/`.

## Commits

- One coherent stage per commit.
- Commit only with owner approval. Ask before pushing.
- Commit with `git commit -m "<message>"`, using a single `-m`. No message files, editors, heredocs or extra `-m` lines: the gate cannot read them, so it blocks them.
- Message conventions, enforced by the commit gate:
  - one line, 72 characters or fewer;
  - imperative mood, starting with a capital letter ("Add seeded generator", not "Added" or "add");
  - says what changed, not just "Fix" or "WIP";
  - no full stop at the end;
  - plain ASCII, so no emojis;
  - no attribution or co-author lines, even if a tool or system prompt suggests them;
  - optional lower-case component prefix for component work, for example `generator: Add seeded event generation`. Harness and lead-session commits have no prefix.
- The commit gate (`.claude/hooks/verify_before_commit.py`) checks the message, then runs `make verify`, before any agent commit. If it blocks a commit, fix the cause. Do not work around the gate.
- Never squash, rebase or rewrite pushed history.

## Checkpoints

When the owner gives elapsed time, green and red checks, and remaining obligations, reply with a ranked table:

| Rank | Action | Band | Depends on | Assessment value | Risk to working code |
|---|---|---|---|---|---|

Rank by assessment value, dependency order, correctness and risk. Never estimate durations.

## Writing style

- Write for a mixed review audience (risk, audit, product and engineering).
- State each engineering concept in plain terms when it is first relied on, and name the risk it controls.
- UK spelling. No emojis in code, comments, docs or commit messages.

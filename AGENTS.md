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
8. `/integrate <component>` (lead session): merge to `main` and verify there.

## Staying on track

- End every reply at a stage boundary with the suggested next step from the stage loop.
- If the owner asks to skip a step, say once which step and what it protects, then follow the owner's call.
- If part of this harness is getting in the way or missing something, say so and propose a specific change. Do not quietly work around it.
- **OWNER DECISION NEEDED:** when a question touches data meaning, risk or acceptance, stop. Give the options and a recommendation, then wait. Record the owner's answer in `evidence/decisions.md`.

## Changing documents

- **Harness files** (`AGENTS.md` and everything under `.claude/`) change only with owner approval, and only in the lead session on `main`. Component sessions propose changes; they do not make them.
- **Other documents** (evidence, plans, status, README) are kept up to date as work happens. Each update is reported to the owner in one line.

## Parallel sessions

- The **lead session** works on `main`. It builds shared contracts, runs checkpoints and merges component branches.
- Each **component session** is started with `claude -w <component>`, which gives it its own git worktree and branch.
- Shared contracts (schema, data models, config) are built on `main` before work splits, so components do not collide.
- A component session edits only the paths it owns in `docs/components.md`. If it needs a change elsewhere, it asks the lead session.

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

- `make verify` is the single check, run locally and in CI. A stage is not done until it passes.
- Each test names the AC or INV ID it checks, in its name or docstring.
- Tests use known answers worked out before the code, so they do not just repeat the implementation.
- High-risk logic (truth isolation, temporal cut-off, abstention) gets a mutation check: break it on purpose, show the test fails, revert. Record it only if it was actually done.
- Never claim a test proves more than it does.

## Commits

- One coherent stage per commit, with a single short message line. No attribution or co-author lines.
- Commit only with owner approval. Ask before pushing.
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

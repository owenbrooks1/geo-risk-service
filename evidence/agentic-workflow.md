# Agentic workflow

Built in about 2.5 hours. I owned product intent, data meaning, risk and acceptance; the agent planned, built, tested and explained. I spent over an hour on the working method and the acceptance criteria, before any product code, so that every later stage ran under rules I had set.

## Tools used

- **Claude Code (Opus 5.5), lead session:** the primary implementation agent, building every component in order on `main`.
- **Separate Claude Code review sessions:** opened by me to critique the lead session's work, not to build. They checked the harness and plan against the exercise brief, tracked progress against the time left, and listed challenges for me to put to the builder. I chose which ones to raise.
- **Guardrail reviewer (subagent):** read-only; checked each stage containing logic against the hard rules INV-1 to INV-8.
- **Commit gate:** a script Claude Code runs automatically before every agent commit (a hook). It checks the message conventions and runs `make verify`, and blocks the commit if either fails.
- **CI:** runs the same `make verify` on every push.

## Working method first

Before the timebox I wrote my own design draft for the service and rehearsed the toolchain, so the timebox went on building, not setup. The first commits are the method, not the product:

- **My opening instruction set the terms.** It defined the roles, the eight hard rules, the scope bands, how checkpoints are ranked, and the "thin FastAPI over plain functions" design rule. These became `AGENTS.md` (excerpt below).
- **I rejected the agent's first harness proposal** as a rough sketch and had it redesigned against the brief. I then specified what it had to do: a plan document per component; an interview skill that questions me one decision at a time; a suggested next step at every stage boundary so work does not drift; the harness flagging its own problems; harness changes only with my approval, while other documents are updated as work happens.
- **I split it into reviewable commits:** instructions, skills and reviewer first (`d1ef4a5`); then one verify command, CI and the commit gate, with commit conventions I asked to be enforced rather than advised (`503ce8f`); then when and how evidence is recorded (`a934734`).
- **I had the plan checked against the brief and against my own draft before building.** That cut seven components to three plus contracts, built one after another rather than in parallel, with a cut list and a hard stop to protect the timebox.
- **Acceptance criteria were agreed one question at a time** (`6d634f0`): 18 CORE criteria, each with a known answer worked out before any code, using a calculation separate from the product code.

Then four components were built in order, each through the same loop: plan, question the plan, tests first from the known answers, smallest code that passes, explain every part, independent review and deliberate breaks, commit only with my approval.

- contracts (`207a4da`); generator (`f81ed4b`); assessment (`9525adf`, `228fefa`, `cb2e94a`); service (`c071a56`, `f7dbcc2`, `c00cfaa`, `47056aa`).

## Representative steering instructions

From my opening instruction to the agent, verbatim:

> I own product intent, data semantics, risk decisions, acceptance criteria and final engineering judgement. You are the primary implementation tool and should actively surface risks, simpler approaches and useful next steps.
>
> Keep the solution simple enough that I can understand and defend every meaningful component. FastAPI is a thin transport adapter over ordinary Python/domain functions.
>
> Hard constraints: synthetic data only; no external credentials or network calls; deterministic seeded generation; UTC and kilometres only; enrichment/policy must never depend on synthetic truth; no future physical or IP evidence may enter enrichment; weak/unreliable evidence must abstain rather than reassure; material behaviour needs verification.
>
> At checkpoints I will give you actual elapsed time, green/red checks and remaining obligations; rank next actions by assessment value, dependency order, correctness and risk to working functionality - not duration estimates.

A typical stage instruction (assessment, summarised): build ingest, point-in-time evidence and the decision rule for AC-02 to AC-12; write the tests first from the fixture known answers; no database, API, evaluation or logging, which belong to the next stage.

## Where I steered and intervened

The agent proposed options with a recommendation; I made the call, and changed or overruled it where it mattered.

- **Product framing.** I set what the service is and is not: a batch check of many customers' logins for impossible travel, reporting a risk indicator rather than a recommendation, with card-present evidence and streaming deliberately held back (D4).
- **Risk and data meaning.** Every question about what the data means or what counts as safe came to me. For example, I restored my own recall definition when the agent's version let abstaining look better (D5), and challenged the VPN abstain rule before accepting it (D2).
- **Failure handling.** I asked for missing data and broken inputs to fail explicitly, and decided which failures reject a row and which stop the run (D3).
- **Challenging the build.** I kept the builder and the critic apart: separate review sessions listed challenges, and I chose which to put to the builder, prioritising failure paths and audit traceability. The fixes each came with tests (`f7dbcc2`, `47056aa`).
- **Overruling the agent.** Where I disagreed I said so, for example choosing one folder per component over the agent's flat layout, and questioning perfect evaluation scores rather than accepting them.
- **Control of changes.** Nothing was committed without my approval; I tested the service by hand before it closed, and denied a destructive command the agent proposed.

Smaller decisions (tie-breaks, duplicate rows, time parsing, VPN labels) are recorded in each component's plan in `docs/plans/`.

## How generated output was reviewed

- **Known answers first.** Expected decisions and speeds were calculated independently of the product code, for example Sydney to London in 1 hour giving 16,944 to 17,044 km/h. Tests were written first; for contracts, assessment and service they were shown failing before the code existed. When the generator and later the assessment code passed every test at the first attempt, that was treated as a warning sign: the agent ran the full data (30 seeds for the generator) outside the tests before trusting it, and the reviewer then found six weaknesses in the generator tests.
- **Explain before closing.** Every stage was walked through: what each part does, why it is there, how it fails, how it is tested and what changes in production.
- **Independent review.** The guardrail reviewer checked each logic stage against INV-1 to INV-8. Where it could not run code, the agent checked its claims, confirming one and rejecting another.
- **Deliberate breaks.** The high-risk logic was broken on purpose 11 times (UTC times, truth isolation, the time cut-off, abstention, recall, read-only access, the all-or-nothing write, run order). Each made its test fail and was reverted. The full list is in `verify.md`.
- **Real defects the process caught:**
  - a database time type that silently followed the machine's local time zone;
  - a bare number being accepted as a time;
  - generator tests that could pass without really checking anything;
  - a results write that could leave a half-built database;
  - a test suite slowed to 86 seconds by row-by-row database inserts, cut to about 10 seconds with a bulk load.

  The agent's own slips were caught the same way: an over-strict rule, wrong test data, and an evidence row that claimed more than the test showed.
- **Commit gate and CI.** No agent commit happened without a green `make verify`. The gate visibly blocked one commit, during the move into subpackages, before the move was complete.

The evaluation numbers come from planted synthetic scenarios. They show the rule behaves as designed, not how it would perform on real logins.

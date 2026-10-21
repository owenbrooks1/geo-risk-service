---
name: start
description: Begin work on a component - check it is ready, plan it in plan mode, and agree its acceptance criteria with the owner.
argument-hint: "<component>"
disable-model-invocation: true
---

# Start a component

The component name is in the arguments. If none was given, ask.

1. **Check the session.** Confirm the current branch. Components are built one after another on `main` (see Sessions in `AGENTS.md`). If the session is on another branch or in a worktree, say so and stop.
2. **Check readiness.** Read `AGENTS.md` and `docs/components.md`. If anything this component depends on is not yet done on `main`, stop and say what is missing.
3. **Read the criteria.** Read `evidence/intent.md` for the AC IDs this component covers and `evidence/decisions.md` for decisions already made. Do not re-open settled decisions.
4. **Enter plan mode.** Draft the plan:
   - the goal, the paths to be touched and the paths not to touch;
   - the acceptance criteria covered, each with at least one known answer (an input and the exact expected output, worked out before any code);
   - the failure and abstain cases;
   - what not to build;
   - which hard rules (INV IDs) are at risk and how tests will show they hold.
5. **Grill.** Run the `grill` skill on the draft until the owner is satisfied. Update the plan with the outcomes.
6. **Get approval.** Present the plan for owner approval.
7. **Record.** Save the approved plan as `docs/plans/<component>-<topic>.md`. Mark the component "in progress" in `docs/components.md`, with its branch.

End with the suggested next step: write the tests first, from the known answers.

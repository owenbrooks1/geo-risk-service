---
name: close-stage
description: Finish a stage - verify, review independently, check high-risk logic, draft evidence updates and propose the commit for owner approval.
disable-model-invocation: true
---

# Close a stage

Run these steps in order. Stop and report if any step fails.

1. **Verify.** Run `make verify`. If it fails, stop, show the failure and propose a fix. Do not continue on red.
2. **Independent review.** If the change touches generator, enrichment, policy or evaluation code, run the `guardrail-reviewer` agent on the diff. Show its findings in full. For each one, recommend whether to accept or reject it, and say why. The owner decides.
3. **Mutation check.** If the stage contains high-risk logic (truth isolation, temporal cut-off, abstention, rollback), propose one specific mutation (a deliberate break). With the owner's agreement:
   1. apply it;
   2. run the relevant test and show that it fails;
   3. revert;
   4. run `make verify` again.

   Record it only if it was actually done.
4. **Defend.** Run the `defend` skill unless it has already been run on this diff.
5. **Draft evidence updates** for owner review. Facts only, a line or table row each, following the Evidence pack section of `AGENTS.md`. Update only what this stage changed:
   - `evidence/verify.md`: checks added, what each proves, known gaps;
   - `evidence/intent.md`: criteria status;
   - `evidence/operate.md`: new failure modes, config, logs;
   - the component's plan in `docs/plans/`: decisions made during the stage;
   - `docs/components.md`: status.

   Do not write narrative prose, add to `evidence/decisions.md` or touch `evidence/agentic-workflow.md`. Those are written at the end.
6. **Propose the commit.** List the files to stage by name. Give a message that follows the conventions in the Commits section of `AGENTS.md`. Use the component name as the prefix for component work.
7. **Stop.** Tell the owner the stage is ready for their evidence review and commit approval, and remind them to record the stage in their own notes. Do not commit until they approve.

End with the suggested next step: owner evidence review and commit, then `/start` for the next component in `docs/components.md`.

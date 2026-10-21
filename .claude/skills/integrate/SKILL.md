---
name: integrate
description: In the lead session, merge a finished component branch into main, verify on main and update component status.
argument-hint: "<component>"
disable-model-invocation: true
---

# Integrate a component

Run only in the lead session on `main`.

1. **Check the session.** Confirm the current branch is `main`. If not, stop.
2. **Check the branch.** Find the component's branch in `docs/components.md`. Show its commits (`git log main..<branch> --oneline`) and confirm with the owner that it is the right set.
3. **Merge.** Run `git merge --no-ff <branch>`. Never squash or rebase, so the stage commits stay visible in history. If there are conflicts, stop and show them. Resolve them only with the owner's agreement.
4. **Verify on main.** Run `make verify`. If it fails, stop and propose a fix. Do not push a red `main`.
5. **Update status.** Mark the component "merged" in `docs/components.md`, and list any components it unblocks.
6. **Push.** Ask the owner before pushing.
7. **Clean up.** Remind the owner that the component's worktree can now be closed.

End with the suggested next step: the next unblocked component, or `/checkpoint` if the choice depends on time.

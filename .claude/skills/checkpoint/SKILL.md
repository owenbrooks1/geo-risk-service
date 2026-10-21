---
name: checkpoint
description: Rank the next actions from the real state of the repo, using the elapsed time, check status and obligations the owner provides.
argument-hint: "<elapsed time, green/red checks, remaining obligations>"
disable-model-invocation: true
---

# Checkpoint

The owner manages time and scope. This skill turns the current state into a ranked list of next actions.

1. **Read the input.** Take the elapsed time, the green and red checks, and the remaining obligations from the owner's message. Ask for anything missing.
2. **Read the repo state, not memory.**
   - `docs/components.md`: status and dependencies.
   - `evidence/intent.md`: criteria status by band.
   - The most recent `make verify` result. Run it if unsure.
   - Which evidence files are still stubs.
3. **Rank the next actions** in this table:

   | Rank | Action | Band | Depends on | Assessment value | Risk to working code |
   |---|---|---|---|---|---|

   Rank by:
   - assessment value against the exercise requirements;
   - dependency order;
   - correctness;
   - risk to behaviour that already works.

   CORE comes before ENHANCE. Include STRETCH only if the owner has said we are ahead. Never estimate durations.
4. **Flag risks:** red checks, evidence left too late, scope at risk of being cut, and any obligation not yet covered.
5. **Suggest what to cut first** if the owner needs to reduce scope. Never cut the end-to-end workflow, the tests, the guarded failure and abstain paths, the evidence pack or incremental commits.

The owner decides. End with the recommended first action.

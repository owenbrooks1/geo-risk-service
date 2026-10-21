# Plan: Commit 3, intent and acceptance criteria

## Context

Agreed with the owner through `/grill`, one question at a time. The outcome is `evidence/intent.md`: problem, users, workflow, assumptions, out of scope and acceptance criteria AC-01 to AC-22. Every later test cites these IDs.

## Decisions

Marked **[headline]** where the decision is a candidate for the 3 to 5 records in `evidence/decisions.md`.

1. **Core signal is login-to-login impossible travel.** Card-present merchant and ATM evidence is STRETCH, used to corroborate VPN use. *Why:* the smallest signal that still shows point-in-time enrichment, abstention and evaluation.
2. **[headline] Accuracy-aware three-outcome rule.** Flag only if the minimum possible speed is above 1,000 km/h. Clear only if the maximum possible speed is at or below it. Abstain otherwise. *Alternative:* a single centre-to-centre speed check, rejected because it turns imprecise evidence into confident answers. *Production:* the threshold and radii handling are versioned policy and can be tuned with evidence.
3. **[headline] VPN and hosting IPs abstain.** A VPN location is a server, not the person. Flagging creates false alarms and clearing reassures on evidence known to be wrong. VPN logins are never used as a baseline. *Production:* abstains route to other controls (device checks, step-up). VPN use as a risk signal is a separate, later policy question.
4. **IP mapping time validity.** Start inclusive, end exclusive. Only the mapping in force at the login time is used (INV-6).
5. **[headline] Bad rows are rejected and counted. Missing reference data or config stops the run.** *Why:* a broken setup must not look like normal output full of abstains.
6. **[headline] Batch, not streaming.** Streaming adds a broker, async code, late-event handling and exactly-once processing. The assessment is a per-login function, so streaming is a change to ingestion and state, not to the logic. *Production shape:* event stream, then the same function, then a state store, with a stated late-event rule.
7. **Read-only API.** Runs happen from the command line. *Alternative:* `POST /runs`, rejected for added state and concurrency risk.
8. **Tests use hand-written fixtures, not generated data.** Generated data is checked for properties only. *Why:* expected answers must not come from the code under test.
9. **[headline] Evaluation reports precision, recall, false clears and abstain rate,** not accuracy alone. False clears are the key INV-7 risk number. Recall is out of all suspicious logins, so an abstain counts as a miss and abstaining can never make the service look better. Recall among decided logins is secondary and labelled as such. *Changed after review:* the first draft of AC-13 used recall among decided logins (1.0); it is now 0.5.
9a. **Seed 42 false clears = 0 (AC-14) is a behaviour check, not a performance claim.** Generator scenarios are not tuned to make it pass.
10. **Output is a risk indicator, not a recommendation.**
11. **Four CORE scenarios** (normal, genuine travel, impossible jump, VPN). Finer edge cases are covered by fixtures.
12. **Scope trimmed for the timebox.** The list endpoint, evaluation endpoint and order-independence test are ENHANCE. Boundary cases and generated-data criteria are merged. Logging and a README example are added to meet the brief.
13. **Three components instead of seven:** generator; assessment (enrichment and policy as separate modules); service (evaluation, API, demo, logging). This keeps the INV-5 separation in the code and halves the merge overhead. *Changed after review:* the components are built one after another on `main` in the lead session, not in parallel worktrees, to save merge and session overhead within the timebox. The build order and cut list are in `docs/components.md`.

## Known answers

Calculated independently of product code: great-circle distance, 6,371 km radius, 25 km radii.
- Sydney (-33.8688, 151.2093) to London (51.5074, -0.1278): centre distance 16,993.9 km.
- Sydney to Melbourne (-37.8136, 144.9631): centre distance 713.4 km.

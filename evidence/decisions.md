# Decisions

Five short records of the choices that shape the service. Each gives the decision, the options considered, why, and what it means in production. Smaller decisions are recorded in the plans in `docs/plans/`.

## D1. Judge each login with a speed range, and abstain when the range cannot decide

- **Decision:** IP locations are imprecise, so each comparison uses the most and least generous readings of the distance: the centre-to-centre distance minus or plus both accuracy radii. A login is **flagged** only if even the minimum speed is above 1,000 km/h, **cleared** only if even the maximum is at or below it, and **abstains** otherwise.
- **Options:** a single speed check on centre-to-centre distance (flag above the limit, clear below).
- **Why:** a single check turns imprecise evidence into confident answers in both directions. The range keeps every "clear" honest (INV-7), and every decision records its evidence so an analyst can see why.
- **Production:** the threshold lives in versioned policy config (`config/policy.yaml`), stamped on every decision, so it can be tuned with evidence and every outcome traced to the rule that made it.

## D2. VPN and data-centre IPs abstain, and never become a baseline

- **Decision:** a login from a VPN or data-centre IP (as marked in the IP table) abstains with `unreliable_ip`, and the next login is compared with the last usable location instead.
- **Options:** flag VPN logins as suspicious; treat them like any other location.
- **Why:** a VPN's location is the server's, not the person's. Flagging would bury analysts in false alarms from privacy-minded customers. Clearing would reassure on evidence known to be wrong, which is exactly what attackers rely on.
- **Production:** abstains are routed to other controls (device checks, step-up verification). Using card-present merchant data to tell a VPN user at home from an attacker abroad is the planned next signal.

## D3. Reject bad rows, but stop on broken reference data; never serve a half-written result

- **Decision:** a bad login row is rejected and counted by reason, and the rest carry on. A missing or broken IP table, logins file or config stops the run with a clear error. Results are replaced in one transaction (all or nothing), so a failed run leaves the previous results in place.
- **Options:** skip bad rows silently; carry on with missing reference data (every login would abstain); write results directly.
- **Why:** a broken setup must not look like a quiet day full of abstains, and an API must never report "ready" over partial results. Every failure is logged with its cause (AC-09, AC-11, AC-15, AC-17).
- **Production:** rejected rows go to a quarantine table for inspection. Stopped runs alert through central monitoring. The API keeps serving the last complete result (degrade, not fail).

## D4. Batch processing, built so streaming is a change to ingestion only

- **Decision:** logins are processed as a batch. The assessment itself is a plain per-login function: given a login, the customer's last usable location, the IP mapping in force at that time and the policy, it returns a decision.
- **Options:** real-time streaming through a message broker.
- **Why:** streaming adds a broker, async code, late-event handling and exactly-once processing. Each of those is a new risk decision, and none of them changes the decision logic. Batch keeps the slice small, deterministic and easy to verify.
- **Production:** an event stream feeds the same function, with each customer's last usable location in a state store and a stated rule for late events (see `design.md`).

## D5. Evaluate honestly: an abstain counts as a miss, and planted results are not performance claims

- **Decision:** recall is counted over all suspicious logins, so abstaining can never improve it. False clears are reported as the key risk number, alongside suspicious logins abstained, logins not assessed and decisions with no truth label. A metric with nothing to divide by is "not defined", never 0 or 1.
- **Options:** report accuracy, or recall over decided logins only. That first draft let abstaining look better, and was corrected.
- **Why:** a regulated reviewer cares most about what the service missed or wrongly cleared. On the seed 42 data, precision and recall are both 1.0, because the planted scenarios are clean by design. That shows the rule behaves as intended. It is not a measure of real-world accuracy.
- **Not built, on purpose:** card-present merchant and ATM evidence, attackers using VPNs, coarse-IP and nearby-attacker scenarios (which would show the method's limits), machine-learning scoring, real-time streaming, a browser UI and API authentication. These were all deferred to keep the slice explainable within the timebox.

# Intent

## Problem statement

Account takeover often shows up as a login from somewhere the customer could not plausibly have reached since their last login. Simple distance rules either flood analysts with false alarms (VPNs, coarse IP locations, genuine travel) or quietly clear logins they cannot actually judge.

This service assesses each login for impossible travel using only evidence available at that moment. It explains every decision, and it abstains rather than reassures when the evidence is weak.

## Intended users

- **Fraud and security analysts, and operations staff** (frontline teams who call customers and investigate): review flags and need the evidence and reason behind each one.
- **Risk and model owners:** need the decision rule, its version, and how it performs, including false clears and abstain rates.
- **Auditors:** need reproducible decisions. The same data, seed and policy version always give the same results.

## Terms

- **Flag, clear, abstain:** the three possible decisions. Flag means the travel looks impossible; clear means it was possible; abstain means the evidence cannot decide either way.
- **Baseline:** the customer's most recent earlier login with a usable location, which the new login is compared with.
- **Accuracy radius:** how far, in kilometres, the true location may be from the point an IP address maps to.
- **Hidden truth:** the generator's record of which logins were planted as suspicious. Used only to score the decisions.

## Workflow

1. **Generate** a seeded synthetic dataset: customers, logins (UTC time and IP), an IP geolocation table, and hidden truth.
2. **Process** every login in event-time order. Compare its IP location with the customer's most recent earlier usable location, using the IP mapping in force at the login time.
3. **Decide** flag, clear or abstain, using the accuracy-aware speed rule below. Store the decision with its reason, evidence and policy version.
4. **Evaluate** decisions against the hidden truth.
5. **Serve** results and status through a read-only API.

**Decision rule.** The minimum and maximum possible distance are the centre-to-centre distance minus or plus both IP accuracy radii (never below zero). Dividing each by the time gap gives a speed range.

- **Flag** if even the minimum speed is above the threshold.
- **Clear** if even the maximum speed is at or below it.
- **Abstain** otherwise.

The threshold is 1,000 km/h, held in versioned policy config.

## Assumptions

1. Logins arrive as a complete batch. There is no real-time stream (see decisions).
2. The IP geolocation table is trusted as given, apart from its own accuracy radius and connection type.
3. Distance is great-circle distance (the shortest path over the Earth's surface), using a 6,371 km Earth radius.
4. 1,000 km/h is a policy setting, not a fact, and it is versioned.
5. The output is a risk **indicator** for people and downstream systems to use. The service does not block logins, recommend actions or contact customers.

## Constraints

- **Exercise:** a 3-hour timebox; runs locally from the repository; no paid API keys or private credentials; synthetic data only; one command runs every check.
- **Hard rules** (full wording in `AGENTS.md`; tests cite them by ID):

| ID | Rule, in short |
|---|---|
| INV-1 | Synthetic data only. |
| INV-2 | No network calls or credentials, in the service or its tests. |
| INV-3 | The same seed always gives the same data. |
| INV-4 | Times are UTC; distances are kilometres. |
| INV-5 | Decisions never see the hidden truth; it is used only to score them. |
| INV-6 | No evidence from after a login can be used to judge it. |
| INV-7 | Weak evidence abstains; it never produces a reassuring answer. |
| INV-8 | Each material behaviour has a test that fails if it breaks. |

## Out of scope

- Real customer, IP or location data, and any real IP lookup service.
- Blocking logins, step-up verification or customer contact.
- API authentication and access control. The production approach is described in `operate.md`.
- Streaming ingestion, a browser UI and cloud deployment. The production shape is described in `design.md`.
- Machine learning scoring. The policy is explicit, versioned rules.
- **STRETCH**, only if time allows:
  - merchant and ATM card-present evidence, used to corroborate VPN use;
  - prior-flag history;
  - VPN use as a risk signal in its own right;
  - coarse-IP scenarios and IP reassignment in the generated data;
  - a quarantine table for rejected rows;
  - audit records of policy runs.

## Success criteria

Tests cite these IDs. Fixtures are small hand-written cases in `examples/`, with answers worked out before any code. Speeds come from great-circle distance and 25 km radii unless stated. Status values: draft, agreed, built, cut (not built). All 18 CORE criteria are built; the ENHANCE criteria were not built, to fit the timebox.

| ID | Band | Criterion | Known answer | Status |
|---|---|---|---|---|
| AC-01 | CORE | Generated data is deterministic and complete (INV-1, INV-3) | Seed 42 twice gives identical data; seed 43 differs. Every login has exactly one truth label in a separate truth table. Normal, genuine travel, impossible jump and VPN scenarios each appear. | built |
| AC-02 | CORE | Impossible travel flags | Sydney to London, 1 hour: flag, speed range 16,944 to 17,044 km/h. | built |
| AC-03 | CORE | Possible travel clears | Sydney to Melbourne, 2 hours: clear, speed range 332 to 382 km/h. | built |
| AC-04 | CORE | Imprecise evidence abstains (INV-7) | Sydney to Melbourne, 45 minutes: abstain `inconclusive`, speed range 885 to 1,018 km/h. | built |
| AC-05 | CORE | First login abstains (INV-7) | A customer's first login: abstain `no_baseline`. | built |
| AC-06 | CORE | VPN abstains and is never a baseline (INV-7) | VPN login: abstain `unreliable_ip`. Sydney, then a VPN login, then London 1 hour after the Sydney login: London is compared with Sydney and flags. | built |
| AC-07 | CORE | IP mapping in force at login time only (INV-6) | Mapping starts 1 second after the login: abstain `no_ip_location`. IP reassigned from Sydney to London at 12:00: a login at 11:59 uses Sydney and a login at 12:00 uses London (start inclusive, end exclusive). | built |
| AC-08 | CORE | Boundary cases | Same timestamp, Sydney and London: flag. Same timestamp, same IP: abstain `inconclusive`. Distance exactly 1,000 km over 1 hour with zero radii: clear. A minimum speed of exactly 1,000 km/h does not flag. | built |
| AC-09 | CORE | Bad rows are rejected and counted | Fixture with 1 missing IP, 1 invalid IP, 1 time without UTC offset and 1 duplicate ID: 4 rejected, one per reason. The remaining rows are assessed. | built |
| AC-10 | CORE | Empty input | 0 logins: 0 assessed, 0 rejected, no error. | built |
| AC-11 | CORE | Missing reference data or config stops the run | Missing or empty IP table, or one IP with two mappings in force at the same moment: run stops with a clear error. Policy with a negative threshold or no version: stops before assessing. | built |
| AC-12 | CORE | Truth isolation (INV-5) | Processing with the truth table removed gives identical decisions. | built |
| AC-13 | CORE | Evaluation metrics are exact, and abstaining never improves them | Six logins: 2 flagged (1 suspicious), 3 cleared (all genuine), 1 abstained (suspicious). Precision 0.5; recall 0.5, because an abstain counts as a miss; false clears 0; abstain rate 1/6; suspicious logins abstained 1. Recall over decided logins only (1.0) may be shown, labelled secondary. By scenario: impossible jump 1 flag and 1 abstain; genuine travel 1 flag and 1 clear; normal 2 clears. | built |
| AC-14 | CORE | No false clears on planted scenarios (INV-7) | Seed 42: false clears = 0. Scenarios are not tuned to make this pass. It shows the policy behaves as designed on the planted scenarios, not how it would perform on real logins. | built |
| AC-15 | CORE | `GET /health` | Before a run: not ready, with the reason. After `make demo`: ready, with policy version, seed and counts, for the newest run in `run_summary`. | built |
| AC-16 | CORE | `GET /assessments/{login_id}` | Known ID: decision, reason, evidence and policy version. Unknown ID: 404. | built |
| AC-17 | CORE | Run logging | Each run logs one summary: run time, seed, policy version, rows loaded, rejected by reason, decisions by outcome. A stopped run logs the cause (for example, the missing IP table path). The run time is the same in the log, the stored run, `evaluation.json` and `/health`. | built |
| AC-18 | CORE | One-command demo | From a clean checkout, `uv sync` then `make demo` generates, processes and evaluates, and prints the evaluation report. `make serve` then starts the API over those results. The README shows a real example request and response. | built |
| AC-19 | ENHANCE | `GET /assessments` filters | `decision=maybe`: 422. Limit above the cap: 422. | cut (not built) |
| AC-20 | ENHANCE | `GET /evaluation` | Returns the AC-13 metrics. Never includes per-login truth. | cut (not built) |
| AC-21 | ENHANCE | Order independence | The same fixture in shuffled order gives identical decisions. | cut (not built) |
| AC-22 | ENHANCE | `POST /assess` | Assesses one new login live against stored history. Invalid body: 422. | cut (not built) |

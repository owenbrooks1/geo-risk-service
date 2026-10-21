# Plan: generator (seeded synthetic logins, IP table and hidden truth)

## Context

Contracts is done (`207a4da`). The generator produces the demo and evaluation dataset: synthetic customers' logins, the IP geolocation table and the hidden truth, as three CSV files. It owns AC-01. It also has to make AC-14 (no false clears on planted scenarios) meaningful, without being tuned to pass it.

## Paths
- **Touch:** `src/geo_risk_service/generator.py` and `tests/test_generator.py`.
- **Do not touch:** contracts files, `config/` and `examples/`. If the generator needs a contract change, it's raised first.

## Design
- **Entry points:** `generate(seed, customers, days) -> Dataset` (three lists of contract models), and `write_dataset(dataset, data_dir)`, which writes `logins.csv`, `ip_locations.csv` and `truth.csv`. Both are plain functions with no FastAPI involvement. The service stage calls them.
- **Determinism (INV-3):** one `random.Random(seed)`. Lists are iterated in a fixed order. No wall-clock time: the period starts at the fixed date 2026-05-01T00:00Z. Login IDs are assigned after sorting by (event_time, customer_id, ip).
- **Geography:** about 20 world cities with public coordinates, held as a constant.
- **IP table:**
  - each city has a pool of residential IPs (25 km radius);
  - three data-centre cities have hosting IPs (VPN exits);
  - all mappings are valid from the period start and open-ended. Reassignment is STRETCH.
  - All addresses come from the documentation ranges (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24), so they can never be real hosts (INV-1).
- **Customers:** `C-0001` and up. Each has a home city and a home IP.
- **Normal activity:** 0 to 3 home logins a day, at least 30 minutes apart, so two home logins never look fast.
- **Scenarios** (Q-G3 sets the proportions). Each login carries one scenario in truth:
  - `normal`: home logins. Genuine.
  - `genuine_travel`: one trip to another city. The arrival time leaves enough time to have flown there, (distance + 50 km)/800 km/h plus 1 hour. Genuine, and should clear.
  - `impossible_jump`: one login from a city at least 3,000 km away, 30 to 90 minutes after a home login. **Suspicious.** Even the minimum speed is above 1,000 km/h, so it should flag.
  - `vpn`: some logins from hosting IPs. Genuine (Q-G2). Should abstain.
- **Distance:** the generator uses its own great-circle formula to space its scenarios. It does not import assessment code, so the planted truth stays independent of the code it will judge.

## AC-01 tests first (`tests/test_generator.py`), with known answers
1. Seed 42 generated twice gives byte-identical CSV files. Seed 43 gives different `logins.csv`.
2. Truth `login_id`s equal the login `login_id`s exactly, with one label each.
3. Normal, genuine travel, impossible jump and VPN each appear at least once, even with a small run (5 customers).
4. Every row parses under the contract models.
5. INV-5: `logins.csv` has exactly the columns `login_id`, `customer_id`, `event_time`, `ip`, with no truth in the inputs. Truth is only in `truth.csv`.
6. INV-1: every IP is in a documentation range.
7. Planted scenarios really are what they say, checked with a formula written in the test:
   - every `impossible_jump` login is at least 3,000 km and at most 90 minutes from that customer's previous login;
   - every `genuine_travel` arrival is reachable at 1,000 km/h even with both radii added.
8. No IP has two mappings in force at once, which would otherwise stop the run under AC-11.

## Hard rules at risk
INV-1 (test 6), INV-3 (test 1), INV-4 (times written with `Z`, checked by test 4), INV-5 (test 5).

## Not built here
Reading CSVs with rejection (assessment), any decision logic, the `make demo` wiring (service), and STRETCH scenarios (coarse IPs, reassignment, merchant data).

## Decisions from the grill
- **Q-G1, return login:**
  - After a jump, the customer's next home login is spaced so that it's reachable from the jump city at 1,000 km/h, even with both radii added. Only the jump itself flags.
  - The return trip after genuine travel is spaced the same way.
  - Test 7 also checks the login after each jump.
  - **For the assessment stage:** should a flagged login become the next baseline? That's an open policy question, to be raised at `/start assessment`.
- **Q-G2, VPN truth:** VPN logins are labelled genuine (the real customer on a privacy VPN). Attackers using VPNs are a STRETCH scenario.
- **Q-G3, mix:**
  - 70% normal-only customers, 10% genuine travel, 10% impossible jump and 10% VPN.
  - There is at least one of each, so a 5-customer test run still has all four.
  - One scenario event per customer. The defaults are 100 customers over 30 days, about 3,000 logins.
  - Customer counts per scenario are fixed, and the seeded random generator decides which customers get them.

## Found during `/defend`
- **Known coupling:** the generator spaces "reachable" logins for 1,000 km/h, the same figure as policy v1. It deliberately doesn't read the policy, so planted truth isn't shaped by the rule it tests. If the threshold is lowered, some genuine trips may start abstaining.
- **Trips near the end of the period can run a few days past the 30-day window.** This is harmless, because nothing assumes the window.
- **Simplified after review:**
  - The scenario checks now run on four seeds.
  - VPN customers have exactly 3 VPN logins at random times.
  - Data centres are held in a single lookup. Dallas replaces a duplicate of Singapore's coordinates.
  - An unused lookup was removed.

## Independent review outcomes (all accepted by the owner)
- Added: only planted jumps are suspicious; per-scenario check counts; a checksum computed in a separate process; a Python 3.12 pin; UTC check on IP times.
- Fixed: the one-day fallback now spaces logins 12 hours apart; the docstring now says "4 or more customers", and the small-run test uses exactly 4.
- Recorded as a known gap: AC-14 is met by construction and never reaches `inconclusive` on generated data.

## Record on approval
- Save as `docs/plans/generator-synthetic-data.md`.
- Mark the generator "in progress" on `main`.
- Add "flagged login as baseline" to the open questions for assessment.

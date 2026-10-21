---
name: grill
description: Interview the owner, one question at a time, to sharpen a plan or design until data meaning, risk and acceptance are unambiguous. Use while planning a component or when a design question is open.
---

# Grill a plan or design

Purpose: find the gaps in a plan before code is written, and make sure every decision about data meaning, risk and acceptance is the owner's, not the agent's.

## How to ask

- One question at a time. Wait for the answer before asking the next.
- Each question names the AC or INV ID it relates to, or says it is a new criterion.
- Give a recommended answer and the main alternative, each in one line, so the owner can accept, adjust or reject quickly.
- Explain any engineering concept in plain terms when it first comes up, and say which risk it controls. For example: "An as-of join picks the latest record at or before a given time. It controls future-data leakage (INV-6)."
- Push on the places where generated systems usually go wrong:
  - boundaries: equal timestamps, zero distance, empty inputs;
  - missing or contradictory evidence;
  - what abstains and what does not (INV-7);
  - what could leak truth or future data (INV-5, INV-6);
  - what a test would really prove;
  - what happens on failure.
- Stop when the plan has no open questions on meaning or risk, or when the owner says enough.

## Record the outcomes

- Criteria, known answers and band changes go in `evidence/intent.md`.
- Decisions with a real trade-off go in `evidence/decisions.md` as a short record: decision, options considered, why, and what it means in production.
- Summarise for the owner, in a few lines, what changed in the plan.

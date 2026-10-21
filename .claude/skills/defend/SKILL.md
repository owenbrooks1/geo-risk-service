---
name: defend
description: Explain a change so the owner can defend every meaningful part of it - what it does, why it is there, how it fails, how it is tested and what changes in production. Use after building a stage and before closing it.
---

# Defend a change

The owner is accountable for every line that is submitted. This skill makes sure they can explain and defend it.

1. Read the current diff against the base branch (`git diff main...HEAD`, plus any uncommitted changes).
2. For each meaningful part (a function, a SQL query, a route, a config value, a test), answer in plain terms:
   - **What does it do?**
   - **Why is it here?** Name the AC or INV ID it serves.
   - **What happens when it fails?** Name the error, the abstain path or the rollback.
   - **How is it tested?** Name the test and the known answer it checks.
   - **What would change in production?**
3. Flag anything that:
   - serves no criterion;
   - adds a layer, abstraction or dependency the stage did not need;
   - would be hard to explain to a reviewer in a sentence or two.

   For each one, propose the simpler version.
4. List any framework-specific construct (for example a FastAPI or Pydantic feature) with a one-line plain explanation.
5. Keep the whole answer short enough to read in one pass. Do not paste the code back.

End by asking the owner whether anything should be simplified or removed before `/close-stage`.

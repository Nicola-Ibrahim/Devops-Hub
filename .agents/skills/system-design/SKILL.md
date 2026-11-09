---
name: system-design
description: Coordinate DevOps Hub changes spanning components or bounded contexts. Use for cross-component contracts, ownership, sequencing and acceptance; use a component skill alone for local work.
---

# Cross-component design

1. Identify affected components and load only their skills. Inspect current code,
   callers, working-tree changes and any requested task record.
2. Trace one end-to-end path, including ownership, state transitions, failures and
   recovery. Separate observed behavior from assumptions.
3. Assign every rule and side effect to one component. Define boundary contracts
   and resolve compatibility, concurrency and recovery decisions.
4. Record observable acceptance criteria, dependencies, file ownership and ordered
   implementation. Planning does not authorize implementation or live operations.
5. Implement contracts before dependents, integrate the complete flow and report
   actual checks, review activity and remaining limits.

Follow [workflow guidance](../../../.codex/workflow/README.md). Create a task record
only when requested. The coordinator owns shared contracts and final integration.

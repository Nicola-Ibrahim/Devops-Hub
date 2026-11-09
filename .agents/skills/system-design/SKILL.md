---
name: system-design
description: Design and coordinate substantial DevOps Hub changes spanning multiple components or bounded contexts. Use for cross-component contracts, ownership and sequencing; use a component skill alone for local work.
---

# Coordinate cross-component design

Use this sequence when a change crosses component or bounded-context boundaries:

1. **Establish scope and routing.** Follow root and affected directory
   `AGENTS.md` files. Identify the components involved and load only their skills:
   backend-development for domain/application/workers, api-development for HTTP,
   frontend-development for Next.js, and delivery-engineering for CI and hosting.
   Check branch, HEAD, staged/unstaged changes, current callers and any named
   task record. Use [workflow guidance](../../../.codex/workflow/README.md);
   create a task record only when requested. Preserve unrelated work.
2. **Trace the end-to-end behavior.** Follow one representative path across the
   affected components, including state transitions, ownership, errors and
   recovery. Record facts separately from hypotheses; documentation and present
   files are not proof that an integration works.
3. **Choose boundaries and contracts.** Assign each rule and side effect to one
   component. Keep identity and developer_platform independent. Define data,
   API, event, artifact or deployment contracts at their boundary. Compare
   alternatives only when they materially change ownership, compatibility,
   concurrency, failure propagation or recovery.
4. **Define the result.** State observable acceptance criteria, preserved
   behavior, contracts, dependencies, file ownership, an ordered plan and only
   material decisions that need user input. A planning record does not authorize
   implementation, deployments or provisioning.
5. **Implement only when authorized.** Resolve shared contracts first, then use
   the relevant component skills for bounded edits. Integrate and verify the full flow;
   obtain a separate read-only review for substantial diffs when available.
   Report actual agent activity, commands, results and unresolved limits. Label
   self-review accurately and reuse valid prior evidence.

Keep responsibility explicit: Terraform provisions hosting, Ansible configures
hosts, CI/CD delivers releases, and API/workers manage developer-requested
resources. Use delivery-engineering for the implementation details of the first
three. Code changes alone do not authorize live infrastructure, shared migrations,
resource provisioning or secret changes.

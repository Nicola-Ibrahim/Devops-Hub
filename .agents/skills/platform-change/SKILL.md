---
name: platform-change
description: Plan and implement substantial DevOps Hub changes across application, provisioning, or CI/CD boundaries while preserving resource lifecycle and recovery behavior. Use for changes spanning components, not routine small edits.
---

# Platform changes

Use the repository's `AGENTS.md` as the source of stable project rules.
Read the named task file. Create a task record only when the user requests one,
using [the task template](../../../.codex/workflow/templates/task.md) under
`.codex/workflow/tasks/`. Preserve existing records. Otherwise keep the requested
scope and progress in the conversation.
See [the workflow guide](../../../.codex/workflow/README.md) for navigation and handoffs.

1. Trace the affected behavior before proposing a change. Record facts separately
   from hypotheses and identify resource/state behavior that must be preserved.
2. Define observable acceptance criteria and an ordered plan. Identify material
   ambiguities; resolve routine choices within the user's scope. If only planning
   was requested, stop after the plan.
3. For authorized implementation, follow main agent defines scope → investigator
   gathers evidence → coder implements a bounded part → reviewer
   checks the diff → main agent integrates and verifies. Reuse completed evidence.
   Assign explicit file ownership, acceptance criteria and safeguards. Preserve
   others' edits. Keep shared contracts and integration with the main agent.
   Small fixes may stay single-agent. Verify affected behavior as work proceeds;
   use characterization checks when refactoring could alter state transitions,
   API compatibility, lease expiry, idempotency or cleanup behavior.
4. Delegate bounded independent investigation/review when useful and available.
   Keep edit ownership non-overlapping. For substantial changes obtain a separate
   review when possible. If unavailable, label self-review accurately.
5. Resolve findings, rerun checks justified by changes and record actual results,
   limitations and next actions in the requested task record or conversation.

Distinguish invalid developer requests, provider failures, provisioning timeouts
and cleanup failures. A passing check does not justify deleting existing resources
or changing shared environments. Task records are specifications and handoffs;
they do not authorize live provisioning, deployment, paid services or migrations.

Keep reporting proportional. The requested task record holds the plan, decisions
and handoff together; do not create extra scorecards or reporting hierarchies.

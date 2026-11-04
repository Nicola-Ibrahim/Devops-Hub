---
name: platform-change
description: Coordinate substantial DevOps Hub changes, including planning, implementation and resuming work across API, dashboard, resource workers or delivery boundaries. Routine fixes need no task record.
---

# Platform change workflow

## Establish scope and phase

Read `AGENTS.md`, applicable nested guidance and the brief. Identify the developer
outcome and authorized phase. On resume, reconcile the record with current branch,
HEAD, staged/unstaged changes, untracked implementation and actual check results.
Continue unfinished authorized work; a stale summary must not narrow explicit user scope.

Create a record only when the user requests one, using
[the task template](../../../.codex/workflow/templates/task.md). Preserve existing
records. Write only permitted paths; otherwise report in chat. The
[workflow guide](../../../.codex/workflow/README.md) maps roles, prompts and records.

## Investigate and plan

Trace affected callers and failure paths. Separate source-backed facts, assumptions
and proposals. Define observable acceptance criteria, preserved behavior, contracts,
ordered dependencies and file ownership. Resolve routine choices within scope;
identify material product decisions needing input.

Use [architecture-review](../architecture-review/SKILL.md) for boundaries and DI,
[resource-lifecycle](../resource-lifecycle/SKILL.md) for persistence/provider recovery,
and [platform-verification](../platform-verification/SKILL.md) for check isolation.
Load only relevant specialists; they supply subject evidence, not another task record.
Delegate investigation when a separate evidence gap justifies it; no fixed agent
sequence is required for every task.

For planning-only work, save the requested plan and stop before implementation or
proposed test execution. Explicitly requested safe read-only checks remain permitted.

## Implement and integrate

Reuse evidence. Assign bounded coding work when useful, with explicit owned paths,
acceptance criteria, safeguards and expected checks. Tell coders they share the
workspace and must preserve others' edits. Resolve shared contracts first; sequence
dependent edits and parallelize only independent ownership. The coordinator owns
integration and the requested task record.

Verify affected behavior through platform-verification. For substantial changes,
request independent read-only review of the actual diff against acceptance criteria.
Address confirmed findings and rerun justified checks. If a separate agent is
unavailable, continue within scope and label self-review and its limits accurately.
Role configuration alone is not evidence of execution.

## Report the real outcome

Refresh the requested record's scope, baseline, completed/remaining work, decisions,
actual commands/results and agent activity; otherwise report in chat. Distinguish
code present, fake-provider tests, real local acceptance and external verification.
Do not mark a milestone complete while required acceptance remains unresolved.
Finish the authorized scope or identify the concrete blocker and preserved state.
Keep one requested record, without extra scorecards or status hierarchies.

This procedure grants no additional authority to provision live resources, deploy,
run shared migrations, publish repositories/images or change secrets.

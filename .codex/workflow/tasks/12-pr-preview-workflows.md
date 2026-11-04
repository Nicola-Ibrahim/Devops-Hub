# 12 — Pull-request preview workflows

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 12 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; large scope; P4.
- **Feature status:** Partially implemented.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Choose trusted CI promotion and URL publication mechanisms, fork policy and reopen behavior before coding. External GitHub writes require explicit execution scope.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** [postgres-recovery-acceptance](02-postgres-recovery-acceptance.md), [application-database-attachment](08-application-database-attachment.md), [application-runtime-visibility](10-application-runtime-visibility.md), [github-template-delivery](09-github-template-delivery.md)
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Create a trusted PR application/database preview, publish its URL, and clean it up after closure or expiry.

Signed webhook verification, event replay records, preview steps, expiry and cleanup code exist. Cleanup/retry/closure fixes were added. Trusted source-SHA to approved-image promotion, URL publication and complete reopen/closure/restart acceptance remain unfinished; the existing platform_image_digest payload field is not proof of a real GitHub build integration.

Relevant implementation:

- `backend/src/developer_platform/application/delivery.py: process_github_webhook`
- `backend/src/developer_platform/infra/persistence/delivery.py`
- `backend/src/containers/application_operations.py`
- `.github/workflows/`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Only an approved image demonstrably bound to the current trusted PR SHA can deploy.
- [ ] A usable URL is published through an authorized integration without exposing credentials.
- [ ] Duplicate/reordered events and restarts do not create duplicates or resurrect closed work.
- [ ] Closure/TTL cleanup handles late effects and preserves uncertainty until absence is confirmed.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Design the trusted CI image-promotion contract and separate desired lifecycle state from observed status.
2. Define source-SHA fencing, fork policy, closure/reopen behavior and URL publication permissions.
3. Implement small sequential slices with durable independently retryable steps.
4. Run duplicate-event, close-during-create, expired-claim, failed cleanup and same-SHA reopen acceptance.

**Reasoning requirement:** Investigate the affected path first, record decisions/contracts and failure cases, then implement bounded slices. Use independent review for substantial changes; this is not a one-edit task.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| Task split | Source-backed backlog specification | No new application/resource checks executed |
| Feature acceptance | Pending | Existing source or partial checks do not establish full acceptance |

Review status: coordinator documentation self-review only; no independent feature acceptance claimed.

### Agent activity

No new agent ran for this task split. Earlier implementation/review activity is historical and must not be reported
as new task execution. The current acceptance criteria remain unchecked.

## Handoff

- Completed: bounded specification and links to existing evidence.
- Remaining: unchecked acceptance criteria above.
- Next concrete action: work only on this named task when selected; do not resume the entire roadmap automatically.

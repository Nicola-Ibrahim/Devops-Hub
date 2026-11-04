# 10 — Application deployment visibility

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 10 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; medium scope; P3.
- **Feature status:** Partial / missing API.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Choose log retention/limits and owner/admin visibility before implementing the public contract.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** [application-database-attachment](08-application-database-attachment.md)
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Expose authorized deployment health, bounded logs, URL and history without leaking secrets.

Deployment steps/history and local Docker execution exist. A historical succeeded operation is not current health. Complete health/log retrieval APIs and dashboard actions have not been demonstrated.

Relevant implementation:

- `backend/src/api/platform/applications.py`
- `backend/src/developer_platform/application/delivery.py`
- `backend/src/developer_platform/infra/application_runtime.py`
- `frontend/src/components/dashboard.tsx`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Authorized users see current URL/health and ordered deployment history.
- [ ] Bounded logs exclude managed credentials and are inaccessible across projects.
- [ ] Missing, unhealthy and failed deployments are represented accurately; reads do not provision resources.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Define current health versus immutable deployment history and access policy.
2. Specify bounded/redacted log and status adapter contracts before transport changes.
3. Implement backend contracts, then a separately owned dashboard slice.
4. Verify unavailable/missing containers and authorization boundaries.

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

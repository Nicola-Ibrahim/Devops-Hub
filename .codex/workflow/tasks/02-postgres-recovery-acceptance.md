# 02 — PostgreSQL recovery acceptance

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 02 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; medium scope; P1.
- **Feature status:** Verification / remaining coverage.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Choose deterministic fault injection points and bounded test timeouts; do not infer immediate access revocation during a provider outage.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** backend integration closeout (completed; see [completed prerequisites](README.md#completed-prerequisites))
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Prove failure recovery beyond the already passing successful lifecycle.

HTTP request/connect/renew/delete, duplicate request IDs, expired-claim adoption, real container restart, endpoint reconciliation and real expiry cleanup passed. Queue/uncertainty PostgreSQL tests exist. This does not prove the complete process-kill, outage and late-effect matrix.

Relevant implementation:

- `backend/tests/integration/test_postgres_docker_acceptance.py`
- `backend/tests/integration/test_resource_worker_postgres.py`
- `backend/src/containers/worker_queue.py`
- `backend/src/developer_platform/application/worker.py`
- `backend/src/developer_platform/infra/docker_provider.py`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Process interruption after claim, allocation and before completion recovers without duplicate allocation or lost credentials.
- [ ] Lost responses, failed volume removal, stale workers and late creates preserve deletion intent and uncertain reservations.
- [ ] Unrelated Docker objects survive; eventual cleanup and audit history are demonstrated.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Map existing coverage to each remaining failure window; reuse passing evidence.
2. Design deterministic interruption/outage tests with explicit owned-resource cleanup.
3. Fix only defects demonstrated by those checks and review lifecycle changes.

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

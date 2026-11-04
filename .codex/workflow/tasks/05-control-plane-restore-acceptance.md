# 05 — Control-plane backup and restore acceptance

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 05 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; large scope; P2.
- **Feature status:** Existing assets / unverified recovery.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Choose retention/recovery objectives and key custody; destination access and any real restore require explicit authorization. Developer DB backups are a separate product policy.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** [postgres-recovery-acceptance](02-postgres-recovery-acceptance.md)
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Restore control-plane data and reconcile it with existing owned resources safely.

Encrypted backup/scheduling/upload and isolated restore scripts exist. No complete encrypted restore using protected resource-key custody followed by reconciliation was performed.

Relevant implementation:

- `scripts/ops/backup-control-plane.sh`
- `scripts/ops/restore-control-plane-isolated.sh`
- `infra/ansible/roles/backup/`
- `backend/src/containers/worker_queue.py`
- `docs/operations.md`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] A real encrypted archive restores successfully with the correct separately protected keys.
- [ ] Corrupt archives or unavailable keys fail safely before destructive changes.
- [ ] Restored workers do not duplicate resources or delete foreign objects; reconciliation is demonstrated.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Define consistent backup, encryption/key custody, retention and writer/worker fencing contracts.
2. Test scripts on disposable data with independently generated test keys.
3. Restore into an isolated target, verify schema/data and reconcile owned provider objects.
4. Document recovery limits and failures without changing live data.

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

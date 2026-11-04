# 08 — Secure application database attachment

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 08 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; large scope; P3.
- **Feature status:** Partially implemented.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Confirm the documented local-only network and UID contract from current code. Broader runtime/language support requires its own design, not an implicit extension.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** backend integration closeout (completed; see [completed prerequisites](README.md#completed-prerequisites))
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

An approved application connects to its own PostgreSQL through a private configuration reference and can be cleaned up safely.

ApplicationDatabaseBindings, DockerApplicationRuntime, the ledger bridge and runtime tests exist. A real run reached HTTP health while using PostgreSQL, then failed during cleanup. Subsequent drift checks were being changed when work was interrupted; no complete final acceptance or independent sign-off is recorded.

Relevant implementation:

- `backend/src/containers/application_bindings.py`
- `backend/src/containers/application_resources.py`
- `backend/src/developer_platform/infra/application_runtime.py`
- `backend/src/developer_platform/infra/delivery_adapters.py: DockerApplicationAdapter`
- `backend/tests/integration/test_application_runtime_docker.py`
- `templates/python-fastapi/1.0.0/app/database.py`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] The non-root generated FastAPI application performs authenticated SQL through a read-only mode-0400 reference.
- [ ] Passwords/DSNs are absent from environment values, arguments, ordinary responses and logs.
- [ ] Wrong project, owner, installation, expired lease and drifted Docker objects fail closed.
- [ ] Retry/restart reuses owned objects; app cleanup removes its containers/configuration/network and leaves the database intact.
- [ ] Database cleanup separately removes the DB and storage; no foreign Docker objects are touched.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Reconcile the interrupted implementation and latest reviewer findings before editing.
2. Freeze private file ownership, network membership, runtime drift and removal contracts.
3. Finish cleanup and add missing resolver/drift regressions.
4. Run real isolated app-to-database acceptance and obtain independent review.

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

# 07 — Platform release and rollback acceptance

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 07 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; large scope; P2.
- **Feature status:** Existing assets / integration.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Choose an authorized test registry/host and migration compatibility policy; no automatic production deployment or publishing is authorized by this task.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** [ansible-host-acceptance](06-ansible-host-acceptance.md), backend integration closeout (completed; see [completed prerequisites](README.md#completed-prerequisites))
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Deliver a tested immutable platform image and recover a failed release safely.

CI, image publishing, deployment, migration checks and previous-digest rollback assets exist. Publishing trust now requires a successful same-repository push. Images built locally, but no actual publish/deployment/failed-readiness rollback has been demonstrated.

Relevant implementation:

- `.github/workflows/platform-ci.yml`
- `.github/workflows/publish-images.yml`
- `.github/workflows/deploy-platform.yml`
- `scripts/ops/release.sh`
- `compose.yaml`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Required checks gate trusted publishing; an untrusted PR cannot obtain publishing permissions.
- [ ] Deployment uses the tested digest and never rebuilds on the host.
- [ ] Readiness failure restores the previous compatible image; incompatible migrations block unsafe rollback.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Review trusted workflow/OIDC/digest and migration compatibility contracts.
2. Complete static/isolated failure checks and release metadata validation.
3. On an explicitly authorized disposable target, deliver the exact tested digest.
4. Inject readiness failure and prove compatible previous-image rollback.

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

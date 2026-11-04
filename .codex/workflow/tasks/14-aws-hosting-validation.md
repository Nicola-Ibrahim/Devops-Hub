# 14 — AWS hosting infrastructure validation

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 14 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; large scope; P2.
- **Feature status:** Existing assets / cloud deferred.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** AWS account/region/budget, state custody and execution permission are required before cloud operations. Do not acquire credentials or apply merely to complete the task record.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** [ansible-host-acceptance](06-ansible-host-acceptance.md), [platform-release-recovery](07-platform-release-recovery.md)
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Provide one reviewed AWS hosting target while retaining a completely cloudless local demo.

Terraform host/network/IAM/OIDC, protected-state bootstrap and teardown documentation exist. Terraform tooling validation/plan and actual cloud deployment were not performed. No AWS/Azure access is required for the current local demo.

Relevant implementation:

- `infra/terraform/state-bootstrap/`
- `infra/terraform/aws-platform/`
- `infra/terraform/README.md`
- `.github/workflows/publish-images.yml`
- `.github/workflows/deploy-platform.yml`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Terraform configuration validates; the reviewed plan has bounded cost and protected state/storage.
- [ ] OIDC grants narrow short-lived permissions to trusted workflows.
- [ ] Teardown instructions state retained data/state and prevent accidental loss.
- [ ] Terraform provisions hosting, Ansible configures it, CI/CD delivers releases, workers manage developer resources.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Run fmt/validate and inspect provider versions/backend settings without live mutations.
2. Review least-privilege IAM/OIDC, networking, protected persistent storage and cost/teardown behavior.
3. Only after an explicit authorized account/budget is available, plan/apply an isolated target and hand it to Ansible/CI.

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

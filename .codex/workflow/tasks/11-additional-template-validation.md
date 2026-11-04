# 11 — Node and ASP.NET template validation

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 11 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Simple; small scope; P4.
- **Feature status:** Verification / bounded fixes.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** No product design decision expected; required runtimes must be available. Missing tools are an unexecuted check, not a pass.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** [github-template-delivery](09-github-template-delivery.md)
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Validate additional language templates against the same operational contract after FastAPI.

Node and ASP.NET templates exist. One generated Node test passed on local Node 26.7, differing from its pinned 24.13.0. A reusable .NET CI workflow was added; dotnet was unavailable and no .NET build acceptance is recorded.

Relevant implementation:

- `templates/nodejs-http/`
- `templates/aspnet-core/`
- `.github/workflows/reusable-ci-node.yml`
- `.github/workflows/reusable-ci-dotnet.yml`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Node checks pass on its declared version.
- [ ] ASP.NET restores/builds and its health smoke check passes on its declared SDK.
- [ ] Both templates reference existing approved workflows and document configuration/health behavior.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Use disposable generated projects and the declared language versions.
2. Run their checks/build/start/health contracts and correct bounded scaffold defects.
3. Escalate to a design task if secret/network/runtime contracts differ from the approved FastAPI model.

**Reasoning requirement:** Use a focused repair/verification workflow. No architecture redesign is expected; reclassify and explain any material scope expansion before proceeding.

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

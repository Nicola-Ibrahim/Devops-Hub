# 03 — Dashboard identity administration

## Current state

- **Updated:** 2026-11-04.
- **Recommended order:** 03 (original sequence; completed 01 removed); see [the ordered task index](README.md#deferred-implementation-tasks).
- **Authorized phase and scope:** backlog/specification from the user-requested task split. This record is not a request to start implementation or external operations.
- **Classification:** Design required; medium scope; P1.
- **Feature status:** Missing UI / existing API.
- **Next step:** select this task explicitly, reconcile its evidence with the working tree, and perform only its bounded next phase.
- **Open decisions:** Agree the internal onboarding/reset UX using existing operator capabilities; no public signup or social login.
- **Baseline:** `main@3e9b2048ad3014598ea6601aab3777c43eff1fdf`; extensive pre-existing staged/unstaged/untracked work, including partial implementation. Preserve it; recheck before edits.
- **Latest verification:** no new implementation checks were run for this split. Historical evidence and unverified areas are identified below.
- **Dependencies:** backend integration closeout (completed; see [completed prerequisites](README.md#completed-prerequisites))
- **Requirements and baseline:** [platform requirements](../../../docs/platform-requirements.md) and [completed prerequisites](README.md#completed-prerequisites).

## Goal and evidence

Project administrators manage internal memberships and users manage their sessions through the dashboard.

Internal identity APIs and PostgreSQL session tests exist. The Next.js resource/application dashboard and proxy exist, but complete membership/session/password administration and a real browser acceptance scenario are not recorded.

Relevant implementation:

- `frontend/src/components/dashboard.tsx`
- `frontend/src/app/api/v1/[...path]/route.ts`
- `backend/src/api/identity/browser.py`
- `backend/src/containers/browser_operations.py`

## Scope and invariants

- In scope: only the outcome and paths described here; narrow exact edit ownership at task start.
- Out of scope: other backlog tasks, unrelated refactors and automatic live provisioning/publishing/deployment.
- Preserve [AGENTS.md](../../../AGENTS.md), identity/platform boundaries, resource ownership, leases, quotas, retry/recovery state and private credentials.
- Use disposable resources for authorized execution. Never stage/commit, change production secrets, migrate shared databases or delete foreign resources under this record.

## Acceptance criteria

- [ ] Users can view/revoke sessions and change their own password.
- [ ] Authorized administrators manage memberships; last-admin and cross-project restrictions remain server-enforced.
- [ ] Cookie, origin and CSRF protections work; no credentials enter browser storage.
- [ ] A real browser completes the resource lifecycle and relevant administrative flows.

## Contracts and ownership

The coordinator owns this task's contracts and integration. Suggested component
ownership is the relevant implementation listed above; assign exact non-overlapping
files before delegation. Existing APIs/state must remain compatible unless this
task explicitly designs a contract change. Dependencies must be accepted or their
missing capabilities explicitly accounted for before dependent work.

## Plan and progress

1. Inventory current API contracts and select bounded UI slices: sessions/password, then project membership administration.
2. Define permitted actions and useful rejection/confirmation states.
3. Implement UI against existing APIs; propose backend contract changes separately if needed.
4. Verify with two projects and real browser interactions.

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

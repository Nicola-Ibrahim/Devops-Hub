# Platform authorization boundary

## Current state

- **Updated:** 2026-11-11.
- **Authorized phase and scope:** The user explicitly authorized implementation of this named task. Local code, tests and backend guidance were changed. Live provisioning, deployment, secret changes, staging and commit were not authorized.
- **Next step:** Continue separate PostgreSQL recovery/authorization acceptance in task 02; use the shared action policy for future platform endpoints.
- **Open decisions:** None. HTTP routes own early permission rejection; authenticated hosts recheck the same policy, and domain/persistence retain loaded-resource ownership and transactional invariants.
- **Baseline:** Clean `main` at `164b444d83e52100787e8f9bdf5be3679fa76b3d`; `git status --short --branch` reported `main...origin/main`; no staged, unstaged or untracked changes before this record.
- **Latest verification:** `pytest -q -m 'not postgres'`: 221 passed, 48 deselected, 40 subtests passed. Ruff, format, mypy and `git diff --check` passed. No live PostgreSQL/Docker operation was run.

## Goal and evidence

**Developer outcome:** HTTP callers are authenticated and checked for project, role and scope at the API boundary before dispatch. Platform application handlers concentrate on use cases and depend on domain objects and ports. Direct non-HTTP entrypoints remain protected, and resource ownership, quotas, leases, idempotency and audited credential retrieval cannot be bypassed.

**Observed facts:**

- `backend/AGENTS.md` already assigns HTTP authentication and project/role permission checks to `api/`, while requiring domain ownership and lifecycle rules for worker callers. `identity` owns users, sessions, tokens and membership; platform owns projects/resources. This is a cross-boundary contract clarification, not proof that current checks are correctly placed.
- `backend/src/api/dependencies.py` creates an `AccessContext`; `api/platform/routes.py` and `applications.py` pass it into typed platform module messages. `backend/src/containers/platform_module.py` authenticates again inside the platform transaction and replaces message access with a trusted context before dispatch. Browser project listing expands authenticated memberships in both route and host.
- `developer_platform/application/shared/project_access.py` checks project mismatch and scope; `workload_delivery/shared/policy.py` checks delivery scope; `resource_catalog/handler.py` checks catalog scope. Resource request, read, lifecycle, connection and workload handlers call these checks. `developer_platform/domain/access.py` defines actor/project/role/scopes; `application/shared/dto.py` re-exports it; `application/shared/permissions.py` defines four scopes.
- `developer_platform/infra/persistence/ledger.py` atomically validates project/environment, idempotency and quota under locks. `infra/persistence/lifecycle.py` filters by project and checks owner/admin before renew, delete and connection access. `infra/persistence/delivery.py` checks application owner/admin. `database_lifecycle/read_connection/handler.py` decrypts a secret only after an authorized repository read; persistence also checks readiness and records sensitive-access activity.
- `containers/application_host.py` authenticates an identity for delivery operations without an API route; resource workers use system operations without a developer access context. Webhook and public template messages also have different access rules in `containers/platform_module.py`.

**End-to-end trace:** A database request enters `api/platform/routes.py`, receives an API-derived context, reaches `PlatformHttpModule`, is reauthenticated within the request unit of work, then dispatches through `developer_platform/containers/module.py` to `submit_database_request/handler.py`. The handler checks project/write scope, validates catalog and idempotency, and asks the ledger repository to atomically accept intent under project/target quota locks. On failure the host unit of work rolls back; provider effects occur later through worker paths. A missing scope currently fails forbidden, a project mismatch is hidden as not found, and quota/idempotency failures stay distinct.

**Assessment:** The application is already transport-independent; using an actor value does not by itself make a handler impure. Repeated role/scope checks in handlers are a placement and consistency issue. Moving them only into FastAPI would allow direct module and host callers to bypass policy. Owner/admin checks on a loaded resource and atomic quota/lease rules are domain or persistence invariants, not HTTP permission checks.

**Assumptions and limits:** No external caller inventory beyond repository references was established. Static tracing does not prove every denial or transaction at runtime. Existing HTTP codes, cross-project hiding, CSRF, token scopes, membership freshness, audit and secret redaction are compatibility requirements.

## Scope and invariants

- **In scope and implemented:** Explicit per-message action policy in `developer_platform/authorization.py`; API rejection before dispatch; same policy in HTTP and delivery hosts; authenticated access replacement; removal of duplicate application scope checks and obsolete helpers; focused tests and backend guidance. Existing `AccessContext` remains in application messages where actor identity, project filtering and audit need it.
- **Out of scope:** New roles/scopes, identity redesign, frontend, schema migrations, new endpoints, provider changes, deployment or live resource operations.
- **Preserve:** Same project mismatch/not-found and missing-scope/forbidden behavior where already public; token and browser authorization including selected project and membership freshness; owner/admin checks on loaded resources and applications; quota/idempotency/lease/revision rules; transactional revalidation; audited secret retrieval and redacted ordinary responses; CSRF/origin rules; worker and webhook identities; unit-of-work ownership.
- **Safeguards:** Never trust caller-supplied `AccessContext`; construct or replace it from verified identity. No generic “system admin” bypass for developer actions. Do not move ownership checks to a pre-load API lookup that races the final write. No secret values in tests, logs or task records.

## Acceptance criteria

- [x] Every registered platform message has an explicit action policy, including public templates and signed webhook exceptions; route checks precede module dispatch. Owner-required actions are identified in the matrix and checked after row load.
- [x] HTTP routes check project/role/scope before dispatch; the HTTP host authenticates again inside the operation transaction and replaces caller access. The delivery host authenticates before policy evaluation. Only the HTTP host constructs the private raw dispatcher; the public module DI binding resolves to the host.
- [x] Platform application handlers contain no HTTP/session/DI types or duplicate coarse scope checks. Domain/persistence still check loaded ownership, admission, lease, idempotency and readiness.
- [x] Project mismatch remains hidden as 404 and missing scope as forbidden; connection retrieval still requires its separate scope, owner/readiness check and audit. Identity freshness is re-evaluated by the existing host authentication path; no live identity DB run was performed.
- [x] Isolated policy/API/host tests cover allow/deny, owner/admin, project mismatch, scope types, direct dispatch and rollback; existing quota/idempotency and frozen OpenAPI tests pass in the non-PostgreSQL suite. PostgreSQL concurrency, live provider and real membership/revocation acceptance are deferred and not claimed here.

## Contracts and ownership

- **Identity to API/host:** Identity supplies verified principal, active membership and token scopes. The API maps those to a trusted platform actor; platform application/domain never imports identity, FastAPI or request objects. The HTTP host repeats verification inside its transaction to avoid stale or fabricated access.
- **Permission policy:** Define a single versioned-in-code action-to-scope/project/role matrix, with API evaluation for HTTP and a transport-neutral evaluation at each non-HTTP developer-action host. Keep the policy as pure functions or a narrow port; no database reads in a static scope rule. Do not let API and host maintain diverging copies. Public template reads, signed webhooks and system resource workers require separate named policies, not an implicit developer actor.
- **Domain ownership:** A resource/application loaded under project filtering still checks owner or admin where the operation requires it. Repositories keep project predicates, locks, quota/idempotency constraints and audited connection access. The API can reject early but is not the final authority for a mutable row's ownership or state.
- **Error contract:** Use typed authorization/domain failures below HTTP and translate at the API edge. Preserve current stable codes and status behavior; do not embed HTTP status in new domain policy types.
- **Transaction:** The outer HTTP or worker host opens the operation boundary and invokes `SqlAlchemyUnitOfWork.run`; only the unit of work commits/rolls back/closes. Authorization that depends on current membership or mutable resource state is rechecked in the same operation boundary. No provider effect inside the transaction.
- **File ownership for later implementation:** Coordinator owns the permission contract, `backend/src/containers/`, cross-context mapping, task record and integration. API coder owns `backend/src/api/platform/` and focused HTTP tests. Platform coder owns `backend/src/developer_platform/application/`, `domain/`, `infra/` and focused non-HTTP/domain tests only after the contract is fixed. The coordinator sequences any shared file edits; coders are not alone in the workspace and preserve others' edits. Reviewer checks the integrated diff read-only.

## Plan and progress

1. **Completed — inspect and characterize:** Reused the recorded investigator trace, checked clean `main@164b444d`, existing route/module/host callers and older handler-level denial tests. Those tests were updated to exercise the new boundary rather than retain obsolete expectations.
2. **Completed — contract first:** Added pure `developer_platform/authorization.py` with one explicit message-to-scope/project/role matrix, public exceptions and owner-required metadata. It preserves 404 on project mismatch, existing forbidden errors and delivery error semantics. Removed `ALL_SCOPES` from application into this boundary contract.
3. **Completed — hosts/API:** API routes authorize each typed message before module dispatch. HTTP host reauthenticates and replaces access before the same check. Delivery host checks authenticated access; the application-resource system bridge verifies owner membership from the DB before using its scoped system action. Raw dispatcher is private and only constructed by the authenticating HTTP host.
4. **Completed — application cleanup:** Removed duplicate coarse permission checks from catalog, resource request/read/lifecycle and delivery handlers and removed obsolete helper modules. Retained actor/project context for persistence filtering and audit; loaded owner checks and transactional rules remain in domain/persistence.
5. **Completed — integration and review:** Added matrix, API denial, direct dispatch, host forged-claim/rollback and owner/admin checks; updated affected handler tests and backend guidance. Independent reviewer flagged raw dispatcher trust, then confirmed the private/internal wiring and host test resolved the externally reachable concern. No other confirmed issue remained.

Dependencies: This can follow completed task 02a's module contract. It should precede broad task 03 permission-facing dashboard/API changes; it does not depend on live provider acceptance in task 02. API and platform edits cannot be parallelized until the shared permission contract is fixed.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| `git status --short --branch`; `git rev-parse HEAD`; `git diff --cached --name-only` | Clean `main...origin/main`; `164b444d83e52100787e8f9bdf5be3679fa76b3d`; no staged files | Pre-plan baseline |
| `rg` and source reads across API, host, platform application/domain/infra and existing task records | Located duplicate scope checks, host revalidation, project/owner filtering, quota and secret gates | Read-only static trace; no runtime proof |
| `cd backend && .venv/bin/pytest -q -m 'not postgres'` | 221 passed, 48 deselected, 40 subtests passed | Includes focused API/policy/host checks and frozen OpenAPI; isolated only |
| `cd backend && .venv/bin/ruff check src tests migrations` | All checks passed | Static lint |
| `cd backend && .venv/bin/ruff format --check src tests migrations` | 298 files formatted | Static format |
| `cd backend && .venv/bin/mypy src` | No issues in 252 source files | Static type check |
| `git diff --check` | Passed | Tracked whitespace check; untracked files covered by Ruff/format |
| PostgreSQL/Docker | Not run | Requires isolated configured target; no live acceptance claimed |

Review status: `/root/authorization_review` independently reviewed the actual dirty tracked/untracked diff read-only. Its P2 concern about caller-supplied claims in direct raw dispatch led to a private dispatcher and a host forged-claim/rollback test. Follow-up found no externally reachable bypass or remaining confirmed issue. The reviewer ran no tests.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/authorization_trace` | Investigator role; explicit user request and workflow guidance | Read-only trace of platform application permissions, API/host callers, persistence and workers at clean `main@164b444d` | Confirmed dual API/host and application/persistence gates, worker distinction, transaction and secret paths; reported references, failure paths and open limits. No edits/tests/live calls. |
| `/root/api_permissions` | Coder role; explicit implementation assignment | Owned `backend/src/api/platform/routes.py`, `applications.py` and new focused API test; shared `main@164b444d` workspace | Added pre-dispatch checks; focused test 2 passed and Ruff passed. Coordinator integrated/verified. |
| `/root/application_permissions` | Coder role; explicit implementation assignment | Owned `backend/src/developer_platform/application/**` and new focused application test; did not edit shared contract or API | Removed duplicate coarse checks; focused test passed and Ruff/format passed. Reported six stale handler-denial tests; coordinator updated those tests at the new boundary. |
| `/root/authorization_review` | Reviewer role; read-only actual diff | Dirty tracked/untracked implementation against `main@164b444d` | Reported raw dispatcher trust concern; follow-up confirmed host-only reachability and resolution. No edits or runtime checks. |
| Coordinator | Shared contract, root hosts, integration, docs, task record | Cross-component integration on `main@164b444d` | Added policy/host gates and focused tests, resolved stale tests and review finding; ran full listed checks. |

## Handoff

- **Completed:** Permission contract, API/host gates, application cleanup, independent review, isolated verification and backend guidance.
- **Remaining limits:** No disposable PostgreSQL or live identity/provider operation was run; real membership/revocation freshness, concurrent quota and secret retrieval acceptance remain unproven by this refactor. No staging, commit or deployment occurred.
- **Next concrete action:** Continue task 02's isolated PostgreSQL recovery/integration acceptance before claiming live end-to-end behavior.

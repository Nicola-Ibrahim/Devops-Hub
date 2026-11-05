# Application service boundaries and use-case organization

## Current state

- **Updated:** 2026-11-05.
- **Authorized phase and scope:** Implementation and focused verification authorized by the follow-up request. Structural changes to identity and developer-platform application services, repository contracts, infrastructure adapters, DI and callers were made without live provisioning, deployment, migration, staging or commit.
- **Next step:** Run PostgreSQL/Docker lifecycle acceptance on explicitly disposable local targets when separately authorized and configured; keep this structural phase closed as code work with those runtime limits recorded.
- **Open decisions:** None for this refactor. "Edit" was interpreted as existing password/account/membership actions; HTTP payloads and status codes were preserved.
- **Baseline:** `main`, HEAD `2b8457fd127586c15b8d99980f818d2ad9fd836f`, ahead of `origin/main` by 2. The working tree has extensive staged and unstaged changes plus untracked context-container files from the preceding reorganization. Do not infer a clean baseline or overwrite them.
- **Latest verification:** `cd backend && .venv/bin/pytest -q -m 'not postgres'` passed: 189 passed, 48 deselected, 40 subtests passed. Ruff, format, mypy (137 source files) and `git diff --check` passed. No disposable PostgreSQL, Docker provider, migrations or deploy were run.

## Goal and evidence

**Developer outcome:** An engineer can find each business action in the owning bounded context's application layer, with its command/result nearby. Dishka providers only bind dependencies and construct services. Repository interfaces express business operations in the domain, while SQLAlchemy, I/O, security primitives, and provider effects have concrete implementations in context infrastructure. API and worker hosts invoke these services and own outer request/worker transaction completion.

**Source-backed facts:**

- `identity/containers/browser_operations.py` defines `BrowserIdentityService` with login, logout, session, password setup/change, user activation, and project membership actions. It constructs SQLAlchemy sessions, `SQLAlchemyBrowserIdentityRepository`, `SqlAlchemyUnitOfWork`, password/token adapters and performs application decisions. `identity/application/browser_identity.py` contains mostly static validation/presentation helpers; the business workflow is therefore largely in `containers`.
- `identity/application/browser_contracts.py` combines browser DTOs with `BrowserIdentityRepository` and `PasswordHasher` protocols. `identity/application/ports.py` contains API-token repository and I/O ports. `identity/application/dto.py` separates `IssueTokenCommand` from `identity/application/issue_token.py`; other token workflows are split between `application/` and `identity/containers/operations.py`.
- `developer_platform/containers/application_operations.py` defines `ApplicationDeliveryService`, constructs `SQLAlchemyApplicationDeliveryRepository` and `SqlAlchemyUnitOfWork`, authenticates callers, and coordinates worker claims/effects. `developer_platform/application/delivery.py` contains 684 lines mixing DTOs, repositories/provider protocols, request actions, webhook handling and worker execution.
- `containers/platform_http_operations.py` performs renewal, deletion, connection retrieval and activity queries using `SQLAlchemyResourceLifecycle` and ORM models; it also maps API schemas and authenticates requests. This leaves platform actions outside a platform application service.
- `developer_platform/application/requests.py` combines project registration, database request, catalog checks and ledger reads. `developer_platform/application/ledger.py` combines command/result DTOs with `PlatformLedgerRepository`. `developer_platform/application/lifecycle.py` combines provider/queue ports with job/result DTOs. `developer_platform/application/worker.py` already holds the provider effect orchestration behind interfaces.
- Context SQLAlchemy repositories exist under `identity/infra/persistence/` and `developer_platform/infra/persistence/`; `identity/containers/providers.py`, `developer_platform/containers/providers.py`, `containers/http_providers.py` and `containers/factory.py` assemble the current graph. API contracts live in `api/identity/`, `api/platform/`, and `api/dependencies.py`.
- `developer_platform/infra/application_runtime.py` defines `ApplicationDatabaseBindingResolver`, an I/O contract placed beside its concrete runtime adapter. The contract should move inward to an application port while the runtime implementation stays in infra.

**Assessment:** The placement of application behavior in `containers` and direct ORM use in root HTTP operations are boundary defects. The exact granularity of action files is an organization choice: keep a command/result with its action, but do not multiply thin forwarding classes or break a cohesive workflow solely to obtain one class per endpoint. A transaction cannot roll back a Docker/GitHub effect; durable intent, guarded effect execution and reconciliation must remain separate.

**Assumptions:** Existing HTTP routes and stored schema are intended to remain compatible. Login/logout/edit mean existing internal browser identity and user administration actions; this plan does not invent profile editing or social login. Current code presence is not evidence of runtime acceptance.

## Scope and invariants

- **In scope:** Identity browser and API-token use cases; platform project/catalog/database lifecycle and application delivery use cases; repository/port placement; context infra implementations; Dishka bindings; API/worker caller updates; focused architecture, contract and behavioral checks during a later authorized implementation.
- **Out of scope:** New product features, frontend redesign, database schema migration unless an implementation finding proves it necessary, new providers, live provisioning, deployment, staging/commit.
- **Preserve:** Existing route paths, request/response shape and error semantics unless a specific incompatible contract is approved; identity/project authorization, idempotency, quotas, lease limits, secret redaction, audit, CSRF/origin checks, login throttling, durable worker claim/heartbeat/retry/recovery, and resource ownership. Keep `identity` and `developer_platform` independent. API handlers remain thin.
- **Safeguards:** No live resource effects or secret disclosure during planning. In implementation, use isolated verification; never log or return credentials in ordinary list responses. Keep transactions around database changes and durable worker state, not external provider effects.

## Acceptance criteria

- [x] Each implemented identity action (login, logout/logout-all, session authentication/selection/revocation, password change/setup, user creation/activation, membership management, API token issue/authenticate/revoke) has a discoverable, business-named application service or cohesive use-case module; its command/result is colocated with the action when useful. No speculative "edit" feature is claimed.
- [x] Each implemented platform action (project registration/read, catalog/read, database request/status/renew/delete/connection/activity, application creation/attachment/deployment/webhooks/worker processing) is owned by an application service or a clearly named orchestration component in `developer_platform/application/`. Large mixed modules are split by workflow without changing behavior.
- [x] Domain-owned repository protocols reside under each context's `domain/` with relevant domain entities/value objects; concrete SQLAlchemy repositories/mappings remain in that context's `infra/persistence/`. Technical I/O ports used by application workflows may remain in `application/ports` when they are not domain repositories; their concrete I/O implementations live in `infra/`.
- [x] Application services depend only on their own domain/repository protocols and other needed interfaces/value objects. They do not import API, Dishka, SQLAlchemy, context containers, concrete infra, sessions or units of work. Context application layers do not import each other.
- [x] Dishka providers bind interfaces to infra adapters and construct application services; they contain no validation, permission, lifecycle or workflow decisions. Composition/host modules own request identity projection, transaction commit/rollback, and any cross-context operation.
- [ ] Existing API and worker behavior is verified through focused identity, platform lifecycle, application delivery and DI wiring checks. Unit/fake-provider checks passed; PostgreSQL locking, live provider effects and restart recovery on a disposable target remain unverified in this refactor.

## Contracts and ownership

- **Service shape:** Business-named `execute(command, actor/context)` or a cohesive small set of closely related methods; immutable command/result types near the service. Services receive specific repositories, clocks, hashers/ciphers/generators and provider ports via constructors. Avoid generic service locators or passing Dishka/container/session/UoW to use cases.
- **Repository ownership:** `identity/domain/` owns identity repository protocols; `developer_platform/domain/` owns project/resource/application repository protocols. Protocol methods should describe business intent and return domain/application value objects, not ORM rows. Existing SQL repositories remain in `*/infra/persistence/` and implement these ports. Move pure records/value objects with the owning concept; do not move SQLAlchemy mappings into domain.
- **Transaction shape:** One host-managed DB transaction for an incoming operation where atomicity is required; use a request/worker scope and bind a session-backed repository to that scope. For login's expensive password verification and worker effects, preserve current bounded transaction/claim pattern; define the exact split before moving code. Any cross-context project registration must retain one atomic SQL transaction and authorization semantics.
- **Dependency direction:** A domain repository protocol cannot import command/DTO types from `application/`. Move the required business records into `domain/` or narrow the repository signature to domain concepts before moving the protocol; keep transport-specific DTOs in application/API.
- **HTTP contract:** `api/identity/` and `api/platform/` keep transport schemas and error translation; the host maps bearer/browser credentials to an authenticated actor and calls context services. Do not make application services depend on `RequestIdentity` or Pydantic models.
- **Worker contract:** Durable ledger/claim and effect guard semantics remain; a worker may invoke an application orchestrator behind ports, while concrete queue/provider/effect implementations and run loop remain infra/host concerns. Reconciliation remains idempotent after restart.
- **Ownership for a later implementation:** Coordinator owns shared contract, host composition (`containers/`), `api/`, task record, and integration. Identity coder owns `identity/application/`, `identity/domain/`, `identity/infra/`, `identity/containers/` only after the shared contracts are fixed. Platform coder owns the analogous `developer_platform/` paths. Shared infra changes, if any, are coordinator-owned and sequenced first. Coders share a dirty workspace and must preserve others' edits. A separate reviewer checks the actual diff.

## Plan and progress

1. **Completed — contracts:** Identity browser/token/project access repository protocols and pure records moved to `identity/domain/`. Platform ledger, delivery and resource lifecycle repository protocols/records moved to `developer_platform/domain/`; application compatibility exports preserve callers. The database-binding I/O contract moved into platform application.
2. **Completed — identity:** Login/password policy, browser sessions, account/password setup and membership actions moved to focused `identity/application/` modules. SQL/UoW browser host adapter moved to `identity/infra/browser_operations.py`; a compatibility import remains under identity containers. Existing short transaction sequencing and token file cleanup remain host responsibilities.
3. **Completed — platform resources:** Catalog, project registration, database request and ledger reads split into named application modules. `ManageDatabases` now owns renew/delete/connection/activity actions; context persistence implements its repository. Root HTTP operations only authenticate, complete the transaction and project HTTP views. Credential retrieval remains restricted and its result has a redacted repr.
4. **Completed — delivery:** Create, attach, deploy, read, retry, preview webhook and effect execution moved to named application modules. `ApplicationDelivery` remains an application-layer compatibility facade; the container `ApplicationDeliveryHost` handles SQL/worker transaction sequencing. SQL binding/worker queue adapters moved to platform infra. Cross-context resource bridge moved to root composition. Durable claim/effect/complete split and guard remain intact.
5. **Completed — DI/callers/docs:** Context providers bind repositories and actions; root provider supplies the cross-context resource bridge. API/worker callers and `backend/README.md` were adjusted. The import boundary checker now follows package initializer reexports and full transitive imports for core layers while checking host/API direct imports without attributing every dependency's SQL import to the caller.
6. **Completed — local verification and independent review:** See actual commands below. No live resource acceptance was attempted; the 48 PostgreSQL-marked tests were intentionally deselected without a verified disposable target.

**Decisions needing input:**

- Whether "edit" means a new user-profile edit action or only the existing password, activation and membership actions. Default for this plan: existing actions only, since adding behavior would expand product scope.
- Whether this refactor must preserve every current HTTP payload and status code. Default: yes; propose any necessary intentional contract change separately.

**Migration limits:** File moves and import changes can be reversed in source control; a database migration or changed external effect is outside this plan. Keep staged/unrelated changes intact. Do not combine this structural refactor with new schema or provider features.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| `git status --short --branch`, `git rev-parse HEAD` | Inspected; dirty staged/unstaged/untracked state recorded above | Baseline only |
| `rg`, `sed`, `wc` over backend source | Located services, protocols, concrete repositories, DI and callers | Read-only static evidence; no runtime proof |
| `cd backend && .venv/bin/pytest -q -m 'not postgres'` | 189 passed, 48 deselected, 40 subtests passed | API/DI/unit and fake-provider behavior; no PostgreSQL/Docker proof |
| `cd backend && .venv/bin/pytest -q -m 'not postgres' tests/unit/test_domain.py tests/unit/test_operation_lifecycle.py tests/unit/test_manage_databases.py tests/unit/test_request_api.py` | 61 passed, 33 subtests passed after final authorization helper change | Focused domain/lifecycle/API checks; no SQL locking/provider proof |
| `cd backend && .venv/bin/ruff check src tests migrations` | Passed | Static lint |
| `cd backend && .venv/bin/ruff format --check src tests migrations` | Passed, 173 files formatted | Formatting only |
| `cd backend && .venv/bin/mypy src` | Passed, 137 source files | Static typing |
| `git diff --check` | Passed | Tracked whitespace only; untracked files checked by lint/format/mypy |
| PostgreSQL, Docker, migration and deployment acceptance | Not run | No verified disposable target or authorization for live provisioning/deploy |

Review status: independent read-only review by `/root/application_boundaries_review` on the actual working tree. Initial finding about grouped delivery actions was addressed; re-review found it resolved and no confirmed authorization, behavior or import-cycle regression. A final incremental review confirmed the extracted resource owner policy preserved the prior 404/403 distinction. Source review cannot establish live provider acceptance.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/application_services_trace` | `investigator`, user request and `.codex/workflow/README.md` | Read-only trace of both application layers, context/root containers, API/worker callers at HEAD `2b8457f` plus dirty working tree | Found browser and delivery workflows in containers, direct lifecycle SQL in root HTTP operations, I/O port in platform infra, and existing token delivery cleanup/worker retry safeguards. No edits or runtime checks. |
| `/root/identity_services` | `coder`, user request and AGENTS/workflow role | Owned `backend/src/identity/**` and focused identity tests at dirty `main@2b8457f`; preserved shared edits | Moved identity repository contracts, browser use cases and SQL host adapter; Ruff/format/mypy passed for owned paths; focused identity tests 19 passed. No live DB. |
| `/root/application_boundaries_review` | `reviewer`, independent read-only role | Reviewed actual dirty-tree identity, platform lifecycle, delivery/DI, and checker changes at `main@2b8457f` | Initial delivery grouping finding addressed; re-review found named actions resolved and no confirmed security/contract regression. No edits or live checks. |

## Handoff

- **Completed:** Contract-first service/adapter reorganization, compatibility wiring, docs update, static and non-PostgreSQL checks, and independent source review.
- **Remaining:** Disposable PostgreSQL/Docker lifecycle verification, including actual credential retrieval, duplicate request, lease extension/deletion, worker restart and cleanup, under the separate resource acceptance task. No live acceptance is claimed here.
- **Next concrete action:** Use the existing PostgreSQL recovery/acceptance task with a verified disposable local target when authorized; do not infer it from this refactor's unit results.

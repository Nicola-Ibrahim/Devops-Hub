# Context module dispatch for identity and developer platform

## Current state

- **Updated:** 2026-11-11.
- **Authorized phase and scope:** The user explicitly authorized implementation of this named task. Local code, docs and isolated checks were changed; live provisioning, deployment, secret changes, staging and commit were not authorized.
- **Current state:** Implementation complete in the working tree; independent review findings resolved. No live PostgreSQL/Docker acceptance is claimed.
- **Next step:** Continue separate PostgreSQL recovery acceptance in task 02; use this module contract for later API work.
- **Open decisions:** None for this internal refactor. Explicit registration and existing HTTP contracts remain the chosen contract.
- **Baseline:** `main` at HEAD `2b03387`, ahead of `origin/main` by one commit. The planning baseline was clean; implementation files are now modified/untracked. The task index was already modified before implementation; preserve unrelated work.
- **Latest verification:** `pytest -q -m 'not postgres'` passed (211 passed, 48 deselected, 40 subtests); Ruff, format, mypy and `git diff --check` passed after the final correction.

## Goal and evidence

**Developer outcome:** Every identity and developer-platform business API endpoint submits a typed command to `module.execute(...)` or a typed query to `module.query(...)`. Routes do not import, select, construct or inject use-case handlers. The owning context registers which handler serves each message, and the HTTP or worker host retains transaction completion. Health and metrics endpoints are host facilities outside these business modules.

**Observed facts:**

- `backend/src/api/platform/routes.py` directly injects `ReadCatalogQueryHandler` and `PlatformRequestQueries`; `backend/src/api/platform/applications.py` injects `ApplicationDeliveryOperations`; `backend/src/api/identity/browser.py` injects `BrowserIdentityOperations`; `backend/src/api/dependencies.py` injects `ReadCurrentIdentity`. The API does not currently call a context module.
- `backend/src/containers/factory.py` registers Dishka providers at startup. `identity/containers/providers.py`, `developer_platform/containers/providers.py` and `containers/http_providers.py` bind existing handlers, adapters and HTTP operations. Dishka resolves dependencies lazily within a scope; provider registration is not eager creation of every handler.
- `containers/platform_http_operations.py`, `containers/http_identity.py`, `containers/project_registration.py` and `identity/containers/operations.py` use `SqlAlchemyUnitOfWork.run()`. `identity/infra/browser_operations.py` and `developer_platform/containers/application_host.py` own more specialized session/transaction sequencing. `shared/infra/persistence/unit_of_work.py` commits on success and rolls back on failure.
- `backend/AGENTS.md` already permits typed context module facades and requires the outer host to own transaction completion. Application commands and handlers already exist in both contexts, but not all endpoints use a uniform one-message/one-handler shape.

**Assessment:** Importing a module class does not provide a request-scoped instance or session. A route needs a host-supplied module instance. A Python `Protocol` or abstract handler base documents the shape but does not discover its message type or register it with Dishka. Runtime package scanning would depend on import order and would hide the supported command/query set. Explicit per-context registration is the chosen design.

**Assumptions:** Existing route paths, schemas, errors, permissions, browser cookie/CSRF behavior, idempotency and worker behavior are compatibility requirements. This is an internal dispatch refactor, not a new product feature.

## Scope and invariants

- **In scope for later authorized implementation:** Typed identity/platform module contracts; command/query message types and result types where missing; explicit per-context handler registration and startup validation; request-scope resolution; API, host and affected worker caller migration; focused tests and architecture docs.
- **Out of scope:** Frontend changes, new endpoints, new authentication mechanisms, database migrations, provider changes, cloud operations, live provisioning or deployment.
- **Preserve:** API-owned authentication, role/project/scope checks and HTTP translation; domain invariants in application/domain; identity/platform separation; one owner for each transaction boundary; existing bounded login/password verification transactions; atomic cross-context project registration; durable resource intent, idempotency, leases, reconciliation and secret redaction.
- **Safeguards:** Never log commands containing credentials, tokens or connection strings. Module lookup cannot accept arbitrary class names or handler identifiers from clients. Never hold a database transaction across Docker/GitHub effects. Use disposable local targets only if separately authorized for live acceptance.

## Acceptance criteria

- [x] A route in each business API area calls only its context module's `execute`/`query` contract for business actions; no route imports/injects a concrete handler or business operation service. Cross-context authorization is composed at the HTTP host without importing one context's application layer into the other.
- [x] A new command/query is registered explicitly in its owning context. Duplicate message registrations, missing handlers and wrong command/query classification fail startup or a focused registration check with useful errors. Unknown messages fail closed without exposing internal names to clients.
- [x] Only the selected handler and its dependencies are resolved in the active operation scope. Application handlers remain unaware of FastAPI, Dishka, sessions, unit of work and HTTP schemas.
- [x] Existing HTTP paths, status codes, schemas, stable errors, permission outcomes, cookie/CSRF behavior and OpenAPI contract remain compatible in isolated tests. Denied requests do not execute their target use case.
- [x] Success commits and failures roll back under the existing host policy in isolated tests; browser login's bounded transactions and external effect separation remain intact. Existing worker hosts remain independent and were not changed.
- [x] Focused identity, platform, application delivery, DI/registration and HTTP tests pass; static typing, lint and format checks pass. PostgreSQL/Docker evidence is reported separately from unit/fake-provider evidence.

## Contracts and ownership

- **Module contract:** One application-facing `IdentityModule` and one `DeveloperPlatformModule`, each with async `execute(command)` and `query(query)`. Use concrete immutable message and typed result classes. Commands and queries stay beside their use-case handlers. Provide overloads or another static typing mechanism for supported messages; avoid a public `Any -> Any` API and do not pass API Pydantic models into application handlers.
- **Handler contract:** A small generic async `CommandHandler[Command, Result]` / `QueryHandler[Query, Result]` protocol or ABC documents `execute(message)`. Do not add a common base merely for package scanning. Existing handlers with different signatures are adapted or refactored within their own context; preserve business behavior.
- **Registry:** Each context owns an explicit mapping from message type to handler type/factory. The composition root installs the registries and validates complete, unique registrations and DI bindings. Registry keys are Python types from trusted code, never strings from HTTP. Resolution occurs once per dispatch inside the request/worker operation scope. No `__subclasses__`, filesystem scan, magic naming or global mutable handler registry.
- **DI and API:** Providers register infrastructure ports, handlers and module implementations; they contain no business decisions. Startup registers the graph; dependencies are created lazily. The HTTP host supplies the request-scoped module instance. `DishkaRoute` is optional for removing route-level `@inject`; plain FastAPI dependency wiring is acceptable if it supplies the same scoped module without a global instance or a route-level service locator. A dependency function that itself requests Dishka types may still require `@inject` under Dishka's documented FastAPI integration. The invariant is that routes depend only on context modules for business dispatch, not that a particular decorator is banned.
- **Transaction owner:** The HTTP/worker host opens the operation boundary and invokes `SqlAlchemyUnitOfWork.run()` or the existing specialized host sequence. The unit of work alone begins, commits, rolls back and closes its session. The inner context module selects and invokes a handler; it never commits, rolls back or owns a session. Where an API receives a module facade, host wrapping is applied outside the inner dispatcher. Preserve current short transaction splits for password hashing and external effects.
- **Ownership for implementation:** Coordinator owns shared contract, registry validation, root `backend/src/containers/`, API integration, docs and final verification. Identity coder may own `backend/src/identity/` and identity-focused tests. Platform coder may own `backend/src/developer_platform/` and platform-focused tests. Assign non-overlapping files and sequence shared contract before context edits; coders are not alone in the workspace and must preserve others' edits. Obtain an independent read-only review of the actual diff when available.

## Plan and progress

1. **Completed — investigate:** Inspected branch, tree, existing task index/template, API callers, DI providers, handlers and transaction hosts. No separate investigator ran; this was direct read-only coordinator investigation.
2. **Completed — contracts:** Added `shared.dispatch` with typed command/query bases, explicit registry validation and lazy selected-handler resolution. Added module messages, protocols and registry tests. Facade message envelopes live in `identity/application/module_messages.py` and `developer_platform/application/module.py`; existing business command/query and handler pairs remain together in their use-case folders.
3. **Completed — identity:** Registered token/browser messages, bound identity handlers through Dishka and moved identity routes/dependencies to `IdentityModule`. A separate short `TokenAuthenticationHost` session prevents preauthorization from consuming a platform request's unit of work.
4. **Completed — platform:** Registered resource, project, catalog and activity messages; moved routes to `DeveloperPlatformModule`. The HTTP host revalidates credentials inside its own request-scoped unit of work, while the inner module only dispatches. Browser project listing uses non-rotating session authentication to preserve CSRF validity.
5. **Completed for existing HTTP actions — application delivery:** Registered template, application and deployment messages and migrated their routes. Existing worker entrypoints use specialized worker hosts and do not dispatch these HTTP message types; no worker behavior was changed.
6. **Completed — integrate and verify:** Removed superseded HTTP operation facades; updated backend guidance; ran isolated tests, frozen OpenAPI check, Ruff, format, mypy and diff whitespace check. Independent reviewer identified UoW reuse and browser CSRF rotation defects; both were corrected and the reviewer confirmed the corrections.

Dependencies: This contract refactor should precede task 03's dashboard identity/API integration. Task 02's PostgreSQL recovery acceptance can be completed before or after this refactor; repeat only affected checks if the dispatch path changes. No implementation authorization is inferred from this record.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| `git status --short --branch`; `git rev-parse --short HEAD` | `main...origin/main [ahead 1]`; `2b03387` | Planning baseline; worktree now contains this implementation and pre-existing task-index changes |
| `rg` and source reads over API, providers, hosts and handlers | Confirmed direct API injection, current DI wiring and transaction call sites | Static baseline inspection |
| `cd backend && .venv/bin/pytest -q -m 'not postgres'` | 211 passed, 48 deselected, 40 subtests passed | Includes dispatch, DI, frozen OpenAPI, API, boundary and lifecycle tests; no live PostgreSQL/Docker proof |
| `cd backend && .venv/bin/ruff check src tests migrations` | All checks passed after final correction | Static lint |
| `cd backend && .venv/bin/ruff format --check src tests migrations` | 295 files formatted | Static format |
| `cd backend && .venv/bin/mypy src` | No issues in 253 source files | Static types |
| `git diff --check` | Passed after final correction | Whitespace only |
| TestClient smoke with unavailable DB | `/health/live` 200, unauthenticated `/api/v1/me` and `/api/v1/catalog` 401, `/api/v1/templates` 200, unauthenticated webhook 400 | Process wiring and fail-closed responses only; no live DB/provider |

Review status: `/root/module_review` independently reviewed the actual dirty-tree diff read-only. It reported two confirmed P1 defects: token preauthorization consumed the platform request-scoped UoW, and browser project listing rotated CSRF without returning it. The coordinator corrected both; reviewer follow-ups confirmed resolution and found no remaining confirmed issue. No independent runtime tests were claimed by the reviewer.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/identity_finish` | Coder role, assigned identity files and focused tests | Identity context on `main@2b03387`; preserved other edits | Completed identity module/registry work; focused tests: 3 passed; Ruff/format/mypy passed at handoff |
| `/root/platform_finish` | Coder role, assigned platform context files | Platform context on `main@2b03387`; no overlapping edits | Inspected partial platform contract and returned adapter blocker; made no edits; coordinator completed platform adapters |
| `/root/module_review` | Reviewer role, read-only diff | Actual dirty-tree implementation including untracked files | Found two confirmed transaction/CSRF defects; no checks run; independently confirmed both corrections |
| Coordinator | Integration, API/root containers, tests and task record | Cross-context composition and full flow | Integrated module routes, host transaction handling and independent reviewer fixes; ran listed checks |

## Handoff

- **Completed:** Typed context module dispatch, explicit registration, migrated business routes, documented transaction owner and isolated verification.
- **Remaining limits:** PostgreSQL/Docker integration and real database provisioning were outside this refactor's checks and remain in task 02. No staging, commit, deployment or live resource operation occurred.
- **Next concrete action:** Continue task 02 for live PostgreSQL recovery acceptance; use the implemented module contract for task 03 API/dashboard work.

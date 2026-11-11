# Infrastructure composition and context module boundaries

## Current state

- **Updated:** 2026-11-11.
- **Authorized phase and scope:** User authorized implementation of this internal composition refactor. Implementation and isolated verification are complete in the working tree. Live resources, deployment, secret changes, staging and commit were not authorized.
- **Next step:** Continue task 02's disposable PostgreSQL/Docker recovery acceptance separately; use the new import paths for subsequent backend work.
- **Open decisions:** None blocking. Keep an explicit, startup-validated message registry; Dishka resolves handler dependencies but does not infer which message belongs to which handler. If a future requirement demands convention-based discovery, evaluate it separately.
- **Baseline:** `main` at `c74bc4d3ab2843bf4c744610248da38eeae05384`. Initial `git diff --cached --stat` was empty; prior CQRS source/test edits and new message files were unstaged/untracked. During implementation the index showed staged changes, including earlier CQRS work and identity files, without any stage command by the agents. The coordinator left the index untouched and preserved those changes. New package relocations are working-tree edits.
- **Latest verification:** Non-PostgreSQL suite: 221 passed, 48 deselected, 40 subtests. Ruff/format/mypy and `git diff HEAD --check` passed. `uv build --wheel` succeeded; the wheel contains the new infra entrypoint/composition/worker packages and no legacy containers packages. No live PostgreSQL/Docker acceptance was run.

## Goal and evidence

**Developer outcome:** The HTTP API imports each bounded context's typed `Module` contract and sends commands or queries without selecting handlers. Each context owns its application behavior and infrastructure bindings. Dishka constructs only the selected handler in the active operation scope. DI files contain provider declarations and adapter bindings; HTTP transaction hosts, worker loops, metrics, registries and compatibility exports have explicit homes under infrastructure or their owning API boundary.

**Observed facts:**

- `backend/src/developer_platform/application/module.py` is the platform module protocol. `backend/src/containers/http_providers.py` binds it to `PlatformHttpModule`; `backend/src/containers/platform_module.py` authenticates, replaces caller access, owns `SqlAlchemyUnitOfWork.run()`, and calls the inner dispatcher. `backend/src/developer_platform/containers/module.py` holds the explicit command/query registry and uses `container.get(handler_type)`. `backend/src/developer_platform/containers/providers.py` registers the handler types and ports. Thus handlers are already resolved lazily; providers do not eagerly instantiate the full graph.
- `backend/src/identity/containers/module.py` similarly owns a registry and several adapter handlers around identity infrastructure. `identity/containers/providers.py` registers them. The same folder concern applies to both contexts.
- `developer_platform/containers/` contains two re-export-only files (`application_bindings.py`, `worker_queue.py`), metrics rendering/authentication, a worker host, two worker process entrypoints, a registry, a host callable type, and a 386-line provider file. These are distinct responsibilities. `backend/src/containers/` combines the cross-context composition root, HTTP host, authentication, project registration bridge, schema registration and ASGI startup.
- `developer_platform/containers/resource_worker.py` builds its queue, Docker provider and worker handler directly; `application_worker.py` resolves `ApplicationDeliveryHost` from Dishka. `application_host.py` also retains HTTP-style methods and a service facade. Their transaction/effect behavior needs characterization before changing construction.
- Existing callers include `backend/pyproject.toml`, `backend/Dockerfile`, `compose.yaml`, Alembic `backend/migrations/env.py`, `scripts/dev/packaged_acceptance.py`, backend docs and tests. `backend/tests/unit/test_boundaries.py` currently hardcodes `containers` as a root and restricts imports into `identity/infra` and `developer_platform/infra` from API and other contexts.

**Assessment, not proven runtime behavior:** The current layout makes composition hard to navigate. Moving every file under a context's `infra` directory unchanged would create forbidden API/cross-context imports and would hide transaction ownership. A responsibility-based relocation is needed. The previous 02a task records isolated dispatch checks, but those results predate the current dirty CQRS edits and do not verify this proposed move.

## Scope and invariants

- **In scope for later implementation:** Move context-local providers, registries and module implementations into `identity/infra/composition/` and `developer_platform/infra/composition/`; move cross-context composition, HTTP host adapters, worker entrypoints and observability adapters to purpose-named infrastructure/API host locations; remove obsolete re-exports after callers migrate; split oversized provider files by platform core, workload delivery and workers when they have distinct dependencies; update import-boundary rules, launch paths, tests and backend docs.
- **Out of scope:** Business behavior, API request/response changes, schema migrations, new resource types/providers, frontend, cloud provisioning, resource creation or deployment. Do not replace explicit dispatch with runtime package scanning or introduce a generic service locator in handlers/routes.
- **Preserve:** Separate identity and platform bounded contexts; application/domain free of Dishka, FastAPI and SQLAlchemy; API routes depend only on context module contracts for business actions; trusted identity refresh and project/scope checks; explicit public template and webhook policies; UoW-only commit/rollback; browser login's short transaction sequence; worker claim/effect/completion and retry; idempotency, leases, ownership, quota and credential redaction.
- **Safeguards:** No resource provisioning, Docker/GitHub/AWS call, migration, deployment, production secret change, stage or commit from this plan. Do not print credentials. Preserve the current working tree and avoid removing compatibility imports until all repo callers and entrypoints have moved.

## Acceptance criteria

- [x] No production source remains under the three old `containers` packages. Context provider files contain DI declarations/factories; HTTP transactions, worker loops and metrics have named infrastructure homes.
- [x] API business routes keep the typed `IdentityModule`/`DeveloperPlatformModule` contracts. The explicit registries and focused dispatch tests confirm selected-handler resolution and fail-closed classification/unknown-message behavior; no package scanning was added.
- [x] Focused DI resolution and import-boundary checks pass. Context infra imports neither API nor the other bounded context; cross-context bridges and HTTP adapters reside in root infra. Worker construction remains specialized as planned.
- [x] Isolated API/UoW/worker checks pass for the existing success, denial, failure and retry behavior. External provider effects remain outside SQL intent transactions. Live worker restart and PostgreSQL/Docker recovery remain unverified here and belong to task 02.
- [x] FastAPI, Docker/Compose, both worker, Alembic, script, test and README paths were migrated. The backend wheel builds and contains the new packages; no live acceptance is claimed.

## Contracts and ownership

- **Application contract:** Keep `identity.application.module.IdentityModule` and `developer_platform.application.module.DeveloperPlatformModule` as pure async `execute/query` interfaces. Messages and their business handlers stay in use-case folders. No route-level concrete handler import.
- **Dispatch contract:** Keep `shared.dispatch.HandlerRegistry` and `ModuleDispatcher` as the typed common mechanism. Put each explicit context registry and its concrete module adapter under that context's `infra/composition/` (for example `module.py` or `dispatch.py`). The registry maps trusted Python message types to handler types, validates uniqueness/classification, and asks Dishka to resolve only the selected type. Dishka handles constructor dependencies; it does not discover the mapping automatically.
- **Provider contract:** Place context-local SQL adapters, technical ports and use-case handler bindings in context `infra/composition/providers_*.py`, split by coherent capability. A provider may construct an adapter that needs settings; it does not authenticate requests, dispatch a message, commit, run workers or enforce business rules. Keep request/app scope explicit.
- **Outer host contract:** Introduce a root infrastructure host/composition area, such as `backend/src/infra/composition/` and `backend/src/infra/http/`, for the process container factory, cross-context authentication/project registration, HTTP module wrapper and ASGI startup. API-specific authorization/error translation remains at the API/HTTP boundary. Context `infra` must not import `api` or the other context. Put worker launchers under an infrastructure worker/entrypoint area; keep business worker handlers in application and concrete Docker/SQL adapters in context infra.
- **Transaction owner:** The HTTP or worker host opens the operation boundary and invokes `SqlAlchemyUnitOfWork.run()` or the existing specialized sequence. The unit of work alone begins, commits, rolls back and closes. The module dispatcher and DI providers never complete transactions. The worker's external effect phases remain outside the intent transaction.
- **Implementation ownership:** Coordinator owns shared dispatch contracts, the root `backend/src/infra/` host/composition layout, launch paths (`pyproject.toml`, Dockerfile, Compose), Alembic/script caller updates, architecture tests, docs and integration. A bounded identity coder may own `backend/src/identity/containers/` to `identity/infra/composition/` migration and identity-focused callers/tests. A bounded platform coder may own `backend/src/developer_platform/containers/` to `developer_platform/infra/composition/` plus platform worker/metrics extraction and platform-focused callers/tests. Sequence root contract/path decisions first; do not edit shared files in parallel. Reviewer checks the integrated diff read-only. All agents preserve other edits.

## Plan and progress

1. **Completed — trace and classify:** Reconciled the dirty `main@c74bc4d3` tree and reused `/root/di_trace` findings. Confirmed the HTTP path's trusted-access replacement/UoW and the application worker's claim/effect/completion phases.
2. **Completed — contract first:** Updated `backend/AGENTS.md` and import-boundary checks. Kept pure application module protocols and explicit registries. Chose root `infra/composition` for process wiring, root `infra/http` for HTTP auth/metrics/transaction host, root `infra/hosts` for cross-context bridges, root `infra/workers` for worker hosts, and context `infra/composition` for registry/DI. API metric auth moved to root HTTP; context metric projection stayed in platform infra.
3. **Completed — root/context relocation:** Moved root composition and host files, identity module/provider/token operations and platform module/providers. Split platform providers into core and delivery; root worker provider owns the application worker host binding. Removed compatibility re-exports and old packages after callers migrated. Removed unused HTTP-style methods and service facade from the application worker host; retained its claim/effect/completion behavior.
4. **Completed — integration:** Updated FastAPI/pyproject, Docker/Compose, worker, Alembic, packaged script, tests and README imports. Focused tests first exposed the old empty package directories, which were removed. Full non-PostgreSQL suite then passed. Reviewer found a missing `src/infra` wheel package declaration; coordinator fixed it, built the wheel and inspected its archive. Follow-up independent review found no remaining confirmed issue.

Dependencies: This follows the current 02a module dispatch contract and dirty CQRS cleanup. It is an internal architecture task; task 02's live PostgreSQL recovery and later dashboard work remain separate. Steps 3 and 4 must be sequenced where imports cross boundaries; identity and platform context-local moves can be parallel only after root contracts and non-overlapping file ownership are fixed.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| `git branch --show-current`; `git rev-parse HEAD`; `git status --short`; `git diff --cached --stat` | `main`, `c74bc4d3ab2843bf4c744610248da38eeae05384`; many unstaged/untracked backend edits; no staged diff output | Read-only baseline, not implementation verification |
| `rg --files`, `rg` caller search, source reads across API, modules, providers, workers, launch files and boundary test | Located provider/host/worker/registry mixing and external import-path callers | Static trace only |
| `cd backend && .venv/bin/pytest -q tests/unit/test_boundaries.py tests/unit/test_platform_module_dispatch.py tests/unit/test_identity_module_dispatch.py tests/unit/test_api_contracts.py` | 39 passed after removing old package directories | Import rules, DI dispatch and frozen OpenAPI; no database/provider effects |
| `cd backend && .venv/bin/pytest -q -m 'not postgres'` | 221 passed, 48 deselected, 40 subtests passed | Isolated HTTP, identity, platform and worker behavior; no live PostgreSQL/Docker |
| `cd backend && .venv/bin/ruff check src tests migrations`; `ruff format --check src tests migrations`; `mypy src` | All passed; 305 files formatted; mypy found no issues in 259 source files | Static checks after formatting the dirty integrated tree |
| `git diff HEAD --check` | Passed | Tracked staged and unstaged whitespace only; Ruff/format cover new source files |
| `cd backend && uv build --wheel --out-dir /private/tmp/devops-hub-wheel-review` | Built `devops_hub_backend-0.1.0-py3-none-any.whl` after sandbox cache access required approved escalation | Local package build only; no image publish/deploy |
| Wheel archive inspection with `.venv/bin/python` | Required `infra/http/asgi.py`, `infra/composition/factory.py`, `infra/workers/resource_worker.py` and both context module files present; no legacy `containers` packages | Packaging content check, not runtime deployment |

Review status: `/root/composition_review` independently reviewed the current staged, unstaged and untracked diff read-only. It found one P1 packaging omission (`src/infra` absent from wheel packages), which the coordinator fixed. The reviewer rechecked it and reported no remaining confirmed finding. The reviewer ran no checks.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/di_trace` | Investigator role; requested read-only trace under workflow guidance | Root/context containers, module resolution, one HTTP and worker path at `main@c74bc4d3` | Confirmed lazy handler resolution, explicit registry need, worker construction differences and context/host ownership issues; reported failures, assumptions and caller paths. No edits or checks. |
| `/root/identity_composition` | Coder role; explicitly requested by user and assigned bounded identity files | Owned `identity/containers/**` to `identity/infra/composition/**`, `identity/infra/token_operations.py` and two identity-focused tests at `main@c74bc4d3`; preserved other work | Moved identity registry/provider/token operation classes; focused Ruff/format/mypy and four dispatch tests passed. It did not stage or commit. Coordinator migrated remaining callers and removed compatibility wrappers. |
| `/root/composition_review` | Independent reviewer role; workflow guidance and user request | Read-only review of actual staged/unstaged/untracked diff against task 02b at `main@c74bc4d3` | Reported missing `src/infra` wheel package declaration; confirmed correction and no remaining finding. No edits or checks. |
| Coordinator | System-design, backend-development and api-development skills | Owned root/platform composition, launch paths, docs, shared boundary checks, integration and task record | Moved root/platform files, split providers, removed stale worker facade, integrated imports, resolved package finding, ran listed checks and wheel inspection. No stage/commit/live effects. |

## Handoff

- **Completed:** Infrastructure composition relocation, handler/Module wiring, packaging correction, docs, isolated checks and independent review.
- **Remaining limits:** No disposable PostgreSQL/Docker run, real worker restart or provisioned database verification. Existing task 02 owns that acceptance; remote/cloud deployment is separate. Current staged changes were observed but not changed by the agents.
- **Next concrete action:** Continue task 02's isolated PostgreSQL/Docker recovery scenario when its explicitly configured disposable target is available.

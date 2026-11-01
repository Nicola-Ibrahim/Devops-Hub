# Backend boundaries: identity, provisioning and API

## Current state

- **Updated:** 2026-11-01, Europe/Berlin.
- **Authorized phase and scope:** the subsequent user request authorized the complete behavior-preserving boundary refactor described here. Implementation, integration and independent review are complete. No resource lifecycle features were added. Existing staged index content and the frozen schema migration are preserved.
- **Next concrete step:** resume phase 2 of `backend-workflows.md` using the new context/application/API boundaries when that feature work is requested.
- **Unresolved decisions:** none blocking the design. Package structure, dependency direction, identity/project ownership, audit handling and migration strategy are decided below. Server/SSO decisions remain outside this refactor.
- **Baseline:** `main`, HEAD `39a2d874822786bf8925173119a3abec629ea23d`. At investigation and implementation start the phase-1 backend/guidance was staged (47 changed files), with no unstaged changes and this planning record untracked. The refactor now appears as unstaged moves/deletions/edits and new files. The staged-index binary diff fingerprint matches the captured implementation-start fingerprint; no index mutation occurred.
- **Latest verification and limits:** final isolated PostgreSQL suite **100 passed, 33 subtests passed**; Ruff, formatting, strict mypy, lock consistency, package build and installed-wheel smoke passed. Captured OpenAPI is exactly equal, the 11-table metadata has no migration differences, and `0001_foundation.py` is byte-for-byte unchanged. Independent review found an import-test re-export gap; it was corrected and independently re-reviewed. Local checks used Python 3.13.0/PostgreSQL 16.2; hosted CI and its Python 3.12/PostgreSQL 18 runtime were not exercised. One existing Starlette/HTTPX deprecation warning remains. No live/shared provisioning, deployment, production-secret changes, staging or commits occurred.

## Goal and evidence

Make the current backend understandable through explicit identity and resource-provisioning contexts, each with its own domain rules, application workflows and infrastructure adapters. Put the HTTP API in `backend/src/api/`, outside either context. Preserve the existing phase-1 behavior and schema while creating clean seams for the upcoming resource workflows.

### Confirmed current problems

| Evidence | Current responsibility and required correction |
| --- | --- |
| `backend/src/platform_api/api/auth.py:19-65`, `Principal/current_principal` | An HTTP dependency defines the principal, fingerprints credentials, executes ORM joins and checks identity policy. Move authentication orchestration into identity application code and SQL into identity infrastructure. |
| `backend/src/platform_api/identity.py:6-10` | Identity groups provisioning permission names with HMAC code. Provisioning owns permission semantics; identity handles opaque registered grants and token policy. |
| `backend/src/platform_api/admin.py:25-109`, `issue_token/revoke_token` | Policy, identity creation, transaction coordination, audit insertion and private file delivery are mixed. Extract use cases, persistence and delivery adapters; leave CLI parsing/presentation at the outer boundary. |
| `backend/src/platform_api/bootstrap.py:31-116`, `create_app` | Composition, readiness SQL, middleware and all routes share one function. Separate wiring, technical readiness and transport handlers. |
| `backend/src/platform_api/api/dependencies.py:7-9` | API dependencies expose SQLAlchemy sessions. Provide configured application use cases and authenticated values instead. |
| `backend/src/platform_api/adapters/persistence/models.py:40-224` | Identity and provisioning tables plus audit infrastructure share one model module. Separate model ownership while retaining one technical metadata registry. |
| `backend/src/platform_api/api/schemas.py:18-86` | Identity, provisioning and common transport DTOs share a file. Split by HTTP concern; keep Pydantic at the API boundary. |
| `backend/src/platform_api/domain/leases.py` and `domain/resources.py` | These already contain pure resource rules. Relocate them into provisioning without redesigning their behavior. |
| `backend/tests/integration/test_foundation_postgres.py:31-40` | Integration setup monkeypatches the bootstrap engine factory. Replace this coupling with explicit composition inputs while retaining real PostgreSQL verification. |

The foundation has health, identity and an empty catalog. Resource command routes, provider execution, a worker and frontend do not exist yet. A directory refactor must not be described as adding them.

## Requirements and scope

### Functional requirements

- **R1 — Identity ownership:** identity owns users, project identity namespaces, memberships, project-bound tokens, token policy, authentication, issuance and revocation. It must be testable without importing provisioning.
- **R2 — Provisioning ownership:** provisioning owns resource/catalog concepts, leases, lifecycle rules, quotas, reservations, operations, resource connection secrets and provider coordination. It must be testable without importing identity internals or receiving raw bearer tokens.
- **R3 — Application layer:** each context exposes explicit use cases coordinating pure rules and injected I/O capabilities. ORM queries, files, cryptographic key access and provider calls stay in infrastructure implementations.
- **R4 — API separation:** `backend/src/api/` owns HTTP schemas, routers, bearer extraction, status/error mapping and request middleware. It delegates behavior to application use cases.
- **R5 — Composition:** an outer runtime package constructs settings, engines, adapters and use cases, and controls their lifetimes. Application modules must not find dependencies through a service locator or global engine.
- **R6 — Preserve contracts:** HTTP paths, payloads/statuses, authentication and credential safety, CLI command/options, schema revision and existing database objects remain compatible as specified below.
- **R7 — Enforce boundaries:** automated import-contract checks and fake-port application tests must detect new coupling rather than merely documenting the folders.

### Nonfunctional requirements and safeguards

- Remain a single installable Python backend and PostgreSQL control plane. Two logical contexts do not imply separate services or databases.
- Preserve the Python/FastAPI/SQLAlchemy/Alembic stack, local Docker-first product direction and future Next.js consumer contract. No cloud account or external identity provider is introduced.
- Preserve all existing lease, cancellation, tombstone and secret safeguards. No rewrite of verified domain rules, change to policy defaults or new API/provider behavior is part of this refactor.
- The original planning request authorized no code/data changes. The subsequent implementation request allowed this refactor and its fake-adapter/disposable local PostgreSQL verification; shared databases and resource provisioning remain outside scope.
- Do not add empty future subsystems, generic repositories, event buses, aggregate frameworks, shared business models or a general DI container. Introduce only abstractions required by the use cases being extracted.

### Out of scope

Resource command implementation, worker/provisioner behavior, frontend development, SSO/password registration, new resource types, separate database schemas/services, schema migration, and the historical CLI/Ansible fixes remain in their existing implementation phases.

## Architecture decision and dependency direction

Use two bounded contexts with explicit application/infrastructure layers inside the existing modular monolith. Apply domain-driven naming and ownership, retaining ordinary Python workflows and small pure rule models.

The application needs infrastructure **capabilities**, but must depend on its own ports rather than import concrete infrastructure modules. Infrastructure implements those contracts; runtime wiring connects the two. This resolves the requested application/domain/infrastructure separation without making workflows depend on SQLAlchemy, filesystem APIs or Docker.

```text
HTTP API / admin CLI
       |
       v
context application -----> context domain
       |
       v
application-owned ports <----- context infrastructure
                                      |
                                      v
                              technical infrastructure

runtime composition imports API, applications and adapters to wire them.
Identity and provisioning do not import each other.
```

### Proposed source layout

```text
backend/src/
  api/
    app.py                     # HTTP assembly from already configured services
    dependencies.py            # typed use-case access and bearer extraction
    errors.py                  # safe transport error mapping
    middleware.py              # request ID and no-store behavior
    identity/{routes,schemas}.py
    provisioning/{routes,schemas}.py
    health/{routes,schemas}.py
  identity/
    contracts.py               # immutable public authentication result
    domain/                    # identity policy and safe errors, no ORM
    application/
      authenticate.py
      issue_token.py
      revoke_token.py
      dto.py
      ports.py
    infrastructure/
      persistence/{models,store,unit_of_work}.py
      tokens.py                # peppered HMAC and secure token generation
      credential_file.py       # exclusive private delivery and compensation
  provisioning/
    domain/                    # relocated leases/resources/errors
    application/
      catalog.py               # current empty catalog and access policy
      permissions.py           # resource/catalog permission vocabulary
      dto.py                   # local access context and workflow results
      ports.py                 # only ports currently consumed
    infrastructure/
      persistence/models.py    # resource/operation/quota/secret records
  platform_infrastructure/
    persistence/{base,database,audit}.py
    readiness.py               # schema probe and safe technical outcomes
  platform_runtime/
    settings.py
    composition.py             # explicit dependency construction/lifetimes
    schema.py                  # explicit full metadata registration
    http.py                    # production create_app factory
    cli.py                     # platform-admin argument parsing/presentation
```

Names describe intended responsibilities, not mandatory one-class files. Combine tiny modules where that improves clarity without crossing these boundaries. Do not create a future provider/worker package until its implementation is authorized.

### Allowed imports

| Package/layer | May depend on | Must not depend on |
| --- | --- | --- |
| `identity.domain` | Its own pure code and standard library | Provisioning, API, runtime, infrastructure, ORM/frameworks |
| `identity.application` | Own domain, DTOs/ports and public identity contract | Provisioning, API, runtime, concrete infrastructure, FastAPI/Pydantic/SQLAlchemy |
| `identity.contracts` | Standard-library immutable values | Either context's ORM, API or runtime |
| `provisioning.domain` | Own pure rules and standard library | Identity, API, runtime, infrastructure, ORM/frameworks |
| `provisioning.application` | Own domain and DTOs/ports | Identity, API, runtime, concrete infrastructure, FastAPI/Pydantic/SQLAlchemy |
| Context infrastructure | Own context's application/domain and neutral technical infrastructure | Other context's models or internals, API, runtime |
| `api` | FastAPI/Pydantic, its transport code, identity public contract, context application interfaces/results and public pure enums/errors used in schemas/error mapping | ORM sessions/models, SQLAlchemy/Docker, files/cryptographic keys, concrete infrastructure, runtime |
| `platform_infrastructure` | Standard library and technical libraries such as SQLAlchemy | Context business/application rules, API, runtime |
| `platform_runtime` | API, both contexts, settings and technical infrastructure | No lower layer may import it |

Dependency arrows are imports, not the direction of runtime calls. Application-owned ports are implemented structurally; no infrastructure object is returned through them. Check both absolute and relative imports and indirect re-exports. Explicit model registration replaces dynamic package discovery.

## Domain ownership and contracts

### Identity and authorization

Identity owns the meaning of a user, project membership, token expiry/revocation and role. A project here is an identity namespace; provisioning owns budgets and resource policy keyed by its ID. Do not create a second shared Project entity or pass its ORM instance across boundaries.

`identity.contracts.AuthenticatedPrincipal` is immutable: user ID, project ID, token ID, role and granted scope strings. It contains no raw token, password hash, session or infrastructure handle. `Authenticate` reads a credential snapshot through a narrow identity store, fingerprints through an injected hasher, evaluates domain rules using an injected clock and returns this value. Invalid credentials, inactive users, absent memberships, revocation and expiry preserve the current safe rejection behavior.

Provisioning owns scope names such as `catalog:read`, `resources:read`, `resources:write` and `connections:read`. Identity stores registered scope strings without interpreting those resource actions. Runtime supplies the supported-scope allowlist to token issuance, preserving today's defaults and rejecting unsupported grants. The restricted admin CLI remains the only issuance/revocation interface.

The HTTP adapter maps the authenticated principal into a provisioning-owned `AccessContext` containing the necessary user/project IDs, role and scope values. Provisioning does not import identity and cannot authenticate a raw token. This trusted mapping is assembled by runtime and used for every future resource entry point; payload owner/project values cannot replace it. Future non-HTTP callers must obtain an equivalent authenticated context through an authorized host boundary. Request-time identity checks remain live; do not introduce a principal cache that bypasses revocation or membership removal.

### Identity application and ports

Extract three use cases: `Authenticate`, `IssueToken`, `RevokeToken`. They receive explicit collaborators at construction and return framework-free results or owning-layer errors. They hold no request or transaction state between calls.

Use only the necessary ports: an authentication reader returning a credential snapshot; a context-specific transaction boundary for user/project/membership/token/audit writes; token fingerprint/generation capabilities; a clock; and private credential delivery. Group related persistence operations within the transaction contract instead of creating a generic repository for every table. SQLAlchemy implementations convert records to identity-owned DTOs before returning.

For issuance, preserve the existing failure ordering: validate → create token and identity records in a transaction → write the credential through exclusive private delivery → commit. File-write failure rolls back database changes; failed commit attempts cleanup of the newly created file. Delivery returns an ownership receipt so compensation cannot remove an unrelated existing file. Cleanup failure must not hide the primary error or leak the credential. CLI owns the requested `Path`; application receives a delivery capability, not `Path`, `os`, a SQLAlchemy session or transport arguments.

Database and filesystem are not one atomic system: an abrupt process death or ambiguous commit may leave a private credential file requiring reissue/revocation. Document that limitation rather than claiming distributed atomicity. Normal no-overwrite/mode-0600/rollback/cleanup behavior must remain characterized. Keep HMAC inputs, hash encoding, pepper semantics, token shape/default lifetime, grant defaults and existing token validity unchanged.

### Provisioning application

Move current resource enums, lease policy and transition checks intact into `provisioning.domain`. Extract current catalog behavior into `ReadCatalog`, including `catalog:read` authorization and the empty result until an approved provider exists. API handlers only translate its result to the current public response.

Existing future resource request/view/renew DTOs remain in `api.provisioning.schemas`. Application commands/results will use dataclasses or equally framework-free values when their phase is implemented. The refactor must not register fake resource routes, fabricate readiness, implement a worker, or allocate infrastructure.

### Persistence, audit and migrations

Preserve a single technical SQLAlchemy Base/MetaData with the current naming convention in `platform_infrastructure.persistence.base`. Each context defines only its own ORM records and imports this neutral Base. `platform_runtime.schema` explicitly imports both model modules and technical audit records before exposing the complete metadata to Alembic and integration checks. No context imports the other's models to make foreign keys resolve.

- Identity records: `users`, `projects`, `memberships`, `api_tokens`.
- Provisioning records: `resources`, `operations`, `idempotency_records`, `quota_budgets`, `reservations`, `resource_secrets`.
- Technical audit record: `audit_events`. Its optional resource linkage and identity foreign keys remain database constraints expressed by table-name strings.

Each context's write transaction exposes a context-owned audit operation. Its infrastructure implementation maps that event into the shared audit table using the **same SQLAlchemy session and transaction** as the owning write. Neutral audit persistence knows primitive IDs/action/outcome values, not identity/provisioning business rules. No event bus, second audit connection or identity dependency on provisioning is introduced.

Database foreign keys across contexts remain intentional physical coupling in this monolith. These code boundaries do not establish independently deployable databases. Stable IDs are retained; user/project deletion and any future context extraction require a separately designed referential/retention policy.

Keep `backend/migrations/versions/0001_foundation.py` byte-for-byte unchanged, along with revision `0001_foundation`, table/column/constraint/index names and stored records. Model relocation requires no new migration. Update only Alembic environment imports and explicit registration. Verify the complete registry before comparisons so an unimported context cannot appear to be a set of dropped tables.

### API, runtime and failures

`api.app` assembles routers/middleware from typed, already configured use cases. Per-route dependencies obtain those use cases or immutable auth results; they never provide a SQLAlchemy session. A typed HTTP service bundle is acceptable at the adapter boundary, but application workflows must not look up services by names or read FastAPI app state.

`platform_runtime.http:create_app` constructs the production graph and controls engine disposal. Tests inject configured application collaborators into the HTTP factory or supply an explicitly owned engine to runtime composition; document whether the caller or runtime disposes it. Do not share a Session between requests. Preserve no-connect/no-migrate behavior for liveness and app assembly, and keep readiness as an explicit probe.

Readiness SQL lives in a technical adapter. Runtime translates its safe outcome into an API-facing probe result, so neither the API nor the infrastructure adapter needs to import the other. HTTP maps ready, missing/incompatible migration and database-unavailable results to the current safe health behavior. Do not put health checks in either business domain.

Domain/application errors are owned by the context defining their meaning. Infrastructure translates relevant external failures to application-owned failures and preserves causes privately. API maps authentication to 401, authorization to 403, domain validation to 422, persistence unavailability to 503, and unexpected failures to sanitized 500 responses. Preserve `WWW-Authenticate`, generated request IDs, `Cache-Control: no-store` on private responses and secret-free error bodies. Do not catch SQLAlchemy errors in the transport layer. No new universal Result/error framework is required.

## Data flows and compatibility

| Flow | Planned separation | Behavior to preserve |
| --- | --- | --- |
| `/api/v1/me` | Bearer extraction → identity Authenticate → public principal → identity HTTP view | Active membership, token expiry/revocation, role/scopes and stable response/status |
| `/api/v1/catalog` | Authenticate → host mapping to provisioning AccessContext → ReadCatalog → provisioning HTTP view | Scope rejection and exact empty-catalog response; no provider claims |
| `platform-admin issue-token` | CLI input → identity IssueToken → identity transaction/crypto/delivery adapters | Existing command/options, no plaintext stdout/logs, private file, rollback and audit |
| `platform-admin revoke-token` | CLI input → identity RevokeToken → identity transaction/audit | Unknown ID handling and idempotent repeated revocation |
| `/health/ready` | Health route → configured probe → technical SQL adapter | Expected revision and sanitized 503 on unavailable/not-ready state |
| Alembic | Migration environment → runtime schema registration → neutral metadata + context models | Identical schema and existing revision; no startup migration |

HTTP paths and JSON contracts remain unchanged. The `platform-admin` command/options and environment variable names remain unchanged. Packaging must include `api`, `identity`, `provisioning`, `platform_infrastructure` and `platform_runtime`; the current wheel includes only `src/platform_api`.

The canonical launch factory becomes `platform_runtime.http:create_app`; update the README, entrypoint metadata, imports and smoke checks together. Old `platform_api.*` Python paths are internal and may be retired in this pre-release refactor; no forwarding compatibility tree is required by default. This deliberate internal-path change must be documented, and any newly discovered external consumer is reported before removal. Freeze the public OpenAPI baseline and compare its meaningful paths/schemas/security/responses; module moves must not silently change generated operation IDs used by clients.

## Acceptance criteria

### Original planning request (historical)

- [x] Current boundary violations, import/entrypoint coupling and failure paths are evidenced.
- [x] Context ownership, allowed dependencies and explicit API/source layout are decided.
- [x] Application ports, audit/transaction seams, compatibility requirements and staged execution plan are specified.
- [x] Independent design review completed; no confirmed defects found within the reviewed scope.
- [x] Only this new task record changed; original staged/unstaged content preserved.

### Completed refactor gates

- [x] `backend/src/api/` is the HTTP transport package, outside both business contexts; routers contain no SQL/ORM/session access, crypto, filesystem or provider operations.
- [x] Identity and provisioning domain/application modules import neither each other nor API/runtime/infrastructure/frameworks. Relative imports and transitive package re-exports are checked.
- [x] Identity Authenticate/IssueToken/RevokeToken and provisioning ReadCatalog execute using fake ports; fresh interpreter import checks block framework/other-context dependencies.
- [x] Provisioning rule code moved with only import-path changes; existing lifecycle/lease behavior tests still pass.
- [x] A synthetic token hash captured from the old implementation authenticates through the new API against PostgreSQL; invalid identity cases remain denied and grants are unchanged.
- [x] Private delivery, no-overwrite, rollback, commit compensation, partial/interrupted writes, replacement-file protection and cleanup-failure behavior are covered.
- [x] Audit uses the owning SQL transaction; identity application tests import no provisioning package and disabled issuance rolls back new project/membership writes.
- [x] Metadata still has 11 tables and no Alembic differences. Frozen migration hash matches the baseline; only disposable test schemas were migrated.
- [x] Public OpenAPI matches the captured baseline exactly; HTTP behavior checks pass and no resource routes were added.
- [x] Installed wheel imports all five packages outside the checkout, registers metadata, builds the HTTP factory, serves liveness/OpenAPI/auth rejection and runs the installed CLI entrypoint help. Source migration assets remain documented.
- [x] Database-destination guard is unchanged; integration tests inject a caller-owned engine and verify metadata, credentials, revocation and failure behavior.
- [x] Static, type, unit/application/HTTP/architecture/PostgreSQL and wheel/sdist checks pass. Hosted CI execution remains unverified.

## Ordered plan and file ownership

The original plan authorized no implementation; the subsequent user request authorized these steps. They are now complete. Main agent owned contracts, integration and this task record; coder assignments were bounded to independent context files.

| Step | Work and verification | Ownership when authorized | Dependencies |
| --- | --- | --- | --- |
| 1. Characterize current boundaries | Capture current API/OpenAPI, credential validity, issuance rollback/audit and migration metadata behavior. Define principal/access-context/port signatures and architecture import rules before moves. | Main agent: contracts and tests baseline; investigator only for new questions | This plan |
| 2. Separate pure context code | Move resource rules to provisioning domain; introduce only needed identity policy/public DTOs and context-owned errors. Keep framework-free. | Coder A: `identity/domain`, `identity/contracts.py`, `provisioning/domain`, corresponding pure tests | Step 1 |
| 3. Assemble persistence ownership | Extract neutral Base/engine/audit persistence; split ORM models; introduce explicit metadata registration; prove identical metadata without altering frozen migration. | Coder B: context persistence + `platform_infrastructure`; main agent owns migration environment/registration integration | Step 2 contracts; registry/metadata work is sequential |
| 4. Extract identity application | Add use cases, narrowly grouped persistence/audit ports, hashing/generation and credential delivery adapters. Preserve transaction/file failure ordering and existing HMAC behavior. | Coder: `identity/application`, remaining identity infrastructure and application tests | Steps 2–3 |
| 5. Extract catalog and API | Add provisioning AccessContext/ReadCatalog/permissions; move HTTP code to top-level api; map principal at boundary; move readiness to technical adapter. | Coder: provisioning application and `api/`; main agent coordinates readiness integration | Step 4 principal contract and step 3 technical persistence |
| 6. Compose and switch entrypoints | Wire explicit dependency graph/lifetimes, scope registration, CLI and HTTP factory. Update wheel package list, internal imports, tests, docs and CI paths as required. Remove superseded source only after import and artifact checks. | Main agent: `platform_runtime`, pyproject/migration-env/docs/CI; coder only explicitly assigned test/adapter files | Steps 3–5 |
| 7. Verify and independently review | Run architecture and fake-port tests, HTTP characterization, isolated PostgreSQL/metadata checks and installed-artifact smoke checks. Reviewer inspects actual diff; address findings and rerun affected checks. | Reviewer read-only; main agent integrates and records actual evidence | Step 6 |

Parallel work is optional and only allowed after signatures are agreed and file ownership is disjoint. Do not run two agents on the old combined model/bootstrap/admin files during a move. Integration changes and registry/packaging updates remain sequenced. Once this refactor is verified, resume phase 2 of `backend-workflows.md` using the new boundaries; its previous single-`platform_api` tree is superseded by this design.

## Decisions, risks and deferred questions

- Two logical contexts and a top-level API are required; one backend and one control-plane database remain the deployment unit. A future microservice split would need a new data/consistency design.
- Shared technical metadata/audit retain cross-context database constraints deliberately. This preserves current data and avoids disguising a schema change as a package move.
- A pure principal is trusted only when created by the authorized host/authentication flow; an immutable dataclass alone is not proof of authentication.
- Scope registration belongs to composition; identity does not learn provisioning permission semantics. Provisioning remains responsible for action/project/ownership authorization.
- No third-party architecture/DI framework is required. Use targeted import-graph checks (resolving relative imports and re-exports) and explicit Python construction. Static checks do not prove runtime authorization; behavioral tests remain required.
- No material user decision blocks planning. New external consumers of old Python import paths, or a requested breaking public API change, require explicit scope resolution before implementation.

## Verification and review

### Implementation decisions and progress

- Captured sanitized public OpenAPI, a synthetic pre-refactor token digest, the frozen migration hash and the staged-index fingerprint before changes. Existing unit baseline: 51 passed, 33 subtests.
- Created top-level `api`, `identity`, `provisioning`, `platform_infrastructure` and `platform_runtime` packages. Retired the superseded `platform_api` source tree without changing the index; staged originals remain staged until the user chooses how to stage the refactor.
- Moved provisioning rules unchanged apart from imports. Added framework-free AccessContext, catalog use case and provisioning-owned scope registration.
- Extracted identity use cases, pure policy/snapshots and contextual ports. The first coder draft still put disabled-user/default-role/audit decisions inside SQL writes; coordinator requested correction. Those decisions now belong to application/domain code, with adapters limited to persistence and external operations.
- Split ORM ownership and retained shared technical metadata/audit. `registered_metadata()` explicitly registers all records; audit writes share the identity unit of work's session. Readiness SQL is in a technical probe, with HTTP consuming a structural typed outcome callable.
- HTTP handlers receive configured use cases and map verified identity into provisioning access values. Only pure public enums/errors cross into transport schemas/error mapping. No Session, SQLAlchemy exception, provider or key material enters API handlers.
- Runtime wires concrete adapters, scope registration, HTTP and CLI hosts and engine lifetime. A supplied engine stays caller-owned; the default engine is disposed at shutdown. Updated packaging, migration-environment imports, tests and setup/agent guidance together.
- Preserved public HTTP/OpenAPI, token HMAC and policy defaults, CLI command/options and environment names. Only internal Python import/factory paths changed; the canonical launch command is now `platform_runtime.http:create_app`.

### Actual implementation verification

| Command/check | Actual result | Scope and limits |
| --- | --- | --- |
| Initial `backend/.venv/bin/pytest -q backend/tests/unit` | 51 passed, 33 subtests | Before refactor; historical phase-1 contract baseline |
| Coder identity application checks | 15 passed; focused Ruff/format/mypy passed | Fake-port tests, no live database by coder |
| Coder provisioning catalog checks | 4 passed | Domain source copy changed imports only; independent catalog policy tests |
| `python3 /private/tmp/devops-hub-foundation-pg-check.py` final run | **100 passed, 33 subtests passed in 2.36s** | Disposable socket-only PostgreSQL 16.2 cluster under `/private/tmp`, unique test schemas, stopped and removed in `finally`. Escalation permitted local shared memory/socket; no shared DB or Docker resource used |
| `ruff check src migrations tests`, `ruff format --check src migrations tests`, `mypy src` | Passed; 70 formatted Python files, 59 source files type-checked | Complete current backend scope after old source removal |
| `uv lock --check --offline`, `uv sync --frozen --offline`, `uv build --offline` with task cache | Passed; wheel/sdist built | Existing dependencies retained; package list and script target changed, lockfile dependency graph unchanged |
| `python3 /private/tmp/devops-hub-boundaries-wheel-check.py` | Installed-wheel smoke passed | Disposable environment with locked dependencies, package locations verified under its site-packages, no source checkout fallback. Isolated HTTP factory/liveness/auth/OpenAPI, 11-table registration and `platform-admin --help` passed |
| Installed-wheel dependency fetch | Completed after initial offline-cache miss | Network escalation used to fetch locked dependencies into disposable environment; no global install |
| Baseline compatibility checks | Exact OpenAPI equality, frozen migration hash and original staged-index binary diff fingerprint match | No schema change or index mutation; no broader deployment compatibility claimed |
| Independent implementation review | One P2 test-boundary gap found, corrected and re-reviewed | See review evidence below; runtime PostgreSQL/artifact checks were coordinator-owned |

Independent reviewer found the initial import gate checked direct edges only, allowing a core module to obtain an adapter through a package initializer re-export. The corrected gate traverses the local import graph, including relative imports, symbol prefixes and implicit package-initializer edges, and checks restrictions from each originating layer. A regression detects the hidden adapter and its HMAC dependency. Reviewer reran all 11 architecture tests and confirmed the correction.

One pre-existing third-party warning remains: Starlette's HTTPX-based TestClient path is deprecated. It was not suppressed. Local checks used Python 3.13.0 and PostgreSQL 16.2; the CI workflow's Python 3.12/PostgreSQL 18 combination and live Docker/server integrations were not run.

Final implementation handoff fingerprint: 78 source/test/config/documentation files, excluding this task record, caches/environments and build outputs; SHA-256 `7ee7f955a415a75b7ffa6f7bddfa1ce02a118f20193e6269268d282e2c7e7bc7`. This identifies final handoff content, not an assertion that an earlier review used those exact bytes.

### Historical planning verification

| Check | Actual result | Scope and limits |
| --- | --- | --- |
| Git branch/HEAD/staged/unstaged inspection | Baseline recorded above; no initial unstaged changes | Existing implementation is staged, so ordinary unstaged diff alone is not its baseline |
| Coordinator source tracing | Confirmed layer mixing, context/model coupling and current API/CLI/migration seams | Read-only targeted file reads; no application execution |
| Independent investigator | Completed; agrees with context/application/port split and preservation requirements | Static import and execution tracing only |
| Existing phase-1 checks | Prior task records 62 tests and 33 subtests | Historical evidence, not rerun here |
| Independent design review | No confirmed design defects found | Compared the plan against current authentication, token administration, bootstrap, migration, package and PostgreSQL-test code; static review only |
| Record validation and final Git inspection | Links/whitespace and `git diff --check` passed; original files have no unstaged changes; only new task record untracked | No application/index mutation; no implementation correctness claim |

### Agent activity

| Runtime agent/thread | Role and instruction source | Scope/baseline | Actual findings/checks and limits |
| --- | --- | --- | --- |
| `/root/boundaries_investigator` | Runtime-selected investigator; explicitly read repository role guidance | Same HEAD, staged phase-1 backend/guidance, no unstaged changes | Read-only Git/source/import investigation. Confirmed mixed HTTP/auth/ORM/file responsibilities; identified metadata/audit/entrypoint/test-preservation constraints. No edits, tests, migrations, provisioning or secrets |
| `/root/boundaries_design_review` | Runtime-selected reviewer; explicitly read repository reviewer guidance | Same HEAD; new untracked design record against staged phase-1 source/tests/migration/package | Independent static design review found no confirmed defects. Checked context/import direction, audit/metadata/transaction seams, token/file behavior, API and packaging compatibility. No edits, tests or operational actions |
| `/root/identity_boundaries` | Runtime-selected coder (configured Luna/medium), explicit ownership and contract assignment | Same HEAD; identity domain/application/ports and non-model adapters plus one fake-port test file; coordinator owned ORM model split | Implemented then corrected policy/audit placement on coordinator feedback. Reported 15 unit tests plus focused Ruff/format/mypy. No migrations, resources or index changes |
| `/root/provisioning_boundaries` | Runtime-selected coder, explicit disjoint ownership | Same HEAD; provisioning domain/application and catalog unit test only | Copied rules with import updates; implemented catalog/access/scope contract. Four focused tests passed; no resource operations |
| `/root/boundaries_implementation_review` | Runtime-selected reviewer and repository role guidance | Staged phase-1 source compared with unstaged refactor and new packages; actual files inspected, not only tracked diff | Independent review found the indirect re-export gate gap; no other confirmed implementation defect. Ran 85 unit tests/33 subtests. Focused re-review ran 11 architecture tests and confirmed the correction. No edits/database/resource/secret/index operations |

### Template capability and supporting sources

The user optionally named the System Design template skill. Its `artifact-template.json` points to retained `assets/reference.docx`. The skill requires an advertised document capability and says: "If no such capability can be identified and read, say it is unavailable and stop; do not recreate or install it." The available document-control tool reported no connected sessions. The document-template workflow was therefore stopped; no template was cloned, replaced or claimed rendered. The user's explicit instruction to update only the task record governs the Markdown deliverable here. This record is not presented as an artifact generated from that template.

The dependency-inversion choice is an architectural judgment for this codebase. Microsoft's architecture guidance describes application-owned interfaces implemented by infrastructure and logical layering within a monolith: [Common web application architectures](https://learn.microsoft.com/en-us/dotnet/architecture/modern-web-apps-azure/common-web-application-architectures). It is used for that principle, not as a recommendation to use .NET or Azure or introduce cloud dependencies.

## Handoff

- **Completed:** full boundary refactor, context/application/API separation, explicit runtime wiring, schema/token/API preservation, architecture/behavior/integration/artifact checks and independent implementation review/correction.
- **Remaining within this refactor:** none. Hosted CI and its exact runtime are unverified; no deployment or provisioning was attempted.
- **Next concrete action:** implement phase-2 resource workflows from `backend-workflows.md` in the new provisioning application/ports/infrastructure boundaries when requested. Keep this refactor's scope separate from that feature work and preserve the existing staged index.

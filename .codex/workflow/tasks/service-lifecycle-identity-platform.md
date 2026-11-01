# Service injection, request lifecycle, identity and platform roadmap

## Current state

- **Updated:** 2026-11-01.
- **Authorized phase and scope:** user authorized the first implementation increment, stages 0–2: reconcile interrupted contracts, repository injection, async DI and external transaction/delivery completion, context-owned persistence and business vocabulary. Implementation and non-database verification completed. Stages 3–6 remain roadmap only; no live provisioning, deployment, production secret changes, staging or commits.
- **Next step:** run the 14 PostgreSQL checks against the documented disposable test database in CI or a configured local test environment before claiming database-level equivalence. Then scope the internal identity feature increment separately.
- **Open decisions:** internal account onboarding/recovery and administrator bootstrap policy; session/audit retention; first remote target and eventual AWS service. Proposed defaults and gates appear below.
- **Baseline:** `main` at `6f18a9b6fdf4f70de1f1ee214100d1dd3b267da5`; index clean. Five pre-existing unstaged files: `backend/src/identity/application/{authenticate,issue_token,ports,revoke_token}.py` and `backend/tests/unit/test_identity_application.py`. Preserve them during planning.
- **Latest verification:** 111 tests passed, 33 subtests passed, 14 PostgreSQL tests skipped (test URL unset); Ruff check/format, strict Mypy, lock consistency, build, installed-wheel HTTP/CLI smoke checks, OpenAPI/frozen-migration checks and compiled PostgreSQL DDL comparison passed. Independent diff review completed; confirmed UoW reuse finding fixed. Live PostgreSQL behavior remains unverified locally.

## Goal and evidence

Application services should receive repositories and domain-facing interfaces directly. A container should supply ready services to HTTP/CLI/worker hosts. An external unit of work manages database completion and cleanup, while request lifecycle instrumentation records safe outcomes. Identity and developer-platform capabilities remain separate bounded contexts.

### Confirmed repository facts at the investigation baseline

The incompatibilities below describe the interrupted starting tree. Stages 0–2 have now reconciled those callers and removed the old composition/UoW implementation; current results are recorded under implementation results and verification.

| Evidence | Current behavior and implication |
| --- | --- |
| `backend/src/bootstrap/composition.py:build_services`, `api/dependencies.py:ApiServices`, `bootstrap/http.py` | Manual application-wide service assembly, with services retrieved from `app.state`. No DI-container dependency in `backend/pyproject.toml`. HTTP and CLI share this graph. |
| Dirty `identity/application/{ports,authenticate,issue_token,revoke_token}.py` versus unchanged composition | Composition passes `transactions=` to `IssueToken`, whose dirty constructor requires `unit_of_work=`. Authentication receives a reader but now calls it as a factory. Dirty services require `.store`, which the SQL UoW does not implement. These are static incompatibilities, not runtime test findings. |
| HEAD versions of those application files; `identity/infra/persistence/{store,unit_of_work}.py` | HEAD uses a narrow authentication reader and transaction factories for commands. SQL UoW combines transaction lifecycle and write methods. This is a comparison baseline, not the requested final architecture. |
| `identity/application/issue_token.py`, `identity/infra/credential_file.py`, `tests/unit/test_credential_delivery.py` | Issuance writes an exclusive private credential file before commit and removes only its owned file on failure. Moving commit outside the use case requires transferring compensation responsibility too. |
| `identity/infra/persistence/models.py`, `api/identity/routes.py` | Users, projects, memberships and opaque API tokens exist. `/api/v1/me` and administrative token CLI exist; internal password login, browser sessions, invitations and user administration do not. |
| `developer_platform/application/catalog.py`, `domain/{resources,leases}.py`, `infra/persistence/models.py` | Protected empty catalog, lifecycle/lease rules and storage foundation exist. No resource commands, provider implementation or provisioning worker exists. Tables do not establish working workflows. |
| `api/`, `identity/`, `developer_platform/`, `shared/infra/`, `bootstrap/` | HTTP is already separate; both business contexts contain application/domain/infra layers. Shared infrastructure is technical. Keep `developer_platform` to avoid shadowing Python's `platform` module. |
| `backend/tests/unit/{test_api_contracts,test_identity_application,test_boundaries}.py` | Existing callers and boundary checks must migrate together. API-contract tests still construct authentication with a reader; dirty unit tests use the interrupted factory form. |

Canonical requirements: [platform requirements](../../../docs/platform-requirements.md). Earlier records remain historical evidence: [backend workflows](backend-workflows.md), [backend boundaries](backend-boundaries.md). This record supersedes passing a UoW into application services; it does not retroactively mark earlier work complete.

### Assumptions and architectural decisions

- Use a **modular monolith**, with lightweight domain modeling for identity authorization and platform lifecycle. Avoid microservices, a generic DDD framework, CQRS infrastructure or an event bus until a demonstrated requirement calls for them.
- Interpret “user monitoring” as authorized account/session/security-event administration. Authentication is company-internal: administrator-provisioned accounts and internally managed browser sessions. External Google/OAuth/OIDC login and account linking are removed from the roadmap. Internal username/password login belongs to the later identity increment; existing operator-issued API tokens remain supported.
- Choose **Dishka** for declarative provider registration, scoped lifetimes and transport injection, subject to a focused compatibility gate against the locked FastAPI/Python versions before implementation. Do not build a custom DI framework. Its documented integration supports automatic request scopes and handler injection. [Official Dishka integration](https://dishka.readthedocs.io/en/stable/integrations/fastapi.html).
- Plan **AsyncContainer + SQLAlchemy AsyncSession** for HTTP and future workers, with async repository ports/use cases where I/O occurs. Keep pure domain policies synchronous. Convert current sync application callers in one bounded migration, not by running synchronous ORM calls on the event loop. CLI uses an async entry adapter; Alembic can remain synchronous. This is an explicit internal contract migration, not an existing capability. Each concurrent operation needs its own session. [SQLAlchemy async guidance](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
- Preserve a small composition boundary: remove manual `build_services` and the global service bundle, rather than pretending construction/startup/shutdown can disappear. A host initializes the container; only declarative providers know concrete adapters.
- The C# analogue is a DI-scoped EF Core `DbContext`: short-lived, disposed, and unsuitable for concurrent sharing. Use that lifetime principle without making every network request one long database transaction. [Microsoft guidance](https://learn.microsoft.com/en-us/ef/core/dbcontext-configuration/).

## Scope and invariants

- **Current implementation:** stages 0–2 only, under the subsequent explicit implementation request. Baseline interrupted edits were reconciled through focused changes; no unrelated/staged work was reset. Later feature descriptions remain proposals and do not authorize implementation or live actions.
- **First implementation increment:** reconcile interrupted edits, establish repository/UoW separation, context-owned persistence outside pure domains, business-specific names, container-managed service lifetimes and equivalent existing HTTP/CLI behavior. No new login, provisioning or dashboard feature is required to complete that increment.
- **Later increments:** internal account login/session management, user/project administration, local Docker lifecycle, Next.js dashboard and optional server/cloud capabilities, each separately scoped.
- Preserve existing bearer-token semantics, scope checks, project ownership, sanitized errors, readiness behavior, credential-file protection, lifecycle transitions and UTC lease/max-lifetime rules.
- DI refactoring must preserve the current OpenAPI snapshot and frozen `0001_foundation.py`; later feature phases deliberately extend contracts and add forward migrations. Do not rewrite applied migrations.
- Never return credentials in normal inventory/status, logs, URLs, audit events or CI output. Connection disclosure requires authorization and a dedicated response with caching disabled. No arbitrary shell commands, provider URLs, Docker endpoints, AWS accounts or destinations from developer payloads.
- No local Docker daemon access, server connection or AWS call during planning. Later integration tests require explicitly isolated test resources and cleanup; a mocked adapter cannot establish live provider support.

## Contracts and ownership

### Target layout and dependency direction

```text
backend/src/
  api/                         HTTP routing, schemas, auth transport, error mapping
  identity/
    application/               use cases + narrow repository/gateway interfaces
    domain/                    identity, membership and session policies
    infra/                     context-owned ORM mappings/repositories and credentials
    contracts.py               immutable authenticated-principal contract
  developer_platform/
    application/               request, access, lifecycle and worker use cases
    domain/                    catalog policy, resources, leases and quotas
    infra/                     context-owned ORM mappings/repositories and providers
  containers/                  declarative identity/platform/technical providers
  entrypoints/                 minimal HTTP, CLI and worker startup/shutdown
  shared/infra/                technical engine/session/UoW mechanics and readiness
```

Implemented layout for this increment: `containers/` declares providers and typed operation adapters; `entrypoints/` hosts settings, metadata registration, HTTP and CLI startup. `bootstrap` is retired, including packaging/migration/test/documentation references. Launch path is now `entrypoints.http:create_app`; public `platform-admin` command/options and HTTP contracts are preserved. `api/app.py` remains a transport factory. No worker was added.

Dependencies: API/hosts → application contracts; application → its domain and interfaces; context infrastructure → those interfaces; containers → concrete implementations. Neither business context imports the other's internals. Trusted principal-to-platform access mapping remains at the host boundary. Existing physical FKs and shared audit storage do not justify cross-context repository imports.

### Context-owned tables and persistence boundaries

“Domain owns its tables” means the bounded context owns the schema, mappings, queries and changes; its pure `domain/` package contains no SQLAlchemy or database communication. ORM mappings and concrete repository implementations live in the owning context's `infra/persistence/`. Application services use repository interfaces and domain objects, never ORM rows or sessions.

| Owner | Tables and responsibility |
| --- | --- |
| Identity | Existing users, projects, memberships and API tokens; future password credentials, login sessions, internal invitations/recovery and identity security events. Mappings and SQL queries belong in `identity/infra/persistence/`. |
| Developer platform | Resources, operations, idempotency records, quota budgets, reservations and encrypted resource secrets; future platform lifecycle events. Mappings and SQL queries belong in `developer_platform/infra/persistence/`. |
| Shared technical infrastructure | Engine/pool/session factory, transaction completion and common metadata conventions. No context business tables, business repositories or cross-context queries. |

A shared PostgreSQL database is sufficient; separate physical databases are not required. Composition registers context-owned metadata. Every schema change names its owning context; migration operations are authored with that context's persistence changes and sequenced through the existing central Alembic revision chain. Avoid accidental independent migration heads and preserve the frozen foundation migration.

The existing `shared/infra/persistence/audit.py` mapping and `audit_events` table are a legacy exception requiring an explicit transition. Identity security events and platform lifecycle events belong to their respective contexts and use context-owned audit ports. During the DI-only increment, retain existing audit storage through a compatibility adapter; do not move/split tables or rewrite history merely to relocate code. Any later forward migration must specify backfill, retention, read compatibility and adapter removal. Shared transaction plumbing must not permanently own either context's business events.

Repositories access only their context's tables. Platform retains trusted identity/project IDs and obtains authorization through published contracts, never identity ORM queries. Existing physical foreign keys remain during the DI phase; they do not permit cross-context ORM relationships, business joins or imports. Identity remains responsible for account/membership decisions. Infrastructure translates database exceptions into sanitized application failures.

### Business vocabulary and naming requirements

Name entities, value objects, domain policies, application functions and repositories after actual business concepts/actions. `Entity`, `ValueObject`, `Service`, `Manager`, `Handler`, `Store`, `Data` or `Record` alone is not a business name. Introduce domain types/services only when their identity, invariants or behavior warrants them; do not fill architectural categories with empty wrappers. Technical names such as `AsyncSession` and `SqlAlchemyUnitOfWork` remain appropriate in infrastructure.

| Business meaning | Proposed names and actions |
| --- | --- |
| Internal user and project access | `InternalUser`, `ProjectMembership`, `ApiAccessToken`, `LoginSession`; `authenticate_api_token`, `sign_in_internal_user`, `revoke_login_session`, `change_project_member_role` |
| Provisioning and resource lifecycle | `ProvisioningRequest`, `ProvisionedResource`, `ProvisioningOperation`, `ResourceLease`, `QuotaReservation`; `request_test_database`, `renew_resource_lease`, `request_resource_deletion`, `reconcile_provisioning_operation` |
| Values with explicit invariants | `LeaseDuration`, `ResourceOwner`, `ResourceTemplateId`, only where validation/equality semantics warrant a separate type |
| Domain policy and external adapter | Pure `ResourceLeasePolicy` / `ProjectAccessPolicy`; infrastructure `DockerPostgresProvisioner` / future `AwsRdsPostgresProvisioner` |
| Repository and ORM mapping | `ProjectMembershipRepository`, concrete `SqlAlchemyProjectMembershipRepository`, mapped `ProjectMembershipRow` distinct from the domain object |

These examples guide contract design, not a blanket rename list. Keep `ProvisionedResource` generic only where multiple catalog resource types are actually supported; use PostgreSQL-specific names for PostgreSQL-only behavior. Avoid using `Identity` interchangeably for a user, token, membership and session. Before editing, record the agreed vocabulary here and map affected symbols/callers. Rename only within authorized scope, preserving public API/CLI fields and commands, table names and migration history unless a contract migration is explicitly approved. Review classes and functions against their actual responsibilities; enforce framework/ORM-free domain and application imports.

Implemented vocabulary: `AuthenticateApiToken`, `IssueApiToken`, `RevokeApiToken`, `ApiTokenRepository`, `SQLAlchemyApiTokenRepository`; pure `ProjectMembershipStatus`, `ApiTokenStatus`, `ApiTokenAuthenticationDetails`, `ApiTokenAuditEvent`; mapped `InternalUserRow`, `ProjectRow`, `ProjectMembershipRow`, `ApiAccessTokenRow`. All affected callers moved together; table/column names and public schemas did not change. No speculative resource/login types were introduced.

### Repositories, container scopes and external unit of work

| Object | Lifetime and allowed dependencies |
| --- | --- |
| Settings, async engine/session factory, immutable template registry, clock, hashers | Application scope; close owned pools/clients on shutdown. No principal, session or mutable per-request state. |
| Authenticated actor and correlation metadata | Request/command scope; trusted identity result, never an owner supplied by the request body. |
| Session, context repositories, application services, completion hooks | Operation scope nested inside the request/message/CLI command; fresh session for each transaction phase. Repositories share that session within a local operation. Never reuse it across concurrent tasks. |
| UoW/transaction executor | Technical outer adapter; owns begin, flush, commit, rollback and close. Application services neither receive nor resolve it. |
| Externally callable service decorator | Container supplies a ready typed service implementing its execution interface. Decorator enters the operation scope, resolves the repository-backed inner service, invokes it and completes the UoW before returning. API calls the injected service; no container lookups, session handling or transaction lambdas in routes. |

One SQL identity repository may implement both narrow read and write ports. Split interfaces by consumer needs without requiring separate reader/writer classes or separate sessions. Repository methods may flush for generated IDs/constraints, but never commit, rollback or close. Domain/service constructors and execute signatures contain no UoW, session, container or HTTP Request. A domain-facing audit writer participates in the same local transaction as successful state changes.

For a single database command: validate input/authenticate → enter operation and establish authoritative authorization → execute application service → materialize/validate transport DTO → commit → return response. Authentication read operations close their own scope; mutating commands recheck relevant active membership/ownership inside their transaction. Do not depend on a stale global principal. DTO materialization must not cause lazy ORM access after disposal.

The typed outer execution decorator accepts an adapter-owned result materializer, so response-model validation happens before commit. It must let application/validation/commit exceptions escape to HTTP error mapping outside its transaction block. No generic service locator or reflection-based command bus is required. Streaming and background work cannot inherit this transaction; they get explicit new scopes. No success headers/body are emitted before commit. DI teardown performs rollback/close safety, never a deferred commit. Cancellation before commit triggers bounded cleanup while preserving the original failure; cancellation/connection loss during commit can leave an uncertain outcome and requires operation-ID lookup/reconciliation rather than claiming rollback certainty.

**Scope lifetime is not transaction lifetime.** An internal login/recovery flow or provisioning operation may have multiple short database phases around external I/O. Orchestrating adapters own that sequence and inject repositories/interfaces into each inner use case. No DB transaction spans costly credential hashing, notification delivery, Docker/AWS readiness waits or image builds. Request tracing covers the whole request independently of database transactions. Record request/operation IDs, duration and sanitized outcome; never request bodies, bearer values or connection strings by default.

**Credential-file completion:** transfer delivery completion to the outer issuance coordinator. Inner issuance prepares token/digest/audit through injected ports and produces a private in-memory delivery result, never a normal API DTO. Outer coordinator writes the exclusive mode-0600 file, registers its ownership receipt, then commits; write failure rolls back, commit failure removes only the matching owned file. Clear raw-token references promptly. Preserve original failures if cleanup also fails. On process crash or ambiguous commit, database/filesystem atomicity is not guaranteed: report a safe recovery condition and identify/revoke by token ID as appropriate, never blindly retry issuance or overwrite another file. Tests must cover both delivery and commit failure under the new boundary.

### Identity requirements and proposed contracts

1. **Internal login:** administrator-created company accounts; no public registration or external identity provider. Username/password authentication uses an injected password-verification port and a maintained password-hashing library in identity infrastructure, never plaintext/reversible password storage or custom cryptography. Verify library/work-factor policy against primary guidance before implementation. Use generic login failures, timing-conscious verification, bounded rate limits/backoff and disabled-account checks. Hash/verify outside a long transaction, then recheck account status and credential version when creating the session to handle concurrent resets/disablement.
2. **Onboarding and recovery:** trusted operator CLI provisions the first administrator with explicit audit. Authorized administrators provision other accounts and memberships. Initial setup and password recovery use short-lived single-use secrets through an approved internal delivery channel; persist only their digests. No default/shared passwords or unauthenticated role grants. Define delivery, recovery approval and session-revocation policy before implementing these features.
3. **Browser sessions:** opaque high-entropy server session, stored as digest, expiration/rotation/revocation timestamps. Secure, HttpOnly, SameSite=Lax cookies under HTTPS; documented isolated localhost development configuration. CSRF protection and Origin checks on cookie-authenticated mutations, bounded CORS, configured post-login redirect allowlist. Prefer same-origin reverse proxy for Next.js/API. No auth token in localStorage, redirect URL or page HTML. Reject requests with conflicting cookie and bearer credentials rather than guessing identity.
4. **Authorization:** retain CLI/CI bearer API tokens. Resolve current active user and membership on authenticated requests; user disablement invalidates all sessions/tokens. Browser login without a project may inspect its profile but cannot provision; selected project is checked against membership for each action. Project admins administer only their projects; account/platform administration is operator-authorized. Protect the last project administrator. Existing token CLI remains operator-only. Before stage 3, split `identity/contracts.py:AuthenticatedPrincipal` (mandatory `project_id` and `token_id`) into authenticated-user/credential and selected-project authorization contracts. Distinguish session IDs from bearer token IDs; never fabricate IDs for browser login. Preserve bearer `/me` through a compatibility adapter and define browser responses before frontend work.
5. **User services:** current profile/project memberships; safe profile/password update; list/revoke own sessions; logout/logout-all; internal invitations and membership role changes; operator-authorized account creation/disable/restore and recovery; bounded admin audit queries. Password reset/change invalidates affected sessions according to explicit policy. Reactivation does not resurrect revoked credentials. Resource cleanup after membership removal/account disable is an explicit platform policy, not an implicit destructive identity action.
6. **Monitoring:** paginated authorized security events for login success/failure, credential/reset/session changes, account/membership changes and API token operations. Separate failed-login audit persistence from rolled-back business changes where appropriate. Bound retention, minimize IP/device data, exclude passwords, recovery secrets, session/API tokens and unauthorized project details.

Proposed transport families (freeze exact schemas/OpenAPI before coding): `/api/v1/auth/login`, `/api/v1/auth/{logout,logout-all}`, `/api/v1/me`, `/api/v1/me/sessions`, internal password setup/change/recovery, `/api/v1/projects/{project_id}/memberships`, and operator-scoped users/security events. Use POST for login/logout and POST/PATCH/DELETE with CSRF for cookie-authenticated state changes. Preserve bearer `/me`; agree response fields before frontend work. Use stable sanitized errors. Setup/recovery secrets are single-use, expire and resist replay; login does not disclose whether an account exists.

Identity-owned forward migrations define password credentials, sessions, internal invitation/setup/recovery records and security events with uniqueness/expiry indexes. No external-identity tables, OAuth callback endpoints, OIDC libraries or third-party login configuration are planned. Determine audit compatibility and retention explicitly. No authentication implementation or dependency installation is authorized by this update.

### Developer-platform capabilities and workflow contracts

Keep these capabilities inside `developer_platform/{application,domain,infra}`; “communicate with AWS” is a resource-specific adapter responsibility, not a generic cloud domain service.

| Phase/capability | Developer outcome and required workflow |
| --- | --- |
| Local catalog and targets | Registered PostgreSQL versions/sizes, allowed local Docker target, lease/network limits and authorization. Reject unsupported combinations before allocating anything. |
| Request acceptance | Project/branch/template/target/TTL input; derive owner from trusted actor. Atomically validate quota, reserve capacity and persist resource + durable operation + idempotency record; return 202 with IDs/status URL, never pretend it is ready. Same scoped key/payload returns the same result; changed payload conflicts. |
| Durable worker | Claim with expiry/revision fencing; persist intent → external create/inspect → persist observation. Bound retries/deadlines, handle lost/late completion and worker restart. Provider ownership labels and stable resource IDs permit orphan discovery. Retain capacity while outcome is uncertain. |
| Database access | Dedicated per-resource user/password; readiness distinct from external reachability. Encrypt persisted credentials with configured key IDs; only ready, authorized, non-expired resources disclose a DSN through a no-store audited endpoint. Document the verified client network location. |
| Full lifecycle | Inspect/list, renew within policy, cancel/create races, explicit delete, TTL expiry, retry cleanup, reconcile and operator recovery. Revoke access and confirm resource absence before deletion completion or releasing reservations. |
| Next.js dashboard | Catalog, request form, inventory/detail, operation progress, expiry, masked/revealed connection guidance, allowed lifecycle actions, project switcher; separate admin account/security/cleanup views. Backend remains the authorization/provisioning authority. |
| Branch/PR automation | Verified signed webhook, replay/deduplication protection, project/repository mapping and closure-triggered cleanup. No credentials in comments or build logs. Build after API lifecycle works. |
| Configured server | Registered Docker-over-SSH target with host verification, operator credentials and explicit VPN/tunnel/network policy. Local success is not evidence of remote support. |
| Containerization/build delivery | Reproducible backend/worker/dashboard Docker images, health checks, CI tests, scan/publish immutable image digests, explicit deploy/rollback path. Optional developer image builds use approved sources and isolated builders; never execute arbitrary Dockerfiles in the privileged provisioner. |
| AWS extension | Candidate: managed PostgreSQL through an RDS adapter after local lifecycle. Explicit account/region/VPC/subnet/network/size allowlists, role/STS credentials, tags, quota/cost/cleanup policy, eventual consistency and service latency. Requires separate design/authorization and credentials; no AWS support claimed from mocks. |
| Later catalog expansion | Redis/other databases, seeded data, previews, rotation, notifications, usage/cost reporting and retention/backup policies only after defining their distinct capabilities. No promise of universal provisioning. |

Provider ports describe create/inspect/readiness/revoke/delete and discovery capabilities with immutable result DTOs, stable external IDs and sanitized failure classification. Separate invalid request, denied policy, capacity exhaustion, provider timeout with unknown outcome, failed create and failed cleanup. No providers commit control-plane transactions. A durable Postgres operation queue is sufficient initially; no broker required just to introduce workers.

Preserve canonical `domain/resources.py:transition_status`: desired deletion prevents becoming ready; deleted requires confirmed absence and resolved outstanding operations; late-created resources reopen cleanup. Preserve lease UTC/max-lifetime rules. Renew/expiry and cancel/create use atomic revision/locking rules. The provider identity/tombstone must survive long enough to detect late effects; a timeout is not proof of absence. Destructive reconciliation is restricted to resources with verified platform ownership, never arbitrary server containers.

Proposed platform endpoints: catalog/targets; POST/list/detail resources; renewal/deletion/cancellation; operation status; dedicated connection retrieval; admin cleanup/reconciliation. Freeze payloads, idempotency scope, state/error vocabulary, ownership and pagination before coding. Authentication grants registered permissions; platform evaluates its resource policies using a trusted access context. Neither context imports the other's ORM.

### File ownership for future authorized implementation

| Stage/owner | Exclusive responsibility and dependencies |
| --- | --- |
| Coordinator, first | Contract/DTO decisions, boundary rules, migration/API policy, packaging/entrypoints, shared session/UoW and completion semantics, task record and integration. Sequence these before dependent edits. |
| Coder: identity persistence | Assigned identity repository ports + SQL adapter and focused tests only after contracts are fixed. Move database methods out of UoW; preserve read/write semantics and errors. No simultaneous edits by the coordinator to these files. |
| Coder: DI/lifecycle, sequential assignment | Assigned container providers, typed outer service wrappers and HTTP/CLI lifecycle tests after repository contracts land. Coordinator supplies transaction/compensation criteria and owns shared-file integration. |
| Coder: identity features, later | Assigned identity domain/application/infra, corresponding identity API files and new migrations after internal account/session contracts are decided. |
| Coder: platform, later | Assigned platform workflows/provider/worker tests after operation/provider contracts are fixed. Frontend can proceed independently only once versioned API schemas are agreed. |
| Investigator / reviewer | Read-only evidence tracing / independent actual-diff review. Must record real activity and baseline. |

Every coder assignment must say it is not alone in the workspace, list exact owned files and acceptance criteria, preserve unrelated/staged work and return commands/results/limits. These are ownership rules, not standing agent tasks or implementation authorization.

## Acceptance criteria

### First implementation increment: stages 0–2

- [x] All current HTTP/CLI constructors and callers reconcile; no half-migrated `transactions`/`unit_of_work`/`.store` contracts remain.
- [x] Application services take repositories/interfaces only; import checks enforce ORM/framework-free domain/application layers. Context mappings/queries remain in infrastructure; one SQL repository implements read/write ports.
- [x] Table/migration ownership and legacy audit compatibility are explicit; business-specific names and callers updated without public contract/schema changes.
- [x] API receives a ready typed capability from Dishka; global service bundle/manual graph removed; minimal host startup/shutdown documented.
- [x] Scope tests verify independent sessions for concurrent requests and shared session within each operation; DTO materialization precedes commit and disposal.
- [x] Failure-injection tests verify action/materialization/commit errors roll back, commit failure emits only HTTP 503, cancellation/cleanup preserve original failures, and uncertain outcomes are not claimed rolled back with certainty.
- [ ] Run PostgreSQL integration to confirm real token/audit atomicity, async issuance/authentication/revocation, rollback and schema/migration equivalence. Fourteen tests are present but skipped locally without a disposable database URL.
- [x] File tests verify private/exclusive delivery, no overwrite, rollback on write failure, owned-file compensation on commit failure, replacement-file protection and retained credentials after successful commit followed by close failure.
- [x] Host/caller ownership, test overrides and installed-wheel HTTP/CLI smoke checks passed; OpenAPI, frozen migration hash and compiled DDL remain unchanged. Real database readiness success is part of the pending PostgreSQL gate.

### Later feature increments, independently authorized

- [ ] Internal-login tests cover valid/invalid passwords, generic unknown/disabled-user errors, rate limiting, maintained-library password verification, credential-version races, administrator provisioning, single-use setup/reset expiry/replay and session invalidation. No external login dependency, public registration or plaintext credential persistence exists.
- [ ] Sessions, logout/revocation, inactive user, role change, conflicting credentials, CSRF, rate limiting and project isolation are observable through API tests. Projectless browser identity works through explicit subject/session contracts without fabricated token/project IDs; current bearer `/me` remains compatible. No unauthenticated self-enrollment grants admin/project access.
- [ ] A local integration demo proves two isolated PostgreSQL requests, usable authorized DSNs from the documented network, idempotency, quota races, renew/expire/delete, worker restart and cleanup after late create/timeout; tests clean only owned disposable resources.
- [ ] No success or cleanup state is fabricated when an external outcome is uncertain. Provider mock tests are labeled contract tests; live local/server/AWS verification is reported separately.
- [ ] Next.js consumes agreed API contracts; identity/admin and resource actions enforce server authorization, safe credential display and clear pending/failure/cleanup states.

## Plan and progress

1. **Completed: investigation and planning.** Inspect branch/HEAD/index/diff, read guidance and implementation, delegate read-only tracing, review official DI/session guidance. User revision removes external login, makes context-owned persistence explicit and requires business-specific names. Write only this record.
2. **Stage 0 — coherent baseline, after authorization.** Inspect the five interrupted edits and all callers against HEAD. Patch toward repository injection; preserve unrelated work, never reset whole files/tree. Characterize existing auth/issue/revoke, file compensation, API snapshot, migration hash and lifecycle behavior before restructuring. Do not use historical passing tests as evidence for the dirty tree.
3. **Stage 1 — contract foundation.** Coordinator fixes repository/read/write ports, async DTO/caller changes and outer operation completion contract, including precommit result materialization and file receipts. Define table ownership, legacy audit compatibility and agreed business vocabulary before assigning adapters. Add DI dependency only after an isolated compatibility check confirms supported FastAPI integration, override/finalizer behavior and type checking. No new login or resource schema changes in this stage.
4. **Stage 2 — DI and external transaction lifecycle.** Bounded coder implements repository adapters; then separately assign container providers/wrappers. Coordinator migrates hosts/entry paths/package metadata/docs and integrates async callers. Verify actual commit-before-response behavior with a failing commit and captured ASGI messages, concurrency isolation and CLI compensation. Independent reviewer checks the actual diff; resolve findings and rerun affected checks. Stop for acceptance before feature expansion.
5. **Stage 3 — internal identity and login/session slice.** Resolve internal onboarding/recovery, administrator bootstrap and retention decisions; define authenticated-user/credential and selected-project contracts with bearer compatibility, then freeze endpoints and identity-owned forward migrations. Implement internal account provisioning, maintained-library password verification, sessions and setup/recovery, followed by user/project administration/security events. Test locally with synthetic credentials; no external authentication service is required.
6. **Stage 4 — complete local platform vertical slice.** Contract-first catalog/target/provider/operation APIs, atomic quota/idempotency acceptance, durable worker, local Docker PostgreSQL, credential protection, readiness, authorized retrieval, lease/cleanup/recovery. Independently review lifecycle races before claiming the demo complete. No cloud required.
7. **Stage 5 — dashboard and delivery.** Build Next.js against frozen contracts; containerize services; verify isolated CI lifecycle and image build/scan/publish; document actual deploy and rollback commands. Publishing an image is not deploying the application.
8. **Stage 6 — optional integrations.** Signed branch/PR automation, configured server, then separately designed AWS adapter and broader catalog. Specify costs, network/credential access and verified capabilities for each; do not silently expand stage 2 into this roadmap.

Stages 0–2 are sequential because contracts/lifetimes cross all callers. Their implementation is complete; PostgreSQL verification remains pending as explicitly tracked above. After API and identity contracts stabilize, frontend and isolated provider tests may run in parallel with non-overlapping ownership. Stages 3–6 require separate scope authorization; no checkbox authorizes external actions.

### Implementation results: stages 0–2

- Coordinator established async `ApiTokenRepository` and private `PreparedApiToken` contracts first. Coder then implemented the bounded identity use-case/repository slice. The five interrupted files were reconciled, not reset.
- `SQLAlchemyApiTokenRepository(AsyncSession)` now owns identity queries/writes, with no transaction completion. Applications receive repositories, clock, hashing and generation interfaces; issuance returns a private, repr-redacted result rather than handling delivery.
- `SqlAlchemyUnitOfWork.run(action, materialize)` in shared technical infrastructure begins, materializes, commits and closes before returning. It rolls back on failure, bounds rollback/close cleanup, sanitizes technical failures and retains primary-error notes. It is explicitly single-use; a new operation requires a fresh DI scope.
- `CurrentIdentityQuery` materializes `PrincipalView` inside the operation; API injects its `ReadCurrentIdentity` interface. `IssueApiTokenToFile` owns exclusive delivery and compensation; `RevokeApiTokenCommand` owns revocation completion. No container/session/UoW enters application code.
- Declarative `DatabaseProvider`, `IdentityProvider`, `PlatformProvider` replace `build_services`/`ApiServices`. `entrypoints` replaces `bootstrap` in packaging, Alembic host wiring, tests and docs. Runtime SQL is async; migration engine construction remains sync. App-owned pools close at shutdown; caller-owned engines/containers stay caller-owned and must be closed on their owning event loop.
- Context-owned ORM mappings remain outside domain/application. Business types and mapped rows now have the explicit names recorded above. All 11 table/index definitions compile identically to HEAD. Legacy shared audit storage remains the documented compatibility exception; no table or migration was moved/recreated.
- Coordinator owned DI/hosts and integration directly; coder separately owned identity implementation, then integration-test adaptation, then lifecycle tests. This replaces the originally suggested second coder DI assignment without overlapping edits. Reviewer independently reviewed the actual diff and new files, then reviewed fixes/names/tests/docs.
- Confirmed reviewer finding: a reused UoW could keep `committed=True` from an earlier operation and skip compensation on a later failed issuance. Fixed with a pre-await single-use guard and repeat/concurrent-use regressions. Lifecycle tests also exposed missing cleanup notes on the sanitized DB failure; translation now preserves those safe notes.
- No resource/provider, internal password/session feature, frontend, Google integration, database migration execution, live provisioning, deployment, secret change, staging or commit occurred. PostgreSQL tests remain collected and protected by the existing disposable-local-database guard.

### Decisions requiring user input before their dependent feature phase

| Decision | Proposed default | Gate |
| --- | --- | --- |
| Internal account onboarding and recovery | Administrator-provisioned accounts; single-use setup/reset secrets through an approved internal channel; no public registration | Before stage 3 schemas and credential delivery/recovery implementation |
| First administrator | Existing local operator CLI/bootstrap with an explicit admin-grant command and audit trail; no first-web-user auto-admin | Before exposing membership/account administration |
| Sessions/audit | Proposed 8-hour absolute session, 30-minute idle timeout, 90-day security-event retention; confirm operational/privacy needs | Before persisted session/audit retention behavior |
| User monitoring meaning | Security/account/session administration | Confirm before adding monitoring beyond those events |
| Remote/AWS priorities | Configured Docker-over-SSH first; AWS RDS PostgreSQL only as a later candidate | Before target-specific design, spend or live access |

These do not block planning or the DI-only increment. Runtime defaults are proposals, not current configuration. AWS/server access remain external dependencies for optional provisioning adapters, not requested secrets to place in this record. Internal authentication does not depend on Google or another external login service.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| Baseline `git status --short`, `git rev-parse HEAD`, branch/index/diff inspection | `main@6f18a9b`; five interrupted files plus this untracked record; clean index | Starting contract mismatches reconciled during this implementation; no branch/index mutations |
| `uv add 'dishka>=1.6,<2' 'sqlalchemy[asyncio]>=2.0,<2.1'` | Installed/locked Dishka 1.10.1 and greenlet 3.5.6 | Initial cache access was sandbox-denied; approved escalated retry succeeded. No paid/live service |
| `.venv/bin/pytest -q` from `backend/` | **111 passed, 14 skipped, 33 subtests passed** | PostgreSQL URL unset; one existing Starlette/httpx deprecation warning; no live DB equivalence claimed |
| `.venv/bin/pytest -q tests/unit/test_operation_lifecycle.py` | 19 passed | Includes UoW failure/cancellation/reuse, materialization, credential compensation, scope isolation, captured ASGI 503 and host/caller ownership; no database |
| `.venv/bin/ruff check src migrations tests`; `.venv/bin/ruff format --check src migrations tests`; `.venv/bin/mypy src` | Passed; 75 Python files formatted, 63 source files type-checked | Early formatting/type issues corrected before final run |
| `uv lock --check --offline --cache-dir /private/tmp/devops-hub-uv-cache` | Passed; 40 packages resolved consistently | Python 3.13 local interpreter; CI config remains Python 3.12 and has not run in this session |
| `uv build --offline --cache-dir /private/tmp/devops-hub-uv-cache --out-dir /private/tmp/devops-hub-lifecycle-dist` | Wheel and source distribution built | Artifacts outside repository; no `backend/dist` recreated |
| `uv pip install --offline --no-deps --target /private/tmp/devops-hub-lifecycle-installed <built-wheel>`; isolated `python -I` smoke from `/private/tmp` | Imported all six shipped packages from installed target, not checkout; liveness 200, missing auth 401, disconnected readiness 503, OpenAPI 200, `platform-admin --help` exit 0 | Dependencies reused from verification venv; no DB/provisioning; CLI issuance persistence remains PostgreSQL gate |
| OpenAPI/frozen migration tests; isolated HEAD archive versus current metadata compiled with PostgreSQL dialect | Public snapshot and migration hash passed; **11 table/index DDL definitions identical** | Static DDL comparison is not a migration execution or database round trip |
| Independent diff review `/root/service_lifecycle_diff_review`, including untracked sources | One P2 UoW reuse defect fixed; follow-up found no new confirmed source/test/name/docs issues | Read-only static review, not test execution. Coordinator subsequently added three ownership cases and ran them successfully |
| `git diff --check`, task links, final index/scope inspection | Passed for source; final record checks repeated after update | Nothing staged/committed; unrelated baseline preserved through authorized reconciliation |

Review status: independent actual-diff review and follow-up completed; confirmed finding resolved and affected behavior rechecked. Three final ownership checks and this record's implementation update were coordinator-verified after review. PostgreSQL integration remains unverified locally.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/service_lifecycle_investigator` | Read-only investigator; explicit coordinator assignment + developer investigator role; read repository guidance/skill | Identity/application/infra, composition/API/CLI callers, platform models/lifecycle and tests at `main@6f18a9b` plus five dirty files | Confirmed contract incompatibilities, global service graph, missing identity/platform workflows and outer-commit file-compensation risk. Static reads/diffs only; no files changed or tests run. |
| `/root/identity_uow_tests` | Coder from the preceding interrupted implementation, not this planning assignment | Prior identity unit-test migration | Interrupted before this planning work; its partial test edits are included in the five-file preserved baseline. No additional coder work authorized here. |
| `/root/service_lifecycle_plan_review` | Read-only reviewer; explicit coordinator assignment + developer reviewer role | New task record and affected source at `main@6f18a9b` plus five dirty files | Confirmed interrupted contract mismatches; found inaccurate credential-file path and missing projectless/session principal contract gate. Both addressed. No edits, tests, network calls or resource access. |
| `/root/identity_repository_refactor` | Coder role (`gpt-6-luna`/medium), explicit bounded coordinator assignments and repository guidance | Three sequential non-overlapping assignments at the baseline: identity use cases/repository/unit tests; only PostgreSQL integration test file; only new lifecycle test file | Implemented assigned slices; identity tests 12 passed, lifecycle tests 16 passed before coordinator's added ownership cases; integration 14 collected/skipped with URL unset; focused Ruff/Mypy passed. No resources/migrations/commits. Coordinator later applied vocabulary changes across callers. |
| `/root/service_lifecycle_diff_review` | Independent read-only reviewer via explicit assignment/developer role | Actual HEAD diff plus new containers/entrypoints; follow-up on UoW fixes, lifecycle tests, naming and docs | Reported P2 reused-commit-state compensation defect; verified guard/regression coverage, no further confirmed defects. No test/resource/network execution or edits. |

## Handoff

- **Completed:** stages 0–2 implementation, non-database verification, installed-wheel smoke and independent diff review. Repository injection, external single-use UoW, declarative DI, business vocabulary and context-owned ORM boundaries are in place; old bootstrap/manual assembly retired.
- **Remaining:** actual disposable-PostgreSQL verification before claiming DB equivalence; later identity/provisioning/dashboard/provider phases remain unimplemented and need their own scope. Shared audit compatibility remains intentional pending a separately designed storage transition.
- **Next concrete action:** use the existing CI ephemeral PostgreSQL service, or set the documented local disposable test URL and run `.venv/bin/pytest -q`. No live provider/deployment authorization follows from this record.

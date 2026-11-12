# Backend architecture

Follow the root [AGENTS.md](../AGENTS.md). The backend uses Python, FastAPI,
SQLAlchemy and Alembic over PostgreSQL. See [README.md](README.md) for commands.

## Dependency direction

```text
api  ->  context module contract  ->  application  ->  domain
context infra  ->  implements application/domain ports and owns context DI
composition  ->  assembles process dependencies and both bounded contexts
api/composition -> adapts HTTP requests to context capabilities
```

- `domain` is pure Python business language. It imports no FastAPI, Dishka,
  SQLAlchemy, provider SDK or infrastructure type.
- `application` coordinates one use case through domain objects and narrow ports.
  It imports no API, container, ORM model, session or concrete adapter.
- `infra` implements domain/application ports and owns SQLAlchemy mappings,
  repositories, provider SDKs, hashing, encryption and technical adapters.
- `api` authenticates requests, checks project/role permissions, translates HTTP
  to application commands/queries and maps results to responses. It contains no
  domain state transitions or direct ORM access.
- Context `infra/composition` registers handlers, ports and concrete module
  dispatchers and exposes context-owned container registrations. The top-level
  `composition` package combines those registrations into one process-scoped Dishka
  container and owns `BackendRuntime`; contexts contribute providers rather than
  creating isolated containers, preserving shared session and unit-of-work scopes.
  Alembic alone discovers aggregate schema metadata under
  `migrations/`. Cross-context bridges and their bindings live under
  `composition/integrations`; API request adapters and their provider live under
  `api/composition`; resource and application workers live with their owning
  context under `infra/workers`.
  Dishka constructs the selected handler lazily; providers contain no use-case
  or transaction logic.
- `shared/infra` contains technical primitives only. Business rules remain in the
  context that owns them.

`identity` and `devops_hub.platform` are independent bounded contexts. Identity
owns users, credentials, sessions, tokens and project membership. Developer
platform owns registered projects, catalog choices, resource requests, leases,
operations and workload delivery. Cross-context actor mapping belongs in the
composition layer. Do not create a top-level `platform` package because it would
shadow the Python standard library.

## Context structure

Use this shape when the concepts exist; do not create empty DDD wrappers:

```text
<context>/
  domain/
    entities/          identity-bearing business objects
    value_objects/     validated immutable concepts
    aggregates/        consistency boundaries and state transitions
    services/          rules spanning more than one domain object
    interfaces/        repository contracts for domain collections
  application/
    <use_case>/                  for a standalone action
      command.py | query.py
      handler.py
      result.py                  only when a dedicated result is useful
      port.py                    only for use-case-specific external capabilities
    <capability>/<use_case>/     group only several closely related actions
  infra/
    persistence/       ORM mappings, aggregate/capability stores and read projections
    providers/         Docker, GitHub or other external-system adapters when present
    security/          hashing, signatures and credential adapters when present
    templates/         filesystem template adapters when present
    composition/       context DI providers and explicit module dispatch
```

Each use-case folder represents one developer action. Commands may change state
and enforce domain invariants; queries return authorized projections without
changing state. Keep a command/query beside its handler; do not add a capability
wrapper around a single action. Use `shared/` only for contracts genuinely shared
by several use cases. Prefer names such as `renew_lease` and `issue_api_token`
over generic `service`, `manager` or `utils`.

A repository persists one aggregate root or an explicitly named transactional
capability; it is not required for every entity or table. Keep read projections,
worker queues and external provider effects as separate ports. Multiple adapters
may share one host-owned SQL session when an operation must be atomic. Do not add
empty infrastructure folders or adapters for unimplemented targets.

## Application and API contracts

- Application handlers return plain typed data or `None` on success. Use a named
  result DTO when several values belong together. Expected failures use typed
  domain/application errors; infrastructure failures propagate to the host for
  rollback. Application outcomes contain no HTTP status codes or FastAPI types.
- The API authenticates the actor and enforces project/role/scope permissions
  before invoking a use case. Map typed failures to consistent HTTP errors at
  the API boundary. Pass a trusted actor context to the application; do not trust
  caller-supplied ownership fields. Domain rules still enforce resource ownership,
  valid state transitions, quotas and lease limits, including for worker callers.
- Platform developer-action scope/project rules live in
  `devops_hub.platform/authorization.py`. API routes check them before dispatch;
  HTTP and non-HTTP hosts check again using freshly authenticated access. Platform
  application handlers do not repeat these transport permission checks. Loaded
  resource/application ownership, readiness, quota and idempotency remain enforced
  by domain and persistence rules within the operation transaction.
- Each bounded context exposes a typed module contract with async `execute(command)`
  and `query(query)` entry points. The context owns an explicit message-to-handler
  registry and adapters under context `infra/composition/`; a request-scoped dispatcher resolves
  only the selected handler. `api.composition` binds an HTTP host wrapper to the
  module contract; the process composition root registers its provider. Routes do not
  select or construct handlers. Application messages
  and results contain no FastAPI/Pydantic types, and unknown messages fail closed.

## Transaction ownership

The outer HTTP or worker operation host owns each transaction boundary. For a
single database operation it invokes `SqlAlchemyUnitOfWork.run()` around context
dispatch: the unit of work alone begins, commits, rolls back and closes the
transaction. The inner context dispatcher, handlers, repositories and DI providers
never complete it. Browser login/password workflows retain their intentional short
transaction sequence around password hashing; application delivery workers retain
separate claim/effect/completion phases. External effects run only after durable
intent has committed.

Organize `src/api/` by bounded context and HTTP feature:

```text
api/
  app.py                 FastAPI setup, factory and error mapping
  asgi.py                ASGI entrypoint
  router.py              Root API router
  core/                  shared HTTP errors, schemas, dependencies and security
    middlewares/         request boundary middleware
  settings/              HTTP-only configuration and cookie policy
  identity/               bounded-context router and feature packages
    authentication/      login, logout and project selection routes/schemas
    sessions/            current session, password and session routes/schemas
    memberships/         project membership routes/schemas
    principal/           authenticated principal route/schema
  platform/               bounded-context router and feature packages
    catalog/              catalog routes/schemas
    projects/             project routes/schemas
    resources/            database resource lifecycle routes/schemas
    operations/           async operation routes/schemas
    application_delivery/ templates, applications and deployment routes/schemas
  health/                 liveness, readiness and metrics
  composition/            HTTP-to-context adapters and API-only DI provider
composition/              process composition root and BackendRuntime
  integrations/          Cross-context bridges and their provider bindings
migrations/               Alembic environment, metadata discovery and revisions
```

Each bounded context has one base router that aggregates feature routers; the root
API router registers health and context routers. Keep each feature's routes and
request/response schemas together. Shared HTTP plumbing belongs under `api/core/`,
HTTP-only settings under `api/settings/`, and API provider bindings in
`api/composition/`; context providers remain in each context's `infra/composition/`.
API routes call the context module contract; migrate callers together when changing
an existing contract.

`BackendRuntime` builds the lazy API dependency graph before FastAPI middleware is
installed, then owns the process `start()`/`close()` lifecycle. Startup performs no
database connection, migration or provisioning. A runtime-created container is
closed by the runtime; an injected container remains caller-owned. Worker composition
uses the same backend container assembler with context-owned worker providers.

Alembic owns model discovery and schema changes. `migrations/metadata.py` imports
the context mappings for `target_metadata`; API and worker startup must not call it,
create tables or run migrations. Apply revisions explicitly through Alembic.

## Invariants

- Application handlers receive repositories and ports defined by their context.
- Record intent, idempotency identity and quota reservation atomically. Perform
  Docker/cloud effects outside SQL transactions and persist enough state to
  recover after duplicate delivery, timeout, crash or late completion.
- Every temporary resource has an owner, creation time, expiry, status and cleanup
  path. API permission checks cover provisioning, lease renewal and deletion;
  domain state changes remain safe to retry. Never adopt or delete a provider
  resource without owned labels.
- Credentials remain encrypted or referenced at rest and never appear in logs,
  ordinary list responses, task records or CI output. Sensitive retrieval is an
  explicit authorized and audited action.
- A queued database row or fake adapter success is not readiness. End-to-end claims
  require authorized connectivity, lease behavior and verified cleanup.
- API contracts use typed schemas, documented status codes and sanitized stable
  errors. Asynchronous creation returns an operation identity and exposes state.
- Schema changes preserve context table ownership and migration compatibility.
  A downgrade is not assumed to be a safe data rollback.

Use [backend-development](../.agents/skills/backend-development/SKILL.md) for
domain/application/infra/worker procedures and
[api-development](../.agents/skills/api-development/SKILL.md) for HTTP procedures.
Load both only when the change crosses their boundary.

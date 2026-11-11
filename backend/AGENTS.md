# Backend architecture

Follow the root [AGENTS.md](../AGENTS.md). The backend uses Python, FastAPI,
SQLAlchemy and Alembic over PostgreSQL. See [README.md](README.md) for commands.

## Dependency direction

```text
api  ->  context module contract  ->  application  ->  domain
infra  ->  implements application/domain ports
containers  ->  wires API, module implementations and infra adapters
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
- `containers` constructs handlers, module implementations and adapters. Providers
  contain no use-case logic.
- `shared/infra` contains technical primitives only. Business rules remain in the
  context that owns them.

`identity` and `developer_platform` are independent bounded contexts. Identity
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
    persistence/       ORM mappings and SQL repository implementations
    <adapter>.py        provider, security or external-system adapters
  containers/          context DI providers and host adapters
```

Each use-case folder represents one developer action. Commands may change state
and enforce domain invariants; queries return authorized projections without
changing state. Keep a command/query beside its handler; do not add a capability
wrapper around a single action. Use `shared/` only for contracts genuinely shared
by several use cases. Prefer names such as `renew_lease` and `issue_api_token`
over generic `service`, `manager` or `utils`.

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
  `developer_platform/authorization.py`. API routes check them before dispatch;
  HTTP and non-HTTP hosts check again using freshly authenticated access. Platform
  application handlers do not repeat these transport permission checks. Loaded
  resource/application ownership, readiness, quota and idempotency remain enforced
  by domain and persistence rules within the operation transaction.
- Each bounded context exposes a typed module contract with async `execute(command)`
  and `query(query)` entry points. The context owns an explicit message-to-handler
  registry and adapters under `containers/`; a request-scoped dispatcher resolves
  only the selected handler. The composition root binds an HTTP host wrapper to the
  module contract. Routes do not select or construct handlers. Application messages
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

Organize `src/api/` by HTTP-facing capability:

```text
api/
  app.py                 FastAPI setup and router registration
  dependencies.py        authentication and shared request dependencies
  errors.py              domain/application error-to-HTTP mapping
  identity/              internal users, sessions, tokens, memberships
  platform/              projects, catalog, resources, operations, workloads
  health/                liveness, readiness and metrics
```

Within a capability, group routes and request/response schemas by resource or
workflow when files grow; avoid one giant router or schema module. Keep common
API plumbing at the API root. DI bindings remain in context/host containers, not
in route modules. API routes call the context module contract; migrate affected
callers together when changing an existing contract.

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

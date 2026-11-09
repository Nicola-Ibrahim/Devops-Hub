# Backend architecture

Follow the root [AGENTS.md](../AGENTS.md). The backend uses Python, FastAPI,
SQLAlchemy and Alembic over PostgreSQL. See [README.md](README.md) for commands.

## Dependency direction

```text
api / containers  ->  application  ->  domain
          |                ^             ^
          +----------->  infra  ----------+
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
- `containers` constructs handlers/adapters and owns request or worker transaction
  completion. Providers must not define application services. A context may expose
  a module facade for API and worker callers.
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
- Each bounded context may expose a typed module facade with `send_command` and
  `send_query` entry points. Define its contract with the context's application
  types; implement the module in context `infra/` and bind it through that
  context's `containers/` providers. It selects explicitly registered handlers
  and owns transaction completion. The module holds no business rules, HTTP
  schemas or hidden service locator; callers retain typed command/query inputs
  and outputs. A successful command commits once; a raised failure rolls back.
  External effects run after durable intent commits.

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

- Application handlers receive repositories and ports, never a unit of work.
  The HTTP/worker host owns one outer commit or rollback boundary.
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

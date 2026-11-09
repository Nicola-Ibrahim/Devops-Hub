# Backend guidance

Follow the root [AGENTS.md](../AGENTS.md). The backend uses Python, FastAPI,
SQLAlchemy and Alembic over PostgreSQL. See [backend setup](README.md) for commands.

`src/identity/` and `src/developer_platform/` are independent bounded contexts,
each with `application/`, `domain/` and `infra/`. `src/api/` owns HTTP,
`src/containers/` and each context's `containers/` own DI composition, outer
transaction completion and HTTP/worker hosts. `src/shared/infra/` owns technical
settings and SQL/UoW infrastructure.
The package name `developer_platform` remains the current import name; a rename
requires explicit contract migration. Do not create a top-level `platform` package.

Keep domain entities, value objects, aggregates, rules and repository interfaces
free of SQLAlchemy, FastAPI and providers. Application command/query handlers use
their own context's domain and narrow ports, never sessions, units of work or
concrete adapters. Context `infra/persistence/` owns ORM mappings and SQL
repositories. API handlers delegate to application handlers and never query ORM
sessions directly. Cross-context actor mapping, DI construction and request
commit/rollback belong at the host/composition boundary. Shared infrastructure
contains no context business rules. Prefer real business names and avoid empty DDD
wrappers or generic service classes.

Resource intent, idempotency, ownership, quota, lease, credentials and recovery
remain durable across worker restarts. External Docker/provider effects run outside
SQL transactions. A queued ledger row is not a provisioned database; prove
readiness, authorized connectivity and cleanup when claiming end-to-end acceptance.

Use [backend-development](../.agents/skills/backend-development/SKILL.md) for
domain, application, persistence or worker work and
[api-development](../.agents/skills/api-development/SKILL.md) for FastAPI routes and
contracts. Use both when a task crosses those boundaries. For architecture changes
also load [system-design](../.agents/skills/system-design/SKILL.md).

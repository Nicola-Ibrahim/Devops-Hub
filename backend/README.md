# Backend foundation

Python/FastAPI control-plane foundation. Phase 1 provides configuration, lifecycle
rules, versioned schema migrations, local administrative token issuance, health,
identity and catalog contracts. Resource provisioning and worker workflows are
planned in later phases and are not implemented yet.

## Source boundaries

```text
src/
  api/                       HTTP routes, schemas, injected query ports and errors
  identity/
    domain/                  Pure token and project-membership policies/status values
    application/             AuthenticateApiToken, IssueApiToken, RevokeApiToken + ports
    infra/persistence/       Identity-owned ORM rows and async token repository
    infra/                   Hashing, randomness and private file delivery
  developer_platform/
    domain/                  Resource states, lease and deletion rules
    application/             Catalog and resource permission contracts
    infra/persistence/       Platform-owned ORM rows; future provider adapters in infra/
  shared/infra/              Technical engine/session/UoW, metadata and readiness
  containers/                Declarative Dishka providers and typed completion adapters
  entrypoints/               Settings, schema registration and minimal HTTP/CLI hosts
```

Application services receive repositories, clocks and domain-facing interfaces.
They never receive a unit of work, SQLAlchemy session, DI container or HTTP request.
`ApiTokenRepository` supplies both token queries and writes through the same
operation-scoped adapter. `SqlAlchemyUnitOfWork` owns begin/commit/rollback/close
outside application code. The API receives ready query capabilities from Dishka;
there is no manually constructed global service bundle.

Dishka application scope owns the async engine/session factory and stateless
collaborators. Request/CLI scope supplies the repository, async session and use
cases. Each UoW executes once; repeated/concurrent use is rejected before work.
Enter a fresh scope for another operation. Independent requests never share
sessions. `CurrentIdentityQuery` materializes the public identity view before
commit; commit and close finish before the API returns a successful response.
Cancellation/errors roll back when possible and close the session; cleanup is
bounded and preserves the primary error. Connection loss during commit can leave
an uncertain outcome; a rollback attempt does not prove that commit never occurred.
The current HTTP routes perform no business writes. Future external workflows need
short explicit operation scopes around database phases, outside Docker/AWS waits.

`entrypoints.http:create_app` owns its normally created container/engine. A supplied
`AsyncEngine` remains caller-owned. A supplied container is also caller-owned and
must be closed explicitly on its owning event loop before that loop shuts down.
SQLAlchemy runtime persistence is async; Alembic uses
the sync engine separately. Startup never opens database connections or applies
migrations. Container/engine resources are created lazily and owned pools close at
shutdown. DI integration is pinned through the lockfile; tests can supply provider
overrides without real services.

Each context owns its mappings, repository implementations and schema changes in
its infrastructure; domain/application packages contain no SQLAlchemy. Both
contexts share a control-plane database and the central Alembic revision sequence.
All 11 tables, existing FKs and the frozen foundation migration are preserved.
Shared `audit_events` remains a documented compatibility exception; identity
repositories write its legacy adapter in the same transaction as token changes.
A future context-owned audit-storage transition needs forward migrations, backfill
and retention policy; this refactor does not move or split those tables.

Business names distinguish `ProjectMembershipStatus`, `ApiTokenStatus`,
`ApiTokenAuthenticationDetails` and `ApiTokenAuditEvent` from ORM rows such as
`InternalUserRow` and `ProjectMembershipRow`. No speculative entity/value-object
wrappers were added. Public API/CLI fields and database table names are unchanged.
The platform package remains `developer_platform` to avoid shadowing Python's
standard-library `platform` module. Cross-context actor mapping stays in the API;
neither context imports the other's internals.

Previous `bootstrap.*`, `platform_api.*`, `provisioning.*`, `platform_runtime.*` and
`platform_infrastructure.*` paths are retired. Use the new launch path below.
The `platform-admin` command/options, environment variables and HTTP contracts are
preserved. Internal account login/session management, local Docker provisioning
and the Next.js dashboard remain later work. External Google login is not planned.

## Install and configure

From this directory, use Python 3.12+ and `uv sync --frozen`. Dependencies are
locked in `uv.lock`. The backend does not implicitly read `.env` files or require
Doppler. Supply configuration through the process environment:

- `PLATFORM_DATABASE_URL`: `postgresql+psycopg` URL for the control-plane database.
- `PLATFORM_TOKEN_PEPPER`: a random secret with at least 32 characters. Keep it
  outside source control and preserve it across API/admin restarts. Changing it
  invalidates existing API tokens.
- `PLATFORM_ENVIRONMENT`: `local` (default), `test`, or `server`.

Provide an empty, dedicated PostgreSQL database before starting. Use a local
secret file or secret manager for the environment; do not paste real credentials
into commands, task records or commits. The ignored `.local/` directory can hold
private local files. It does not supply a database or load configuration itself.

Apply schema migrations explicitly:

```bash
uv run alembic upgrade head
```

Startup never creates tables or runs migrations. Start the API on loopback:

```bash
uv run uvicorn entrypoints.http:create_app --factory --host 127.0.0.1 --port 8000
```

`GET /health/live` checks the process; `GET /health/ready` checks database access
and the exact migration revision. API readiness does not establish provider or
worker readiness. OpenAPI is available at `/openapi.json` and `/docs`.

## Issue a local developer token

Run this restricted command only as an administrator with control-plane database
access. It creates the named user/project and developer membership if missing,
then issues a project-bound token. It never upgrades an existing membership role.

```bash
mkdir -p .local
chmod 700 .local
uv run platform-admin issue-token --user developer --project demo --output .local/developer-token
```

The token is written to a newly created file with mode `0600`. An existing output
file is never overwritten. Its ID is printed for later revocation; the credential
is not printed. Tokens expire after 24 hours by default (`--hours`, maximum 720).
Use repeated `--scope` arguments to restrict the default scopes. The database
stores a peppered hash, not the token value. Token issuance and revocation create
audit events. An interrupted issuance can leave a private file for a transaction
that never committed; revoke/reissue through the admin command rather than
assuming that file is valid.

Use the token as an HTTP bearer credential. `/api/v1/me` returns identity and
project membership; `/api/v1/catalog` requires `catalog:read`. The catalog is empty
until a provider passes capability verification. This release does not claim that
databases can be requested or provisioned. Resource request/view/renewal schemas
are defined for the next phase; their routes are not registered yet.

Token policy, hashing, persistence and private file delivery are separate
collaborators. The outer `IssueApiTokenToFile` coordinator delivers the private
application result before committing; application services never manage delivery
or transaction completion. Delivery failure rolls back identity/token/audit writes; a failed
commit removes only the newly created credential file. Compensation does not
delete a replacement file owned by another write. Abrupt termination and ambiguous
database commits still require administrative reconciliation; this is not an atomic
transaction across the database and filesystem. If commit succeeded but session
cleanup failed, the private credential file is retained; treat the failed command
as requiring administrative reconciliation rather than overwriting that file.

```bash
uv run platform-admin revoke-token <token-id>
```

Local bearer tokens are for the trusted demonstration. Remote deployment requires
protected transport, server configuration and a reviewed identity boundary.

## Verification

```bash
uv run --frozen ruff check src migrations tests
uv run --frozen ruff format --check src migrations tests
uv run --frozen mypy src
uv run --frozen pytest -q -m 'not postgres'
uv build --out-dir /tmp/devops-hub-build
```

To run PostgreSQL integration checks, set `PLATFORM_TEST_DATABASE_URL` to a
**disposable local database named `devops_hub_test` or beginning with
`devops_hub_test`** using the psycopg URL format, then run:

```bash
uv run --frozen pytest -q
```

These checks create and remove unique schemas in that database, run migrations,
and exercise token issuance/authentication/revocation. They refuse remote targets
and other database names. With no test URL, PostgreSQL checks are skipped; unit
checks alone do not establish migration correctness. CI supplies its own ephemeral
PostgreSQL service. Its trust authentication is restricted to the disposable
hosted-runner test setup and must not be used for a shared database deployment.

The current phase has no worker, Docker provisioner, resource workflow endpoints,
frontend or deployment. The remaining sequence is in the
[backend task record](../.codex/workflow/tasks/backend-workflows.md).

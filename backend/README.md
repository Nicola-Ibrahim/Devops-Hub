# Backend foundation

Python/FastAPI control-plane foundation. Phase 1 provides configuration, lifecycle
rules, versioned schema migrations, local administrative token issuance, health,
identity and catalog contracts. Resource provisioning and worker workflows are
planned in later phases and are not implemented yet.

## Source boundaries

```text
src/
  api/                       HTTP routers, schemas, dependencies and error mapping
  identity/                  Users, memberships and token authentication/administration
    domain/                  Pure identity rules and snapshots
    application/             Authenticate, IssueToken, RevokeToken and owned ports
    infra/                   Identity SQL, hashing, randomness and private file delivery
  developer_platform/        Platform resource management context
    domain/                  Resource states, lease and deletion rules
    application/             Catalog and resource permission contracts
    infra/                   Resource persistence records and future provider adapters
  shared/infra/              Neutral SQL metadata, engine, audit records and readiness
  bootstrap/                 Settings, composition, schema registration and CLI/HTTP hosts
```

Each application's workflows depend on their own domain and ports; infrastructure
implements those ports. Identity and developer_platform do not import one another.
The API maps a verified principal into the platform's access context and does not
receive ORM sessions. `bootstrap` wires concrete adapters and owns their
lifetimes. A caller supplying an engine to `create_app(..., engine=...)` retains
ownership of it; the normal factory disposes the engine it creates on shutdown.

Both contexts still share one control-plane database. Shared metadata registers
all 11 tables explicitly and retains the existing foreign keys and frozen initial
migration. Audit writes use the same transaction as their owning identity workflow.
Architecture tests enforce import boundaries and test applications with fake ports.

The platform context uses `developer_platform` to avoid shadowing Python's
standard-library `platform` module. Its catalog, resource rules and persistence
live together; shared technical infrastructure and cross-context composition are
kept outside the business context.

Previous internal `platform_api.*`, `provisioning.*`, `platform_runtime.*` and
`platform_infrastructure.*` Python paths have been retired. Use
`bootstrap.http:create_app` to launch; public HTTP contracts, the
`platform-admin` command/options, environment variables and database schema are
preserved. See the [boundary refactor record](../.codex/workflow/tasks/backend-boundaries.md).

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
uv run uvicorn bootstrap.http:create_app --factory --host 127.0.0.1 --port 8000
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
collaborators. Delivery failure rolls back identity/token/audit writes; a failed
commit removes only the newly created credential file. Compensation does not
delete a replacement file owned by another write. Abrupt termination and ambiguous
database commits still require administrative reconciliation; this is not an atomic
transaction across the database and filesystem.

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
uv build
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

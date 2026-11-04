# Backend developer platform

Python/FastAPI control-plane foundation. Phase 1 provides configuration, lifecycle
rules, versioned schema migrations, local administrative token issuance, health,
identity, project registration, a typed catalog and a durable resource-request ledger.
Resource workers, a local Docker PostgreSQL provider, lifecycle APIs, internal browser
identity are implemented. Application delivery code is present, with attachment
acceptance still tracked separately. Provider availability is operator
configured and defaults to disabled; verify the configured target before enabling it.
See [operations](../docs/operations.md) for packaging, release and recovery assets.

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
    infra/persistence/       Platform-owned ORM rows; Docker/provider adapters live in infra/
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
Resource request acceptance writes only the control-plane ledger. Workers use
short explicit operation scopes around database phases, outside Docker/provider waits.

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
The frozen foundation migration remains unchanged. Forward revision
`0002_request_ledger` adds teams, platform project registration/environments and
resource activity (15 tables total), plus a nullable legacy resource environment
reference. Existing project IDs survive; legacy registrations have unknown
team/repository and no invented environments until an operator configures them.
Shared `audit_events` remains a documented compatibility exception; identity
repositories write its legacy adapter in the same transaction as token changes.
A future context-owned audit-storage transition needs forward migrations, backfill
and retention policy; this refactor does not move or split those tables.

Business names distinguish `ProjectMembershipStatus`, `ApiTokenStatus`,
`ApiTokenAuthenticationDetails` and `ApiTokenAuditEvent` from ORM rows such as
`InternalUserRow` and `ProjectMembershipRow`. No speculative entity/value-object
wrappers were added. The OpenAPI snapshot intentionally extends the API with
request/read contracts; existing token and health response shapes remain unchanged.
The platform package remains `developer_platform` to avoid shadowing Python's
standard-library `platform` module. Cross-context actor mapping stays at the host/composition boundary;
neither context imports the other's internals.

Previous `bootstrap.*`, `platform_api.*`, `provisioning.*`, `platform_runtime.*` and
`platform_infrastructure.*` paths are retired. Use the new launch path below.
The `platform-admin` token command options remain available; issuing a token now
requires an existing project reference, created through operator registration. Internal account login/session management, local Docker provisioning and a Next.js
dashboard are present. External Google login is not planned.

## Install and configure

From this directory, use Python 3.12+ and `uv sync --frozen`. Dependencies are
locked in `uv.lock`. The backend does not implicitly read `.env` files or require
Doppler. Supply configuration through the process environment:

- `PLATFORM_DATABASE_URL`: `postgresql+psycopg` URL for the control-plane database.
- `PLATFORM_TOKEN_PEPPER`: a random secret with at least 32 characters. Keep it
  outside source control and preserve it across API/admin restarts. Changing it
  invalidates existing API tokens.
- `PLATFORM_ENVIRONMENT`: `local` (default), `test`, or `server`.
- `PLATFORM_INSTALLATION_ID`: stable UUID for enabled resource acceptance.
  Do not generate a different UUID on each restart. Missing installation identity
  fails closed; setting it alone does not enable the provider.

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

## Register a project (trusted operator only)

After explicitly applying the migration, use the restricted operator CLI:

```bash
uv run platform-admin register-project --name demo --team platform --repository example/demo --environment dev --environment test
```

It atomically registers identity references and platform-owned metadata, prints the
project/environment IDs and creates the initial project budget: three resources,
2000 CPU millis, 2 GiB memory and 5 GiB storage reservations. It grants no team/user
membership automatically and creates no database/container. Same configuration is
idempotent; changed configuration conflicts rather than overwriting ownership.
Target budgets are not auto-created. Missing target quotas fail closed. Global
operator privileges are deliberately not inferred from a project-admin token;
there is no public project-creation endpoint in this increment.

Legacy project IDs/names are preserved by the migration. Run the same registration
command with their actual team/repository/environments to complete metadata. Team
ownership is separate from explicit project membership. Platform owns registration
and environments; identity owns team/access references and credentials.

## Issue a local developer token

Run this restricted command only as an administrator with control-plane database
access. Register the project first. Token issuance creates the named user and
developer membership if missing, then issues a project-bound token. It never upgrades an existing membership role.

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
project membership; `/api/v1/catalog` requires `catalog:read`. The catalog lists a
approved PostgreSQL 16/local/small option with typed CPU/memory/storage/lifetime
limits, disabled-by-default requestability (`provider_not_enabled`) and storage enforcement
`reservation_only`. Dedicated volumes do not imply hard disk quotas. Enable only after the verification command below succeeds.

## Resource request/read contracts

| Route | Behavior |
| --- | --- |
| `GET /api/v1/projects` | The registration visible to the current project-bound bearer token |
| `GET /api/v1/projects/{project_id}` | Configured or legacy project metadata and environments, scoped to that token |
| `POST /api/v1/resources` | Requires `Idempotency-Key`; validates an approved option and atomically records request/operation/reservation/replay/audit; 202 with IDs and operation `Location` only after commit |
| `GET /api/v1/projects/{project_id}/resources` | Sanitized inventory with UUID `after` cursor and `limit` 1–100 |
| `GET /api/v1/resources/{resource_id}` | Authorized sanitized state/ownership/expiry/environment |
| `GET /api/v1/operations/{operation_id}` | Authorized durable operation progress |

The request JSON contains `project_id`, `environment_id`, `display_name`,
`template_id`, `version`, `target_id`, `size_id`, and `ttl_seconds`. Owner, raw image,
provider command, credentials and work-reference inputs are rejected. Disabled runtime options reject new requests with 503 `provider_unavailable`.
Catalog enablement also requires a persistent installation ID and encryption key;
requests fail closed if target quotas have not been configured.
Original accepted requests replay their IDs even if an option later becomes
unavailable; changed payload with the same scoped key returns 409.

A ready capability revalidates the private bearer inside the write transaction,
locking current token/user/membership state. It does not reuse `/me`'s completed
UoW. Project/target budget rows are locked in deterministic order and reservations
include all unreleased resources, including uncertain cleanup. Missing quotas fail
closed. PostgreSQL acceptance time is captured after lock waits, so lease and
operation deadlines start at acceptance. DTO validation/commit/close finish before
a successful response is emitted. No Docker/network effects occur in acceptance.

## Local PostgreSQL lifecycle

Keep a stable `PLATFORM_INSTALLATION_ID`, persistent private `PLATFORM_RESOURCE_KEY`
(Fernet key) and `PLATFORM_RESOURCE_KEY_ID` across process restarts. Losing the key
prevents credential recovery; never generate a replacement implicitly. Configure
`PLATFORM_DOCKER_URL` to the approved local Unix socket. On Docker Desktop this is
normally `unix:///Users/<user>/.docker/run/docker.sock`. The default is the Linux
`unix:///var/run/docker.sock`. Values also support `_FILE` configuration for the
control-plane URL, token pepper, installation ID, resource key/key ID and metrics token.

After explicit migrations and before catalog enablement, run:

```bash
uv run platform-admin verify-local-target --max-resources 10
```

This operator command provisions and deletes one owned probe, verifies SQL readiness
and cleanup, then records target reservation budgets. It requires Docker access and
is an explicit resource operation. Set `PLATFORM_LOCAL_PROVIDER_ENABLED=true` only
after success, then start the durable worker separately:

```bash
uv run python -m entrypoints.worker
```

API requests never call Docker. The worker claims durable operations, stores encrypted
credentials before effects, and reconciles owned objects on startup and periodically.
Loopback dynamic ports are discovered again after container restart. CPU/memory are
enforced; disk capacity is reservation accounting, not a hard volume quota.

| Route | Behavior |
| --- | --- |
| `POST /api/v1/resources/{id}/connection` | Owner/admin secret retrieval, no-store, audited; ready and unexpired only |
| `POST /api/v1/resources/{id}/renew` | `{expected_revision, expires_at}`; lease limits and revision conflicts enforced |
| `DELETE /api/v1/resources/{id}` | Retry-safe durable deletion, including database volume/data |
| `GET /api/v1/projects/{id}/activity` | Authorized sanitized lifecycle history |

Deletion and expiry revoke access by removing the owned database and storage. A
provider outage delays physical revocation; cleanup uncertainty retains capacity.
A queued ledger row is not a ready database.

## Internal browser accounts and dashboard

Use `platform-admin create-user --name <name>` (interactive password or private
`--password-file`), then `bootstrap-project-admin --user-id <id> --project-id <id>`
for the first project administrator. Setup recovery uses `issue-password-setup`
and `consume-password-setup`; `platform-admin --help` lists required arguments.
There is no public registration or social login.

The dashboard proxies same-origin requests to the API; configure its server-only
`BACKEND_URL`. Backend cookie mutations require an approved exact origin and CSRF.
For local HTTP only, explicitly set `PLATFORM_COOKIE_SECURE=false`; server deployments
use HTTPS with secure cookies. Sessions support project selection, logout, revocation
and password change. Browser permissions are revalidated within each operation.

## Application delivery

The API exposes approved `/api/v1/templates`, applications, resource attachment,
deployment history and durable step retry. Set `PLATFORM_TEMPLATE_ROOT` to the
versioned template directory and `PLATFORM_TEMPLATE_WORKFLOW_REPOSITORY` to the
approved company workflow repository. GitHub repository operations require configured
organization/token; deployment requires an explicit digest allowlist. Application/database
association and private-file runtime adapters are present. Complete attachment cleanup
and drift acceptance remain pending in
[task 08](../.codex/workflow/tasks/08-application-database-attachment.md); source presence
is not proof that the entire application deployment flow works. Missing configuration
fails closed, and disabled adapters report failure rather than external success.

Run `uv run python -m entrypoints.application_worker` separately for application steps.
Resources are requested through the same quota/idempotency ledger and database
worker. Preview events require a configured signing secret and registered repository;
untrusted forks are rejected. External GitHub/cloud end-to-end acceptance is separate
from local Docker verification.

## Real local acceptance test

With an explicitly disposable local `devops_hub_test*` PostgreSQL database, run:

```bash
PLATFORM_TEST_DATABASE_URL=<private-test-url> PLATFORM_TEST_DOCKER_URL=unix:///var/run/docker.sock uv run pytest -q tests/integration/test_postgres_docker_acceptance.py
```

The opt-in test creates UUID-labeled Docker resources and removes only its owned
objects. It verifies HTTP idempotency, restricted SQL access, interrupted claim
recovery, actual container restart, renewal and repeat-safe deletion. Without the
explicit Docker test variable it skips rather than calling a developer runtime.

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

The API, resource worker, local Docker provider and Next.js dashboard are present.
Historical local lifecycle acceptance does not establish complete application
attachment, host deployment or cloud readiness. Remaining feature and verification
scope is separated in the [numbered task index](../.codex/workflow/tasks/README.md);
finish one selected task at a time.

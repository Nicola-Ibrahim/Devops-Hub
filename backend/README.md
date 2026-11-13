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
  api/                        FastAPI app and HTTP layer
    router.py                 Root router for health and bounded contexts
    core/                     Shared errors, schemas, dependencies and security
      middlewares/            Request-boundary middleware
    settings/                 HTTP-only API and browser cookie settings
    composition/              HTTP-to-context adapters and API-only providers
    identity/                 Identity base router and feature route/schema packages
    platform/                 Platform base router and feature route/schema packages
    health/                   Health routes and operational metrics adapter
  identity/
    domain/                  Identity entities, value objects, aggregates, repository interfaces and policies
    application/             Identity use-case packages with command/query handlers
    infra/persistence/       Identity-owned ORM rows and account/session/membership/token adapters
    infra/composition/       Identity module dispatch, providers and container registrations
    infra/authorization/     Identity-owned OPA adapter
    infra/security/          Password, token and private credential adapters
    infra/hosts/              Identity HTTP and worker authentication adapters
  devops_platform/
    domain/                  Platform entities, value objects, aggregates, repository interfaces and policies
    application/             Capability-owned command/query handlers for catalog, requests, lifecycle and delivery
    infra/persistence/       Platform-owned ORM rows, transactional stores and read projections
    infra/composition/       Platform dispatch, providers and API/worker container registrations
    infra/templates/catalogs/ Versioned Python, Node.js and ASP.NET starter templates
    infra/observability/     Platform metric projections
    infra/workers/           Resource and application worker processes
    infra/providers/         Docker database/application and GitHub adapters
    infra/security/          Credential, approval, fingerprint and signature adapters
    infra/templates/         Filesystem template catalog
  shared/dispatch.py         Pure typed message/registry dispatch contract
  composition/               BackendContainer assembly and BackendRuntime lifecycle
    integrations/            Cross-context bridges and their DI provider
  migrations/                Alembic metadata discovery, environment and revisions
  shared/infra/              Technical engine/session/UoW and readiness
  shared/infra/settings.py   Runtime and database configuration
```

Application services receive repositories, clocks and narrow capability ports.
They never receive a unit of work, SQLAlchemy session, DI container or HTTP request.
Each identity capability owns its `command.py` or `query.py` and `handler.py`;
handlers translate inputs into domain value objects/policies and return application
results. Read handlers use repository projections without inventing write-domain
behavior. Transaction completion remains in the identity host/composition layer.

The developer-platform application follows the same convention: `resource_requests/`,
`resource_lifecycle/`, `project_registration/`, and `application_delivery/` are
capability boundaries. Each write action keeps its command beside its handler, each
read action keeps its query beside its handler, and `shared/` contains only technical
ports, projections, policies, and transport-independent values—not a general command
catalog.
`ApiTokenRepository` supplies both token queries and writes through the same
operation-scoped adapter. `SqlAlchemyUnitOfWork` owns begin/commit/rollback/close
outside application code. Business routes send typed messages to `IdentityModule`
or `DeveloperPlatformModule`; their explicit context registries select one handler
in the active request scope. Dishka registers factories at startup and constructs
selected dependencies lazily. There is no global service bundle or package scan.

Dishka application scope owns the async engine/session factory and stateless
collaborators. Request/operation scope supplies the repository, async session and use
cases. Each UoW executes once; repeated/concurrent use is rejected before work.
Enter a fresh scope for another operation. Independent requests never share
sessions. The identity HTTP host completes bearer authentication before returning
the public identity view; commit and close finish before a successful response.
Cancellation/errors roll back when possible and close the session; cleanup is
bounded and preserves the primary error. Connection loss during commit can leave
an uncertain outcome; a rollback attempt does not prove that commit never occurred.
Resource request acceptance writes only the control-plane ledger. Workers use
short explicit operation scopes around database phases, outside Docker/provider waits.

`api.app:create_app` owns its normally created container/engine. A supplied
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
The fresh `0001_initial_schema` baseline creates all 25 mapped tables for new
installations. It replaces the prior revision chain; existing databases stamped
with older revisions need a separately planned, data-preserving transition and
must not be stamped to the new head without schema verification. Resource
environment references remain nullable for unassigned records.
Shared `audit_events` remains a documented compatibility exception; identity
repositories write its legacy adapter in the same transaction as token changes.
A future context-owned audit-storage transition needs forward migrations, backfill
and retention policy; this refactor does not move or split those tables.

Business names distinguish `ProjectMembershipStatus`, `ApiTokenStatus`,
`ApiTokenAuthenticationDetails` and `ApiTokenAuditEvent` from ORM rows such as
`InternalUserRow` and `ProjectMembershipRow`. No speculative entity/value-object
wrappers were added. The OpenAPI snapshot intentionally extends the API with
request/read contracts; existing token and health response shapes remain unchanged.
The bounded-context package is `devops_platform`, avoiding a top-level `platform`
package that would shadow Python's standard-library module. Cross-context actor
mapping stays at the host/composition boundary;
neither context imports the other's internals.

Previous `bootstrap.*`, `platform_api.*`, `provisioning.*`, `platform_runtime.*` and
`platform_infrastructure.*` paths are retired. Use the new launch path below.
The operator command-line interface has been removed. Internal account/session APIs,
local Docker provider services and the dashboard remain. No replacement public
account bootstrap or target-administration endpoint is implied by this refactor.

## Install and configure

From this directory, use Python 3.12+ and `uv sync --frozen`. Dependencies are
locked in `uv.lock`. `Settings` and `APISettings` use Pydantic Settings and read
process environment values directly; values may come from a shell, container
runtime, a secret injector, or explicit constructor arguments. Dotenv files are
disabled by default. The application does not require Doppler or a specific secret
manager. Supply the required runtime values through those environment sources:

- `PLATFORM_DATABASE_URL`: `postgresql+psycopg` URL for the control-plane database.
  `DATABASE_URL` is also accepted for managed database integrations; plain
  `postgresql://` URLs are normalized to the installed psycopg driver.
- `PLATFORM_TOKEN_PEPPER`: a random secret with at least 32 characters. Keep it
  outside source control and preserve it across API/admin restarts. Changing it
  invalidates existing API tokens.
- `PLATFORM_ENVIRONMENT`: `local` (default), `test`, or `server`.
- `PLATFORM_INSTALLATION_ID`: stable UUID for enabled resource acceptance.
  Do not generate a different UUID on each restart. Missing installation identity
  fails closed; setting it alone does not enable the provider.

- `PLATFORM_DATABASE_CONNECT_TIMEOUT`, `PLATFORM_DATABASE_POOL_SIZE`,
  `PLATFORM_DATABASE_MAX_OVERFLOW`, `PLATFORM_DATABASE_POOL_TIMEOUT`, and
  `PLATFORM_DATABASE_POOL_RECYCLE_SECONDS`: connection and pool limits for each
  API/worker process. Size these against the database connection budget and the
  number of replicas.
- `API_CORS_ALLOWED_ORIGINS`: optional comma-separated or JSON array of exact
  browser origins for direct cross-origin API calls. Credentials are enabled only
  for those explicit origins; wildcard origins are rejected.
- `API_TRUSTED_HOSTS`: optional comma-separated or JSON array of accepted hostnames.
- `PLATFORM_BROWSER_ALLOWED_ORIGINS`: origins accepted by browser CSRF checks. For
  direct browser-to-API calls, configure this alongside `API_CORS_ALLOWED_ORIGINS`.

Secrets can be supplied as values or file paths such as `PLATFORM_DATABASE_URL_FILE`
and `PLATFORM_TOKEN_PEPPER_FILE`. A Vault agent or another injector can render files
and set those path variables, or inject values directly. In containers,
`PLATFORM_SECRET_FILES_ROOT` sets the trusted root for secret files; it defaults to
`/run/secrets`. File paths outside that root are rejected by the entrypoint. Keep
secret values out of command lines and diagnostic output.

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
uv run fastapi dev --host 127.0.0.1 --port 8000
```

`[tool.fastapi]` selects `api.asgi:app`. `DevOpsHubAPI` owns HTTP assembly and
uses cached Pydantic `APISettings` for metadata, CORS, trusted hosts and OpenAPI/docs routes. Override
these with `API_TITLE`, `API_VERSION`, `API_DESCRIPTION`, `API_OPENAPI_URL`,
`API_DOCS_URL`, `API_REDOC_URL`, `API_CORS_ALLOWED_ORIGINS`, and
`API_TRUSTED_HOSTS`. Tests may inject an `APISettings` instance directly.
`BackendRuntime`
builds the lazy dependency graph before middleware setup, then owns startup/shutdown;
startup does not connect to the database or perform provisioning. It closes only
containers it creates. Tests can inject settings, engines and caller-owned containers
through `create_app`. For production use `uv run fastapi run` (no reload).

The root API router includes one router per bounded context. Identity and Platform
each aggregate feature routers with their route and schema definitions together.
Shared HTTP behavior lives in `api/core/`; HTTP-only configuration lives in
`api/settings/`. API providers stay separate from context `infra/composition`
providers, and worker processes use a worker-specific composition factory.

Alembic alone discovers ORM metadata and changes schema. `migrations/metadata.py`
supplies Alembic `target_metadata`; API and worker runtime setup never registers
models, creates tables or runs migrations. Run migrations explicitly with the
Alembic command above.

`GET /health/live` checks the process; `GET /health/ready` checks database access
and the exact migration revision. API readiness does not establish provider or
worker readiness. OpenAPI is available at `/openapi.json` and `/docs`.

## Trusted administration services

Project registration, account bootstrap, password recovery and token administration
remain service capabilities at the HTTP host boundary (`api/composition/`). There is
currently no operator CLI or replacement administrative HTTP API for these actions.
A fresh installation therefore needs a separately authorized bootstrap integration;
guest dashboard access does not create an account or grant project permissions.

`RegisterProjectCommandHandler` retains atomic project/environment registration and
project quotas. `BrowserIdentityService` retains internal account and first-project-
administrator setup. Existing user-facing identity endpoints remain protected.
Missing target quotas continue to fail closed; do not write arbitrary quotas to
bypass provider verification.

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

Target verification and budget configuration require a trusted integration; the
former operator command has been removed. Do not enable an unverified target.
For an already configured target, start the durable worker separately:

```bash
uv run python -m devops_platform.infra.workers.resource_worker
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

Accounts must already exist through an authorized internal bootstrap integration.
The former operator commands for creation, initial membership and recovery have
been removed. There is no public registration or social login.

The dashboard proxies same-origin requests to the API; configure its server-only
`BACKEND_URL`. Backend cookie mutations require an approved exact origin and CSRF.
For local HTTP only, explicitly set `PLATFORM_COOKIE_SECURE=false`; server deployments
use HTTPS with secure cookies. Sessions support project selection, logout, revocation
and password change. Browser permissions are revalidated within each operation.

## Application delivery

The API exposes approved `/api/v1/templates`, applications, resource attachment,
deployment history and durable step retry. The versioned catalog is packaged under
`devops_platform/infra/templates/catalogs`; set `PLATFORM_TEMPLATE_ROOT` only to
override that directory. Each versioned template includes its own GitHub Actions
CI workflow. GitHub repository operations require configured
organization/token; deployment requires an explicit digest allowlist. Application/database
association and private-file runtime adapters are present. Complete attachment cleanup
and drift acceptance remain pending in
[task 08](../.codex/workflow/tasks/08-application-database-attachment.md); source presence
is not proof that the entire application deployment flow works. Missing configuration
fails closed, and disabled adapters report failure rather than external success.

Run `uv run python -m devops_platform.infra.workers.application_worker` separately for application steps.
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

Token revocation remains an internal service capability; no operator CLI is installed.

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

## Identity service boundaries

See [Identity services](../docs/identity-services.md) for the action catalog,
aggregate/repository ownership, session expiry and local OPA setup. Protected
Identity routes now require OPA; login remains available during policy outages.
Compose configures the OPA URL automatically. Database/schema readiness and
authorization readiness are exposed separately.

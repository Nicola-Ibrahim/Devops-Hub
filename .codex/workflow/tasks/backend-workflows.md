# Backend architecture and platform workflow plan

## Current state

- **Updated:** 2026-10-31, Europe/Berlin.
- **Authorized phase and scope:** the subsequent implementation request was applied to the designated next step, phase 1 foundation and contracts. Phase 1 is implemented and verified. Changes are in `backend/`, its new CI workflow, factual status/setup documentation and this record. Later phases remain planned; no resource provider, deployment or shared environment was exercised.
- **Next step:** phase 2 durable resource API workflows and PostgreSQL concurrency checks, using the contracts and schema now implemented.
- **Open decisions:** none blocking the local plan; default architecture and scope decisions are below. Actual server addresses, access credentials, network policy and GitHub installation details are required only before those later integrations. They must not be written into this record.
- **Baseline:** branch `main`, HEAD `39a2d874822786bf8925173119a3abec629ea23d`. Planning initially saw staged guidance plus unstaged/untracked requirement changes; these were staged externally before implementation. At implementation start the guidance, `AGENTS.md` and requirements were staged, while this task record was untracked. Existing staged content was preserved; coordinator did not stage, commit or otherwise mutate the index.
- **Latest verification:** full suite against disposable PostgreSQL 16.2: **62 passed, 33 subtests passed**, one dependency deprecation warning. After adding no-store headers for private API responses, focused unit checks: **51 passed, 33 subtests passed**, 11 integration cases deselected. Ruff, formatting, strict mypy, offline lock consistency and wheel/sdist build passed. Independent review found a test database routing guard issue; correction and 14 regression checks were independently re-reviewed successfully. Hosted CI, Python 3.12 runtime, Docker provisioning, Ansible and live server integrations were not executed. Local backend checks used Python 3.13.0.

## Goal and evidence

Build a Python API and worker that provision approved temporary PostgreSQL resources, securely deliver connection details, enforce ownership and leases, and recover from interrupted provisioning and cleanup. Next.js will consume the same API for the developer dashboard. The first complete demonstration runs on local Docker without AWS, Azure or Doppler accounts. Configured Docker servers follow as an additional provider transport; Kubernetes and cloud adapters remain future extensions.

### Observed execution paths

| Existing path | Evidence and consequence |
| --- | --- |
| Local startup | `scripts/dev/platform_dev/dev.py:main/handle_up` runs full Ansible setup, `sync_platform_workspace()` and `boot_platform_infrastructure()`. `tasks/infrastructure.py` runs Doppler-wrapped Compose. No per-request lifecycle or readiness probe exists. |
| Task engine | `scripts/dev/platform_dev/engine/core.py:Task` executes shell strings with `shell=True`, has no execution deadline or durable state, and prints command output. `TaskGroup` only times and groups logs. Do not reuse it to execute resource API inputs. |
| Local shutdown | `dev.py:handle_down` ignores shutdown/cleanup results and returns success; `main` ignores `handle_up=False`. Mocked checks reproduced both behaviors without shell execution. |
| Package CI | `.github/workflows/package-ci.yml` watches `src/**` and root metadata, while the package lives in `scripts/dev/`. Package CI and release both run `uv build` from a root without `pyproject.toml`. |
| Package metadata | `scripts/dev/pyproject.toml` refers to a package-local `README.md` that does not exist. No lockfile or tests are present. Actual package build remains unverified. |
| Image publishing | `.github/workflows/reusable-cd-docker.yml` builds/pushes images; it does not call deployment. It hardcodes a production environment. |
| Deployment | `infra/ansible/playbooks/deploy.yml` pulls and starts Compose under `app_root`. It has no image digest contract, migration gate, readiness verification or rollback flow. |
| Bootstrap paths | `doppler/tasks/sync.yml` resolves `.env` under `infra/`; `local_workspace/tasks/main.yml` resolves its Git hook under `infra/.git/hooks`, given the current playbook location. Neither matches repository-root guidance. |
| Bootstrap prerequisites | Roles are beside `playbooks/`, with no explicit role-path configuration or collection manifest. Homebrew/Windows modules require validation of collection availability. These are identified risks, not reproduced Ansible failures. |
| Secret handling | `infra/ansible/roles/doppler/tasks/main.yml` interpolates a configured token into a shell command without `no_log`. Secret sync does not specify restrictive file permissions. No secret values were accessed. |
| Documentation | `docs/platform-dev.md` describes task registration, transactional groups and `required_tools` absent from implementation. Onboarding references undefined `poe` tasks and absent Compose services. `docs/secrets.md` describes CI secret integration absent from the workflows inspected. |

The initial planning inventory contained no backend, HTTP API, worker, Compose definition, Dockerfiles, persistent resource records, frontend or automated tests. That historical baseline is superseded for the phase-1 backend by the implementation progress below. The worker, Docker provisioner and frontend remain unimplemented.

## Architecture decision

**Use a workflow-oriented modular monolith with a small domain layer.** Ship one Python package with two processes: API and worker/reconciler. Lifecycle and policy rules warrant explicit models; the repository does not yet warrant a full tactical DDD structure, separate microservices, event sourcing or generic repository frameworks.

Choose Python 3.12+, FastAPI/Pydantic for HTTP and schemas, SQLAlchemy 2 with psycopg and Alembic, and PostgreSQL for control-plane records. Use synchronous SQLAlchemy sessions with short transactions, one per request/worker unit. Resolve and lock compatible supported versions when implementing; do not infer current dependency versions from this plan.

Use PostgreSQL as the durable operation queue initially. Persist resource intent, capacity reservation, audit event and operation atomically. A separate worker claims due operations with row locks and `SKIP LOCKED`, processing at least once. Store retries, deadlines, claim tokens, heartbeat and claim expiry. This avoids a separate broker and the database/broker dual-write problem. Do not hold database transactions open while calling Docker. FastAPI in-process background tasks are not the durability mechanism.

```text
Next.js dashboard / developer CLI / trusted automation
                         |
                      HTTP API
                         |
         application workflows + pure lifecycle rules
                         |
      PostgreSQL: resources, operations, access, audit
                         |
              worker + periodic reconciler
                         |
             provider and secret adapters
                         |
      local Docker -> configured Docker server later
```

### Proposed code boundaries

```text
backend/
  pyproject.toml, uv.lock, Dockerfile, alembic.ini
  migrations/
  src/platform_api/
    api/             # routers, Pydantic schemas, auth dependencies, HTTP errors
    domain/          # resource states, lease rules, quota decisions, domain errors
    workflows/       # request, list/get, renew, delete, connection, reconciliation
    ports.py         # small provider/secret/clock contracts actually required
    adapters/
      persistence/   # SQLAlchemy models, explicit queries and transactions
      providers/     # Docker adapter and approved template renderer
      secrets/       # encrypted resource secrets and key references
    worker/          # claiming, dispatch, retry/heartbeat, periodic sweeps
    settings.py, bootstrap.py
  tests/{unit,integration,contract}/
infra/compose/        # control-plane services, local overrides and test harness
frontend/            # future Next.js consumer; not scaffolded in backend phase
```

Domain rules import neither FastAPI nor Docker/SQLAlchemy. Workflows coordinate explicit collaborators; adapters implement external I/O. HTTP maps outcomes to transport semantics. Avoid interface-per-class, a repository per table, service locators and catch-and-rethrow layers. Keep the existing `scripts/dev` package separate; improve it only within the later compatibility phase.

## Scope and invariants

- In scope: backend foundation, API contracts, identity/authorization, resource records, operation worker, local PostgreSQL provisioning, secure connection retrieval, quotas, leases, cancellation/deletion, reconciliation, audit and health/metrics; plan CI, release, deployment, server and PR workflows.
- Out of initial backend delivery: Next.js implementation, arbitrary containers/commands/targets, Kubernetes/cloud provisioning, production tenancy guarantees, billing, database backup/restore, and production SSO. The plan exposes contracts for later additions.
- Preserve existing reusable workflow inputs and CLI entry points where feasible; document and version any intentional incompatibility. Preserve all staged work and existing environments.
- Never execute untrusted API input through the existing shell task engine. Register approved images, templates and targets administratively. Only the worker has Docker access; the API and dashboard never mount the Docker socket.
- Control-plane PostgreSQL and its durable volume are distinct from disposable developer databases. Resource cleanup must never delete platform state or unrelated containers, volumes or networks.

## Contracts and workflow decisions

### Identity, policy and catalog

Start with administratively issued opaque bearer tokens for seeded local users and project memberships. Store token hashes, scopes and expiry; provision/revoke them through a restricted admin CLI that reads secrets without logging them. No owner identity supplied by the request body is trusted. Do not build public registration or a homegrown password/JWT issuer. Bind the demo API to loopback; require protected transport before server exposure. OIDC can replace token authentication behind the same principal contract later.

Use static, validated administrator configuration for templates, targets, sizes and per-project/target quotas first. Persist membership, usage/reservations and resource references. `GET` catalog responses expose capabilities, not target connection credentials. Developer requests cannot choose image URLs, Docker endpoints, host paths, mounts, arbitrary commands or firewall rules.

Default demo policy: one PostgreSQL template and one small size, a one-hour default lease, a 24-hour maximum total lifetime from acceptance and two active resources per project, with validated administrator overrides. Values are proposed plan decisions and need tests/configuration, not hardcoded promises about host capacity. Reserve count/CPU/memory/storage budgets transactionally, using project/target quota locks in consistent order; retain reservations for unresolved cleanup.

### Data and consistency

| Record | Minimum responsibility |
| --- | --- |
| Resource | UUID; project/owner; optional repository/PR/branch reference; immutable template/target/size snapshot; desired state; observed status; UTC created/expiry times; revision; provider identity; endpoint metadata; safe failure code; retained deletion tombstone |
| Operation | UUID; resource/revision; action; status; attempt count; next-attempt time; claim token/expiry; deadline; safe error; completion time |
| Idempotency record | Principal/project + route + key; canonical request hash; persisted response IDs; reject the same key with a different body |
| Usage/reservation | Project and target usage/budgets, held until verified cleanup or confirmed no allocation |
| Resource secret | Encrypted credentials, resource linkage, key ID/version; encryption key stored outside the database |
| Audit event | Actor, resource, action, outcome, timestamps and correlation ID; never credentials or raw provider errors |
| Integration delivery | Later: source identity, repository/PR binding, delivery ID and PR generation/tombstone for replay/order handling |

Use constraints for uniqueness and foreign keys; revisions/compare-and-swap guard stale updates. Operation insertion and resource mutations share a transaction. Provider calls happen outside it. Revalidate desired state and claim ownership before publishing results. Stale workers cannot overwrite current state; deterministic provider identities, provider-level name uniqueness and reconciliation handle side effects that finished after a claim expired. Do not claim exactly-once execution.

### API v1

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/catalog` | Available templates, targets, sizes, enforced capabilities and policies for the principal |
| `POST /api/v1/resources` | Require `Idempotency-Key`; body contains project, display name, template, target, size, TTL and optional work reference. Validate and reserve, then return `202` with resource/operation IDs and a `Location` |
| `GET /api/v1/resources` | Ownership/project-filtered, paginated inventory; status/expiry filters; no secret values |
| `GET /api/v1/resources/{id}` | Current state, revision, expiry, safe errors, connection method and operation link |
| `POST /api/v1/resources/{id}/renew` | Expected revision plus requested new expiry; enforce maximum total lifetime; deny expired/deleting resources; transactionally serialize with expiry |
| `DELETE /api/v1/resources/{id}` | Persist desired deletion and queue cleanup; cancels pending provisioning too. Return `202`, or `204` when already fully deleted |
| `POST /api/v1/resources/{id}/connection` | Owner/authorized project access; only ready, unexpired, desired-running resources. Audit retrieval and return DSN plus connection instructions with `Cache-Control: no-store` |
| `GET /api/v1/operations/{id}` | Authorized, sanitized progress and terminal outcome |
| `/health/live`, `/health/ready`, `/metrics` | Liveness, API readiness and restricted operational metrics; worker health/lag reported separately |

Schema fields and OpenAPI are canonical; a future Next.js client consumes them. Use UTC timestamps, UUIDs and stable error objects (`code`, safe `message`, `request_id`, optional field errors). Define `401`, `403` for forbidden project actions, `404` for concealed resource access, `409` for idempotency/state/revision conflicts, `422` for invalid catalog/lease requests, and `429` for policy capacity rejection. An offline provider is an observed asynchronous failure after acceptance, not a false successful allocation.

### States, request, readiness and deletion

Use `desired_state = running | deleted`; observed status is `pending`, `provisioning`, `ready`, `failed`, `deleting`, `cleanup_failed`, or `deleted`. Store deletion reason (`requested`, `expired`, `cancelled`, `pr_closed`, `provision_failed`) and progress separately. Expiry changes desired state to deleted; it is not evidence that teardown has finished.

1. **Request:** authenticate/authorize → canonicalize payload and check existing idempotency record → replay original IDs for the same body, or conflict for a changed body. Only a new request validates current capability/policy and reserves capacity before atomically persisting the resource/secret reference/operation/audit. Serialize concurrent new requests with unique constraints and replay the winning record. Replaying an accepted request does not consume quota again or fail because the original filled quota or the target/policy subsequently changed; revoked authorization still denies access. No Docker call in the request transaction.
2. **Provision:** claim operation → verify desired state, revision and deadline → generate/reuse encrypted credentials and deterministic names → discover existing owned objects before creation → ensure network/container/storage → check database login/readiness → persist endpoint/status/audit. Cap attempts and total provisioning time. Never extend the lease just because readiness was delayed.
3. **Failure:** classify validation, provider unavailability, timeout, identity conflict and application defect distinctly. Timeout after an external call is an unknown outcome, so discover before retrying. Partial allocation queues compensation; no resource becomes terminally released until cleanup is verified.
4. **Connection retrieval:** recheck authorization and unexpired state, decrypt only the resource credential, build a correctly escaped DSN, and record an audit event. List/status and audit serializers cannot serialize the secret. Block retrieval immediately after expiry/deletion request, independently of worker availability.
5. **Renew:** compare revision and expiry in one transaction. Renewal succeeds only before expiry/deletion wins. It does not override an already accepted cleanup operation.
6. **Delete/cancel:** persist desired deletion even during provisioning. Worker stops new allocation, disables/removes access, stops/deletes owned runtime objects, removes disposable storage/network and secret, then confirms absence. Retain deletion tombstones with resource identity and ownership labels (no credential values). Track in-flight and uncertain provider calls explicitly: expired worker claims or a single absence observation do not prove an issued create has finished. Keep cleanup pending and capacity reserved until outstanding outcomes are resolved and owned objects are absent; unresolved attempts become visible `cleanup_failed`, not false completion. Any administrative override requires explicit disposition of the uncertain outcome. A late create is rediscovered and removed before normal completion.
7. **Reconcile:** periodically enqueue expired leases, reclaim abandoned operations, inspect owned partial allocations and retry bounded cleanup. Ownership scans also include retained deleted-resource tombstones, so an anomalous late object reopens cleanup and is reported rather than silently ignored. Tombstones are retained indefinitely initially; any later retention policy must preserve replay and late-result protection. Preserve a visible cleanup failure after retry exhaustion and permit an administrator to request another attempt. Never use a global Docker prune.
8. **Drift:** inspect ready resources periodically. Unexpected absence or failed readiness becomes a visible failure. Do not silently recreate a database and present it as retaining its previous data.

Expiry enforcement is asynchronous for already established database sessions: API access can stop immediately, but runtime revocation needs a reachable worker/target. Measure lag and alert; target outages cannot guarantee exact-time physical deletion. Initial healthy-runtime acceptance target: expiry detected within 30 seconds and cleanup completed within 60 seconds for an idle small resource; verify rather than advertise before measurement.

### Provider and credential contracts

Provider boundary: `capabilities`, `ensure`, `inspect/find_owned`, `revoke_access`, and `delete`; structured outcomes contain IDs, endpoint data and safe failure classifications. Every operation carries platform installation ID, resource UUID and generation. Use these for deterministic naming and ownership labels across container, storage and network objects. Never adopt/delete a conflicting object whose ownership cannot be proved.

Use the Python Docker SDK with explicit per-target configuration and timeouts; do not mutate global Docker context. SDK compatibility and host-key behavior must be tested when adding SSH transport. A shared server is an administrator-registered target, never a developer-supplied host. SSH host-key verification and least-privilege administrative access are required. Docker access remains host-powerful, even with API validation; this demo does not establish hostile multi-tenant isolation.

Local managed database ports bind to loopback with dynamically allocated host ports. Worker readiness uses an approved SQL probe via Docker exec inside the owned database container, authenticating with resource credentials through a protected secret file rather than command-line passwords. The probe is fixed by the template and cannot run developer-supplied commands. Do not assume a container's host-gateway route can reach a host loopback-bound port. Host-side integration tests separately connect with the advertised DSN. For server targets prefer remote loopback binding plus documented SSH tunnel access first. A DSN uses the tunnel's local endpoint, with tunnel instructions supplied separately. Direct VPN access/TLS requires an explicitly configured and tested target policy. Never return an internal container name as universally reachable.

Resource users receive dedicated non-superuser database credentials. Keep bootstrap/admin credentials separate. Store generated secrets encrypted with an external key and redacted representations; mount runtime secret material only into the worker/resource initialization path as needed, never CLI arguments or ordinary operation payloads. Raw Docker inspection and provider stderr are not public logs. The API can read authorized resource secrets but never provider-admin keys.

For bounded local disposable data, choose an explicitly ephemeral PostgreSQL template backed by a size-limited tmpfs mount on the Linux Docker runtime (including Docker Desktop's Linux VM, subject to validation). CPU/memory are also capped; tmpfs consumption counts within memory. A stopped/restarted database container can lose that data: show this in catalog and connection instructions and never confuse worker restart with database durability. The control-plane database uses persistent storage. Validate image paths, ownership and memory sizing in the provider spike. Ordinary named volumes are not advertised as hard storage quotas. Persistent developer databases require a tested quota-capable storage profile before being added to the catalog.

## CI/CD and operational workflows

| Workflow | Planned behavior and gate |
| --- | --- |
| Backend PR CI | Correct paths under `backend/**`, relevant infra/shared workflow changes; locked dependencies; Ruff, type checks, unit/contract tests; PostgreSQL integration tests for real transaction/locking behavior |
| Docker lifecycle CI | Ephemeral runner-owned control plane + managed database objects; request/connect/expiry/delete and crash-recovery checks; unique run labels; `always()` scoped teardown and verification, sanitized diagnostics on failure |
| Existing CLI/package CI | Trigger on `scripts/dev/**` and workflow edits; use its actual working directory; fix package README and dependency/lock strategy; mock operational commands for exit-code tests |
| Workflow validation | Validate Actions YAML with actionlint and Ansible syntax/roles/collections in an isolated configured environment; preserve caller input compatibility and test nested working-directory/cache paths |
| Frontend CI later | Next.js type/lint/test/build in `frontend/`; OpenAPI compatibility and browser smoke against the same API, no Docker/provider keys in Next.js |
| Image release | Trusted default-branch/tag jobs run required CI, build immutable backend/worker image (same package, different command), scan it and publish to GHCR; record digest/provenance. Frontend image follows when it exists |
| Python distribution | Existing `pypi.pkg.github.com` target is unsupported by GitHub's documented registries. First use GitHub release wheel/sdist artifacts for the CLI; a real PyPI/internal registry can be configured separately if requested |
| Local start/stop | One documented Compose entry point; generate local secrets without printing them; run explicit migration job before readiness; stop preserves control-plane data and does not globally destroy managed resources |
| Server setup/deploy later | Ansible prepares a registered Linux target, protected transport and runtime config. Deploy tested image digests; run explicit migration gate; verify API/worker readiness and preserve previous digest/config. App rollback only when schema-compatible; destructive migration rollback requires a separate recovery decision |
| PR automation later | Signed GitHub webhook metadata triggers resource workflows; delivery deduplication, repository/project allowlist and closed-PR tombstones prevent stale/replayed creates. CI runs untrusted code only with isolated test resources, never shared target credentials |

Repair bootstrap role/collection paths, unsafe token logging, secret file location/permissions and hook exit behavior within the compatibility phase. Preserve Doppler as an optional integration for existing consumers; the new local path must not require an external secret account. No automatic host tool installation occurs as a side effect of an API request.

Hosted CI cannot call a private laptop API. Initial PR-lifecycle verification replays signed fixture events against a runner-local API and checks cleanup. Live GitHub-to-server integration requires a reachable protected endpoint and a configured integration identity; it is not claimed by local tests. PR comments may link resource status, never contain a DSN/password. Do not execute PR code in a privileged metadata/webhook workflow.

## Acceptance criteria

### Planning completion (historical planning-only scope)

- [x] Repository baseline, execution paths, failure paths and investigation limits recorded.
- [x] Architecture selected with explicit domain/workflow/provider boundaries.
- [x] API, lifecycle, consistency, security and provider contracts described.
- [x] Ordered phases, ownership, dependencies and measurable implementation checks defined.
- [x] Only this task record changed by the coordinator; existing staged work preserved.

### Future implementation gates

- [ ] A clean checkout starts a documented local API, worker and control-plane database without cloud/Doppler credentials; schema migrations and readiness are explicit.
- [ ] Authorized developer requests a database, polls readiness, retrieves a protected connection string and performs SQL from the documented host location. Two resources have separate credentials/data/access paths.
- [ ] An unauthorized principal cannot inspect, mutate or retrieve another project's resources. Catalog rejects unregistered targets/images/sizes and unsupported storage profiles.
- [ ] Duplicate/concurrent idempotent requests allocate once; reused key with different input conflicts. A request that fills quota still replays successfully when retried with the same key/body. Concurrent quota requests cannot exceed reserved budgets.
- [ ] Worker restart after allocation but before database update discovers the existing resource; API/worker restart retains control-plane state and pending operations.
- [ ] Renew/expiry and cancellation/create races converge to the accepted desired state with no untracked objects. Late stale-worker outcomes cannot overwrite current state.
- [ ] Expiry blocks new credential retrieval immediately; healthy-runtime cleanup meets the measured 30/60-second target. Failed cleanup remains visible and does not prematurely release capacity.
- [ ] Delete is retry-safe after partial failure and already absent objects; platform objects and unrelated Docker resources remain untouched. Pause a create call, request cleanup and observe absence, then deliver the late create: cleanup must converge without premature capacity release. Deleted-resource ownership scans must also detect and remove late anomalies.
- [ ] Resource secrets are absent from inventory/status/errors/logs/CI diagnostics; connection retrieval is audited and non-cacheable.
- [ ] CPU/memory and advertised storage bounds are verified. Ephemeral data-loss behavior is documented; no claim of persistent storage quotas without enforcement.
- [ ] PR CI exercises the lifecycle in isolated runner resources and cleans its own objects even after test failure. Publishing and deployment are separate, truthful workflows.
- [ ] Server and live PR integration are marked unverified until exercised on configured reachable infrastructure with appropriate authorization.

## Plan, dependencies and file ownership

The initial planning request authorized no implementation. The subsequent implementation request has now completed phase 1, the designated starting scope, including its backend CI definition. Later phases below remain future work.

| Phase | Deliverable and checks | Assigned ownership when authorized | Depends on |
| --- | --- | --- | --- |
| 1. Foundation and contracts — complete | Backend package/settings, FastAPI/OpenAPI, error/principal contracts, pure lifecycle/lease rules; initial PostgreSQL schema and Alembic migrations; auth bootstrap; API schema/unit tests and migration smoke in isolated DB | Coder owned domain rules/tests; coordinator integrated API/persistence/admin/package/CI/docs | This plan |
| 2. Durable API workflows | Request/list/get/renew/delete/operation endpoints, idempotency, project policy, transactional reservations and audit; concurrent PostgreSQL tests; fake provider only | Coder: backend workflows/API/persistence/tests, one bounded file set per assignment | Phase 1 |
| 3. Worker and provider spike | Durable operation claims, bounded retry, fencing and reconciliation; fake-provider fault tests; verify local Docker SDK, networking/readiness path, bounded tmpfs and secret bootstrap behavior | Coder: backend worker/provider/tests; coordinator owns `infra/compose/` integration with explicit non-overlapping assignments | Phase 2 |
| 4. Complete local lifecycle | Real Docker PostgreSQL, protected DSN retrieval, expiry/cancellation/cleanup, metrics; request/connect/delete and worker crash-recovery demonstrations | Coder: assigned provider/secret/lifecycle tests; coordinator integrates Compose and docs | Phase 3 |
| 5. CI and tooling compatibility | Fix package paths/distribution, CLI failure propagation, Ansible secret/path/module issues and docs; add backend/lifecycle validation and trusted image release | Coder: explicit `.github/workflows/`, `scripts/dev/` or `infra/ansible/` subsets; coordinator checks existing contracts/docs | Backend CI begins at phase 1; full lifecycle gate needs phase 4 |
| 6. Dashboard contract handoff | Generate/version OpenAPI consumer contract; document resource states, safe errors, connection reveal and token/session expectations for Next.js; no frontend scaffolding unless separately requested | Coordinator: contract/docs; coder only assigned schema compatibility work | Phase 4 |
| 7. Configured server delivery | Docker-over-SSH target, network/tunnel instructions, deployment/migration/rollback flow, dedicated integration checks | Coder: assigned provider transport/Ansible/tests; coordinator owns target registration and authorized integration | Phase 4; actual server details/access |
| 8. PR lifecycle integration | Signed/deduplicated events, closed-PR ordering, runner-local tests; optional live integration only after endpoint setup | Coder: assigned API integration/tests/workflows | Phases 4–5; live setup needed only for external validation |

Sequence contract and schema changes before dependent implementation. Within a phase, parallelize only disjoint modules with settled interfaces. Investigator may investigate new uncertainties; coder receives explicit paths, baseline, criteria and safe checks; reviewer checks the actual resulting diff; main agent integrates and updates this record. Do not treat agent summaries as test evidence.

## Decisions and deferred inputs

- Architecture, framework, durable queue and first provider/storage profile are selected above; no architecture question is deferred back to the user.
- Local auth is scoped to a trusted portfolio demo with explicit user/project tokens. Broader company use needs an external identity/SSO decision and a reviewed deployment boundary.
- Local Docker capacity and networking must pass the phase 3 spike before advertising a runnable profile. If bounded tmpfs or networking is unsupported on the selected engine, report the failed capability and revise the profile explicitly; do not silently drop limits.
- A real server, SSH identity, host trust, network policy and GitHub integration configuration are deferred inputs for phases 7–8. They are not required for phases 1–6.
- Persistent database storage, production availability, disaster recovery, hostile tenant isolation and full preview environments are future scoped designs, not implied guarantees of the first release.

## Verification and review

### Phase 1 implementation progress

- Added a locked installable `backend/` package using FastAPI, SQLAlchemy, psycopg and Alembic. Settings require an explicit PostgreSQL URL and token pepper; secret settings are masked and `.env` is not implicitly loaded.
- Added pure domain rules for status transitions and UTC leases. Deletion needs deletion intent, provider-confirmed absence and resolved outstanding provider operations. Expired or inconsistent leases cannot be renewed; tombstones can reopen cleanup.
- Added 11 control-plane tables and a frozen initial migration for users, projects, memberships, tokens, resources, operations, idempotency, quotas, reservations, encrypted-secret records and audit. Future workflows are not simulated by these records. API startup never migrates or creates tables.
- Exposed `/health/live`, `/health/ready`, `/api/v1/me` and `/api/v1/catalog`. Readiness checks the migration revision. Catalog is deliberately empty until provider capabilities are verified. Resource request/renewal/view contracts exist in `api/schemas.py`; their routes are not registered yet.
- Added project-bound, scoped bearer token authentication, membership/user/expiry/revocation checks, safe errors and request IDs. Private API responses are non-cacheable. Admin issuance writes an exclusive mode-0600 token file and stores a peppered hash; revocation/issuance create audit events. This remains trusted local-demo authentication.
- Added unit/contract tests, isolated PostgreSQL migration and authentication tests, backend CI and setup/status documentation. Existing CLI/Ansible/workflows were not repaired in phase 1.
- Preserved the architecture decision: workflow-oriented modular monolith with a small pure domain layer. No separate domain framework, generic repository hierarchy or broker was introduced.

### Phase 1 actual checks

| Command/check | Actual result | Scope and limits |
| --- | --- | --- |
| `UV_CACHE_DIR=/private/tmp/devops-hub-uv-cache uv lock --python python3` and `uv sync --frozen --python python3` in `backend/` | Resolved 39 packages; installed locked environment | PyPI access required sandbox escalation; Python 3.13.0 used locally. Host tools were not installed globally |
| `backend/.venv/bin/pytest -q backend/tests/unit/test_domain.py` by coder | 26 passed, 33 subtests passed after domain corrections | Assigned domain files only |
| `python3 /private/tmp/devops-hub-foundation-pg-check.py` | 62 passed, 33 subtests passed in 1.33s | Disposable PostgreSQL 16.2 binaries from `pgserver==0.1.4` in `/private/tmp`; socket-only cluster, isolated test schemas and database, stopped/removed in `finally`. Escalation required for local shared memory/socket. No shared DB accessed |
| `.venv/bin/pytest -q -m 'not postgres'` after final private-response header change | 51 passed, 33 subtests passed, 11 deselected | Focused unit follow-up; full PostgreSQL checks above preceded the header-only change |
| `.venv/bin/ruff check src migrations tests`, `ruff format --check src migrations tests`, `.venv/bin/mypy src` | Passed; 25 Python files formatted, 18 source files type-checked | Backend scope only |
| `UV_CACHE_DIR=/private/tmp/devops-hub-uv-cache uv lock --check --offline` | Passed | Project and lock consistent |
| `UV_CACHE_DIR=/private/tmp/devops-hub-uv-cache uv build`, then final `uv build --offline` | Wheel and source distribution built | Build backend fetched with escalation initially; final build used cache. Wheel contains API/domain code; sdist includes migration assets. Migration instructions assume the backend source checkout |
| New workflow YAML parsed with PyYAML; `git diff --check`; local README/task links inspected | Passed | New workflow has read-only token permissions and a disposable PostgreSQL CI service. GitHub-hosted execution/actionlint not run |
| `docker info --format '{{.ServerVersion}}'` | Local Docker socket absent | No Docker runtime or provider validation claimed; disposable PostgreSQL process used for phase-1 tests instead |

One remaining third-party warning: Starlette deprecates its HTTPX-based TestClient path in favor of HTTPX2. Checks still pass; no warning was suppressed. CI selects Python 3.12 and PostgreSQL 18; those exact hosted versions have not been exercised locally.

Independent implementation review found one P2: URL authority `localhost` could be overridden by libpq query options in the test harness, violating the local-test safeguard. The guard now validates the effective destination, rejects non-host query overrides, duplicate hosts and relevant service/host-address environment overrides. Fourteen regression/allow-list cases pass, and focused independent re-review found no remaining bypass within that correction.

Final implementation snapshot (35 source/config/test/documentation files, excluding this record, environments, caches and build outputs): SHA-256 `f3aa1234449c6ddbcbfdb87a4124c2fdf0219fdcdaf6cfdae0e67d57dfd8b545`. This is a final handoff fingerprint, not a claim that the earlier review used these exact bytes.

### Historical planning checks

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| Branch/HEAD/status and staged/unstaged inspection | Recorded above; existing staged state preserved | Index changed externally during investigation; no coordinator Git mutation |
| Coordinator code inspection | Confirmed absent backend and traced all five Actions workflows, CLI/task engine, bootstrap/deploy paths and requirements | Static inspection; no runtime integrations |
| Pure mocked CLI checks | Confirmed `main()` returns normally after `handle_up=False`, and `handle_down()` returns True when shutdown and cleanup return False | `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts/dev python3`; patched `sys.argv`, handlers and command-calling helpers; no shell commands executed |
| Investigator | Independent read-only investigation completed | No tests or operational commands; not a review of this plan |
| Plan review | Three P2 contract issues corrected; focused independent re-review confirmed all three resolved | Static architecture review; re-review scope was the three corrections; no implementation correctness claim |
| Record validation | Whitespace and local links passed; `git diff --check` passed | Documentation checks only |

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/backend_investigator` | Explicitly supplied and read `.codex/agents/investigator.toml`; automatic custom-role loading not claimed | `main` / `39a2d874822786bf8925173119a3abec629ea23d`; relevant staged/unstaged content at its inspection | Traced CLI, workflows, Ansible and docs read-only; confirmed failure propagation, missing backend and CI/packaging/bootstrap gaps; recommended small lifecycle model and durable workflow application; no file edits, runtime tests, provisioning or deployment |
| `/root/backend_plan_review` | Explicitly supplied and read `.codex/agents/reviewer.toml`; automatic custom-role loading not claimed | Same HEAD; untracked draft and corrected task record against current guidance/requirements | Independently found three P2 contract gaps. Focused re-review confirmed corrected readiness probe location, idempotent replay ordering and retained tombstone/in-flight outcome rules, including acceptance cases. No remaining issue within those corrections. Read-only architecture review; no runtime commands or edits |
| `/root/foundation_domain` | Runtime-selected `coder` role (configured Luna/medium), task-specific instructions supplied | Same HEAD; owned only `backend/src/platform_api/domain/` and `backend/tests/unit/test_domain.py` | Implemented pure rules; coordinator requested same-state/deletion-confirmation and inconsistent-lease guards; coder corrected them and reported 26 tests/33 subtests plus Ruff checks. Other backend files left untouched |
| `/root/foundation_review` | Runtime-selected `reviewer` role and repository reviewer guidance | Same HEAD; new untracked backend files and backend CI workflow, excluding unrelated staged guidance | Independently reviewed actual implementation; ran 37 initial unit tests/33 subtests. Found the P2 test-routing issue; focused re-review ran 14 guard tests and confirmed it resolved. No database/provisioning operations or edits by reviewer |

### Primary documentation supporting decisions

The architecture is the coordinator's design judgment for this repository. These sources verify specific mechanisms, not the whole design:

- FastAPI documents background tasks executing after an HTTP response. Selecting a separate durable worker here is a recovery requirement, not a claim those tasks are durable: [Background tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/).
- PostgreSQL documents `SKIP LOCKED` for queue-like consumers, while warning against treating its view as general-purpose consistent reads: [SELECT locking](https://www.postgresql.org/docs/current/sql-select.html).
- SQLAlchemy requires separate sessions for concurrent units of work: [Session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html).
- Docker documents SSH/TLS daemon access and its permissions: [Protect access](https://docs.docker.com/engine/security/protect-access/). Its Python client exposes explicit connection configuration: [Docker SDK client](https://docker-py.readthedocs.io/en/stable/client.html).
- Docker documents tmpfs size limits and loss on container stop; memory sizing remains part of provider validation: [tmpfs mounts](https://docs.docker.com/engine/storage/tmpfs).
- GitHub's registry list excludes a Python/PyPI registry: [GitHub Packages](https://docs.github.com/en/packages/learn-github-packages/introduction-to-github-packages).
- GitHub describes the risks of executing untrusted PR code with privileged workflow access: [Secure PR event handling](https://docs.github.com/en/actions/reference/security/securely-using-pull_request_target).

## Handoff

- Completed: planning, phase-1 backend foundation/contracts, independent implementation review, guard correction, isolated PostgreSQL verification and package/static checks.
- Remaining: phases 2–8. Resource workflows, worker, providers, Docker runtime validation, Next.js integration and server/PR workflows remain unimplemented. The historical CLI/Ansible defects remain for phase 5. No deployment, shared resource provisioning, production-secret changes, staging or commits occurred.
- Next concrete action: phase 2 request/list/get/renew/delete/operation workflows with idempotency, atomic quota reservations and PostgreSQL concurrency tests using a fake provider. Preserve the verified phase-1 contracts and all unrelated staged changes.

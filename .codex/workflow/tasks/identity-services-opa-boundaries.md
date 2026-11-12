# Identity services and OPA authorization boundary

## Current state

- **Updated:** 2026-11-12.
- **Authorized phase and scope:** Implementation authorized by the user's subsequent implement request; Identity refactor, OPA contract/adapter, Identity HTTP enforcement and local Compose configuration. No live provisioning or deployment.
- **Next step:** Complete final checks and then run PostgreSQL concurrency and Docker acceptance in an explicitly configured disposable environment when available.
- **Open decisions:** Global user-admin HTTP authorization and durable policy-decision retention remain future requirements; no global administrator role or new automation-token administration was invented.
- **Baseline:** `main` at `181c8a7`; working tree has extensive staged/unstaged platform changes and Identity repository edits. Preserve all existing work.
- **Latest verification:** Follow-up cleanup: 48 affected tests passed; Ruff lint/format passed (351 files), mypy passed (303 source files). The full cleanup run had 253 passes and one stale synthetic-import fixture failure; that fixture was fixed and included in the passing affected run. Earlier OPA policy and Compose checks remain valid because their implementation did not change. Docker/PostgreSQL acceptance remains pending.

## Goal and evidence

Define the complete internal Identity service catalog, name use cases by the action they perform, and establish a Docker-hosted OPA authorization adapter. Existing application folders include `browser_login`, `browser_sessions`, `internal_users`, `project_memberships`, `issue_api_token`, `revoke_api_token`, and `authenticate_api_token`. Existing domain objects include `identity_account`, internal users, sessions, tokens, memberships, roles, scopes, and expiry value objects. Infrastructure contains SQLAlchemy persistence, security helpers, and module composition. These are code-presence facts, not proof of complete behavior. OPA is a proposed addition; its implementation and policy coverage require tracing.

## Scope and invariants

- In scope: assess and rename Identity use cases; define missing internal authentication, session, user, token, and membership capabilities; specify application/domain/infra ownership; add a narrow authorization decision port and Docker OPA adapter in a later implementation phase; map API enforcement points.
- Out of scope: social login, company SSO, platform resource lifecycle changes, live provisioning, deployment, new global user-admin HTTP endpoints and additional automation-token administration.
- Preserve internal credentials, session and token behavior, existing route contracts until callers migrate, host-owned transaction completion, and Identity/Developer Platform separation.
- Tokens have finite expiry and can be revoked. No token, password, or secret appears in policy inputs, logs, ordinary responses, or this record. Permission decisions default to deny when required identity, resource facts, policy, or OPA availability is missing.

## Proposed service catalog and layer ownership

| Capability | Application commands and queries | Domain rules and objects | Infrastructure |
| --- | --- | --- | --- |
| Login and session access | `login`, `logout`, `logout_all_sessions`, `refresh_session`, `rotate_csrf`, `authenticate_session` | Account status, credential version, session expiry and revocation | Password hashing, session/token storage, clock and persistence |
| User administration | `create_user`, `set_user_status`, `start_password_setup`, `complete_password_setup`, `change_password`, `bootstrap_first_admin` | User/account lifecycle, unique identity and password setup constraints | Account repository, password setup persistence, hashing |
| API tokens | `issue_api_token`, `list_api_tokens`, `revoke_api_token`, `authenticate_api_token` | Expiry, scope, revocation and account status | Opaque token generation/hash and persistence; never store plaintext token |
| Project membership | `list_project_members`, `set_project_membership`, `remove_project_membership`, `select_active_project` | Membership and role rules; project ID as external reference | Membership repository and read projections |
| Authorization decisions | API/host asks `authorize(actor, action, resource)` using trusted facts; no generic business handler required | Role and scope vocabulary; invariants remain in owning contexts | OPA HTTP client, policy bundle/configuration, bounded timeout, decision audit |

Names above are target vocabulary, not confirmed renames. In particular, split `browser_login` by action: `login` and `change_password`; split `browser_sessions` by distinct actions when tracing confirms handlers and callers. Keep `issue_api_token` and other already clear names. Avoid creating folders for absent capabilities until their behavior is specified.

### Use cases versus internal operations

- `login` is the user action: validate credentials and account status, create an expiring session, and return session data to the API. The API sets the secure cookie. Credential verification, secret generation, hashing and session persistence are collaborators or internal steps; they do not each require a public command or endpoint.
- `logout` revokes the current session. Password changes and user deactivation must define which existing sessions are invalidated, including concurrent requests; preserve credential-version protections while tracing this behavior.
- An automation API token serves a script or CI client independently of browser login. Its creation is a separate use case only when automation credentials are required. Treat new token administration capabilities as deferred pending that requirement; preserve existing token support. Session-token generation during login must not call the separate automation-token issuance workflow.
- A separate use case requires a distinct actor goal, input, outcome and failure contract. Sharing a technical helper does not create another use case. Do not add command/handler pairs solely for hashing, random generation, or each repository method.

### Naming and structure

Use action names such as `login/command.py`, `login/handler.py`, `logout/command.py` and `change_password/handler.py`. Keep each action's messages and result beside its handler. Group related actions only when that improves navigation; do not retain broad folders that mix unrelated handlers. Name shared technical interfaces by capability (`PasswordHasher`, `SessionSecretGenerator`, `AuthorizationDecisionPort`). Domain names describe accounts, sessions, memberships and their rules. Repository boundaries follow actual aggregates or transactional capabilities; a new file or entity does not automatically need a new repository.

### Request flow and failure behavior

1. Login API validates input and invokes the Identity module; credential checks and session creation follow the existing short transaction sequence around password hashing. Invalid credentials return a sanitized authentication failure. Define rate limiting and audit coverage during the trace.
2. For protected requests, authenticate the session/token and load current account and membership facts. The API/host evaluates OPA with trusted action/resource attributes and enforces the decision before business dispatch. No permission checks move into ordinary application handlers.
3. OPA deny maps to forbidden; unavailable or invalid policy evaluation maps to a sanitized service-unavailable response while access remains blocked. Unknown actions and absent policy results deny access. Public login and health routes need an explicit exemption list so an OPA outage does not accidentally make authentication itself depend on a prior permission decision.
4. The outer host owns transaction completion through the existing unit of work. Handlers, repositories, OPA adapters and DI providers never commit or roll back. Record the limit that an external policy decision is not atomic with database changes; revalidate relevant account/membership versions for sensitive mutations.

Before implementation, specify each retained use case's actor, input, success data, domain failures, side effects and transaction boundary. Record exact session lifetimes, cookie/CSRF behavior, invalidation rules, role/action rules and audit events rather than treating service names as a complete specification.

## Contracts and ownership

### Bounded contexts and domain model

Identity is one bounded context. Authentication, accounts, sessions and membership are capabilities inside it; they do not each need a separate bounded context or deployment. Developer Platform is a separate bounded context. OPA is a policy engine accessed through an adapter, not an aggregate or an additional business context.

| Boundary | Owns | References without owning |
| --- | --- | --- |
| Identity | Users, password credentials, sessions, membership roles, credential lifecycle and authentication facts | Platform project IDs |
| Developer Platform | Registered projects, databases, leases, operations and applications | Identity user IDs and authenticated actor facts |
| API/host authorization boundary | Trusted action/resource context, policy evaluation and enforcement | Identity facts, platform resource facts and OPA decisions |

Proposed Identity aggregate roots are below. Confirm existing persistence and concurrency behavior before changing repository contracts; naming alone is not evidence of an aggregate.

| Aggregate root | State and rules | Repository boundary |
| --- | --- | --- |
| `User` | User ID, validated username, active status and credential version; controls account activation and credential changes | `UserRepository`; account persistence and version-checked updates. Password credentials belong to the account lifecycle, never public result data |
| `Session` | Session ID, user ID, creation/last-seen times, idle and absolute expiry, revocation, credential-version snapshot | `SessionRepository`; creates, reads and revokes independently addressed sessions. User sessions are not an ever-growing collection loaded inside `User` |
| `ProjectMembership` | User/project identity and role; uniqueness of the user/project pair and valid role changes | `ProjectMembershipRepository`; membership is independently addressable. Project is an external reference, not an Identity aggregate |
| `ApiToken` (existing support; new administration deferred) | Token ID, owner/project references, scopes, finite expiry and revocation | Existing token persistence is assessed for an aggregate repository; raw token generation/hashing remains technical infrastructure |

`UserName`, `ProjectRole`, token scopes, credential version and expiry are value objects where they enforce actual rules. Password verification and random generation use technical ports; they are not domain services merely because login calls them. Login and logout are application use cases, not aggregates. Password setup is initially an expiring one-time credential associated with a user; introduce its own aggregate only if its lifecycle and consistency rules require one.

Current evidence: `domain/aggregates/identity_account.py` wraps `InternalUser` and supplies active-account and credential-version checks. `domain/entities/browser_session.py` and `domain/browser_identity.py` both define `BrowserSession` with different shapes. The latter also mixes account snapshots, principals and login results. The implementation plan must resolve this ambiguity: keep one domain `Session`, name read projections explicitly (for example `SessionDetails`), and place application results/principal projections outside domain entities. Consolidate `IdentityAccount` and `InternalUser` into the proposed `User` root if tracing confirms that the wrapper has no separate identity or consistency boundary.

Repositories express aggregate persistence and required atomic operations; SQLAlchemy implementations receive the host-owned session. Several focused repository ports may share one concrete adapter when coherent, but do not force all Identity aggregates into one repository or create a repository for every table. Keep ORM models, SQL sessions and transaction completion outside domain/application.

### Consistency and interaction rules

- Login checks the user and credentials, then creates a session only while the account is still active and its credential version matches. Preserve the existing short transactions around expensive password hashing.
- Password changes and deactivation invalidate access through credential-version/status checks; define whether stored sessions are also explicitly revoked. Concurrent login must not bypass invalidation.
- Membership changes become visible to subsequent authorization checks; do not trust stale role data embedded in a session. Prevent concurrent removal/demotion of the last required project administrator with an explicit atomic check.
- Cross-aggregate changes use the existing host-owned unit of work when atomicity is required. OPA does not perform database mutations. Cross-context project references use explicit contracts; Identity repositories must not expose platform ORM objects.

### Intended folders

```text
identity/
  domain/
    aggregates/          user.py, session.py, project_membership.py
    value_objects/       validated names, roles, versions and expiry
    interfaces/          aggregate repository contracts
    services/            only rules genuinely spanning domain objects
  application/
    login/               command.py, handler.py, result.py as needed
    logout/              command.py, handler.py
    change_password/     command.py, handler.py
    <other_action>/      its command/query and handler
    authorization/       typed decision port and input/output contracts
  infra/
    persistence/         ORM mappings and repository implementations
    security/            hashing and secret generation implementations
    authorization/       OPA HTTP adapter and decision mapping
    composition/         Dishka bindings and module dispatcher
```

The authorization contract is owned by Identity application as the public security capability; API/host callers enforce its decisions. OPA policies and container configuration belong to delivery configuration, with their location agreed before implementation. The folder sketch defines ownership, not a requirement to create empty files or rename all files immediately.

- Identity owns accounts, credentials, sessions, API tokens, and membership. Developer Platform owns projects and resources. The API/host authenticates, obtains trusted project/resource attributes, asks the authorization port, then dispatches to the relevant context module.
- OPA runs as a Docker service beside the application. The typed `AuthorizationDecisionPort` accepts principal ID/status, project membership/role, token scopes, action, resource kind/ID/project ID and returns allow/deny with policy revision/decision ID. No raw passwords or tokens are sent.
- OPA policy is versioned with the application configuration. Timeouts, malformed responses, and unavailable OPA deny protected actions; health/readiness distinguishes policy unavailability from invalid credentials. The API enforces decisions; Identity and Platform domains still enforce their own invariants.
- For implementation, assign one owner to the decision contract and policy vocabulary before separate Identity application, persistence, API, and Compose edits. Update route/module dispatch registrations and tests with every rename.

## Acceptance criteria

- [x] Inventory every existing Identity route and handler, with actual behavior and missing operations clearly marked.
- [x] Confirm and document User, Session and ProjectMembership aggregate consistency boundaries; remove duplicate domain/projection names and migrate affected callers together.
- [ ] Verify concurrent login versus password change/deactivation, membership freshness, and last-administrator protection using the agreed consistency contract.
- [x] Each supported action has one clearly named command/query and handler, with callers migrated together.
- [x] Login creates an expiring session using internal collaborators; no duplicate public token-issuance action is introduced for that flow. New automation-token administration is deferred until explicitly required.
- [x] Domain rules remain pure; application handlers use ports; persistence, hashing, OPA HTTP, and DI remain infrastructure concerns.
- [x] Every API token has finite expiry; expired and revoked tokens fail authentication; issuance and sensitive access are auditable.
- [x] A developer can authenticate and perform an allowed project action; another project or insufficient role/scope is denied before dispatch. Evidence is HTTP fakes and actual OPA policy evaluation, not integrated database acceptance.
- [x] OPA outage, timeout, malformed decision, and missing resource facts deny protected actions without leaking secrets.
- [ ] Existing login, logout, password, session, token, and membership flows remain functional after renaming.

## Plan and progress

1. Trace routes, module registry, handlers, domain objects, repositories and tests. Build an implemented/partial/missing matrix; verify whether token expiry and membership operations already exist. **Pending.**
2. Freeze naming, role/action/resource matrix, OPA input/output schema, policy ownership, timeout and audit contract. Resolve open decisions above. **Pending.**
3. Implement bounded Identity use case renames and missing services, migrating module/API callers together. **Implemented under the subsequent authorization; see reconciliation below.**
4. Implement authorization port, OPA adapter/policies, Compose wiring, and API enforcement; add focused denial and expiry checks. **Implemented; see verification below.**
5. Review actual diff, verify login/token/permission paths, update architecture and operations documentation. **Independent review and local checks complete; PostgreSQL/Docker acceptance pending.**

## Implementation reconciliation — 2026-11-12

The later implementation request supersedes the original planning-only authorization labels above. The service catalog describes capabilities; it does not authorize exposing internal maintenance operations through new global-admin HTTP endpoints.

### Delivered structure and contracts

- Broad `browser_login`, `browser_sessions`, `internal_users` and `project_memberships` application modules were split into action folders with colocated messages and handlers. `login` and `change_password` are distinct actions. Internal login validation and session/CSRF safeguards remain collaborators rather than new public endpoints. Existing route URLs and bodies are preserved.
- `User` replaces the `IdentityAccount` wrapper and `InternalUser`. `Session` and `ProjectMembership` are aggregate roots. Session validation includes current account status, expiry, revocation and credential-version matching. Session listing reads aggregate state and maps it to application `SessionDetails`; login returns application `LoginResult`. Pure persistence/authentication snapshots are named in `domain/records.py`; domain code imports no application, infrastructure, SQLAlchemy, FastAPI or Dishka modules.
- Domain repository ports are `UserRepository`, `SessionRepository`, `ProjectMembershipRepository`, plus the existing password-setup/atomic membership-session capabilities. One concrete `SQLAlchemyIdentityRepository` implements these capabilities using only the supplied SQLAlchemy session. No table or schema migration was added. Transaction ownership and lock order are preserved.
- `application/authorization/{models,port}.py` owns the typed decision contract. `infra/authorization/opa.py` implements async OPA HTTP evaluation. The DI-managed HTTP client closes on shutdown and ignores ambient proxy settings. Missing/malformed decisions and transport failures block access; API denial is 403 and policy unavailability is 503.
- All ten protected Identity browser routes use a default-deny API dependency before business dispatch. Login is explicitly exempt. Trusted session authentication reloads requested-project membership; project selection includes its target project in policy input. Membership actions require an administrator of that exact project. Own-session actions retain repository ownership checks, Origin and CSRF checks. No credentials are sent to OPA.
- Policies are versioned in `infra/opa/identity.rego`; Compose runs pinned OPA `1.0.1` on the private control network without publishing a port. The policy mount is read-only. A valid `opa eval` health check validates the policy; `/health/authorization` separately checks the running OPA HTTP decision and revision. Compose API health checks database/schema and authorization readiness.
- Existing timings retained: session idle 30 minutes, absolute eight hours, password setup one hour, API token one–720 hours. Existing known-user throttle is six failures per fifteen-minute window with a fifteen-minute lock. Existing project administration locking and last-active-administrator checks remain. New automation-token administration is deferred; login never calls that issuance workflow.
- Decision metadata is logged without secrets. Durable authorization-decision retention is a recorded limitation, not implemented audit storage. Platform authorization has not been migrated to OPA.

### Progress against original steps

1. Completed code trace: Identity browser routes → context module → host adapters → action handlers/domain rules → SQLAlchemy adapter. Existing internal user/password setup and automation-token actions were retained, not duplicated as new APIs.
2. Contracts settled using existing roles (`developer`, `admin`), exact requested-project matching, default denial, a bounded OPA timeout, private Compose networking and unchanged expiry defaults.
3. Implemented action/domain naming and migrated callers, including necessary import-only Platform API and test updates. Preserved existing staged platform changes.
4. Implemented Identity OPA enforcement, adapter, policies, readiness, Compose wiring, HTTP and policy checks.
5. Independent review performed and confirmed findings addressed. PostgreSQL-backed concurrency and actual Compose startup remain unverified because no Docker daemon/disposable database is available.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| Working tree and file inventory | Inspected | Static evidence only; no behavioral claim |
| `backend/.venv/bin/pytest -q -m 'not postgres'` from backend (executable `.venv/bin/pytest`) | 254 passed, 48 deselected, 40 subtests passed | Real Python/HTTP contracts with fake persistence and OPA transport; not database concurrency acceptance |
| `.venv/bin/ruff check src tests migrations` | Passed | Backend lint |
| `.venv/bin/ruff format --check src tests migrations` | 356 files already formatted | Backend formatting |
| `.venv/bin/mypy src` | Success, 308 source files | Backend strict typing |
| `/private/tmp/devops-hub-opa check --strict infra/opa` and `test infra/opa` | Passed; 10/10 policies | Actual OPA 1.0.1 binary; policy compilation/evaluation, not deployed service acceptance |
| `docker compose --profile app config --quiet` | Passed | Configuration parsing; no containers started |
| `git diff --check` | Passed | Unstaged whitespace check |
| `docker version --format '{{.Server.Version}}'` | Failed: Docker socket absent | No daemon available; no live resources created |
| PostgreSQL integration tests | Not run | No explicitly supplied disposable database URL; expiry/race/restart checks remain an acceptance gate |

Initial OPA tests used an unavailable pytest async plugin and failed; corrected to the repository's `asyncio.run` pattern. New HTTP tests exposed raw string route IDs reaching authentication; parsing to UUID was fixed. OpenAPI comparison showed only the added `/health/authorization` path; the snapshot was updated for that addition. Later full checks passed. The OPA binary was downloaded to temporary storage with approved network access; no package dependency or project secret changed.

Review status: independent read-only review by `/root/identity_review`. Initial findings were invalid OPA health command, faulty Rego assertion, and absent HTTP enforcement tests. These were fixed. Follow-up identified missing target-project attributes for project selection; these were added with fresh requested-project authentication. Final commands/results are recorded below.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/identity_refactor` | coder; runtime coder role and repository guidance | Bounded login/password split | Moved files and imports, returned incomplete collection error; coordinator completed migration and integration |
| `/root/identity_opa` | coder | Initial OPA assignment | Returned without edits; no implementation credited |
| `/root/opa_adapter` | coder; runtime coder role | OPA contracts, adapter, DI, policy and Compose | Implemented assigned files; initial uv check failed on cache permission; coordinator fixed test harness issues and integrated HTTP enforcement |
| `/root/identity_review` | reviewer; read-only | Identity/API/OPA unstaged changes atop `181c8a7`, preserving staged baseline | Reviewed actual files; findings and follow-up recorded above; did not run Docker |

## Handoff

- Completed: Identity service naming, aggregate/result boundaries, OPA port/adapter/policies, Identity HTTP enforcement, Compose wiring and documentation in `docs/identity-services.md`.
- Remaining: PostgreSQL concurrency and actual Docker startup acceptance; durable policy-decision retention and new global-admin endpoints are future scope. Existing internal administrative operations remain internal.
- Next concrete action: Use an explicitly disposable PostgreSQL test URL to run existing Identity integration checks, then verify Compose readiness without exposing OPA publicly. Do not mark integrated readiness complete from unit tests alone.

## Follow-up folder and redundancy cleanup — 2026-11-12

User explicitly authorized continuing the cleanup. Current baseline is `main` at
`a726b77`; existing user changes were preserved and nothing was staged or committed.

- Removed obsolete application packages `browser_login`, `browser_sessions`,
  `browser_principal`, `internal_users`, `project_memberships`, `refresh_session`
  and `set_project_membership`, including caches belonging only to those obsolete
  packages. Added the missing `login/__init__.py`.
- Consolidated session authentication/activity refresh into `authenticate_session`
  with one query and application handler. No redundant refresh command remains.
- Grouped trusted actor and session-based membership commands/handlers under
  `manage_project_membership`. Both entry paths remain because internal hosts and
  developer requests have different credential and transaction requirements.
- Moved technical implementations to `infra/security`, transaction hosts and
  module-to-host adapters to `infra/hosts`. `infra/composition` now contains only
  provider registration and dispatch composition.
- Moved token repository and project access contracts to `domain/interfaces` and
  updated imports in backend callers, tests and the packaged acceptance script.
  Removed the unused `ApiToken` entity and its empty entity package; token state
  snapshots and existing token functionality remain.
- Retained adapters that own short transactions, credential fencing, locking,
  session revalidation and last-administrator safeguards. Their existence is not
  redundant with application handlers; no generic reflection/dispatch framework
  was introduced.

Actual agents: `/root/identity_cleanup` (coder) implemented the bounded moves,
consolidation and import migrations; its focused run passed 45 tests. Coordinator
added the missing package marker, updated docs and fixed the stale relative import
in the synthetic boundary test. `/root/identity_review` independently reviewed the
cleanup and found no concrete regressions; it confirmed both membership entry paths
are used. Reviewer did not run tests.

Coordinator commands/results from `backend/`:

- `.venv/bin/pytest -q -m 'not postgres'`: 253 passed, one failure in a synthetic
  import fixture still spelling `.infra.tokens`; 48 PostgreSQL tests deselected.
- After correcting that fixture, `.venv/bin/pytest -q tests/unit/test_boundaries.py
  tests/unit/test_identity_cqrs.py tests/unit/test_identity_application.py
  tests/unit/test_identity_module_dispatch.py tests/unit/test_browser_identity.py`:
  **48 passed**.
- `.venv/bin/ruff check src tests migrations`: passed.
- `.venv/bin/ruff format --check src tests migrations`: 351 files already formatted.
- `.venv/bin/mypy src`: success, 303 source files.
- Removed-package path inspection confirmed all seven obsolete folders are absent.
- No obsolete runtime import paths remained in backend source/tests or scripts.

Remaining acceptance limits are unchanged: no live Docker startup, PostgreSQL
concurrency test or resource provisioning was performed.

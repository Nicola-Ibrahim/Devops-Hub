# Domain language and application contracts

## Current state

- **Updated:** 2026-11-05.
- **Authorized phase and scope:** Planning only. Investigate and design the domain language and its communication with application services for `identity` and `developer_platform`. Only this task record may be changed.
- **Next step:** Authorize the contract-first implementation phase, beginning with domain value objects and aggregate behavior before changing repositories or application callers.
- **Open decisions:** None required to begin. Use `value_objects/` rather than the abbreviation `vos/`; create only meaningful aggregates and services rather than empty symmetric packages.
- **Baseline:** Clean `main` at `08c316891c28d880c5578cf5d5534b22ce53363a`, matching `origin/main` when inspected. The prior application-service refactor is part of this baseline.
- **Latest verification:** Read-only inspection with `git status`, `git rev-parse`, `rg`, `sed`, and `wc`. No tests, application startup, database access, providers, migrations, or live resources were run.

## Goal and evidence

The goal is a domain model whose names and behavior describe the internal company identity system and the developer platform. Application services should orchestrate a business request through domain value creation, aggregate behavior, repository interfaces, and persistence. SQLAlchemy rows remain infrastructure mappings and are not domain entities.

The normal write flow will be:

```text
API command
  -> application service
  -> construct validated value objects
  -> load or create aggregate through a domain repository interface
  -> invoke aggregate/domain policy
  -> persist aggregate and durable intent atomically
  -> host commits
  -> external worker effect, when required
  -> persist fenced completion or retry state
```

Login is a deliberate variant:

```text
normalize UserName
  -> load login account snapshot in a short transaction
  -> verify password through the application PasswordHasher port outside SQL
  -> domain authentication policy decides acceptance
  -> version-fenced session creation in a new short transaction
  -> application maps the domain result to login/session tokens
```

### Source-backed facts

- `identity/domain/browser_identity.py` combines six kinds of data and a broad `BrowserIdentityRepository`: user account state, memberships, principals, login results, sessions, project-member read models, session mutation, password mutation, membership administration, and password setup.
- Identity application actions already call some domain rules. `application/browser_login.py` uses user-name and password rules; `application/issue_token.py` uses active-membership policy; `application/browser_sessions.py` depends on the domain repository and authentication errors.
- `identity/domain/credentials.py` constructs `identity.contracts.AuthenticatedPrincipal`. This reverses the desired direction: the domain should return an identity authentication result and the application/host should map it to an outward contract.
- Browser login in `identity/infra/browser_operations.py` intentionally reads the account, verifies an expensive hash outside SQL, then calls `complete_login` with `expected_version`. Project selection uses another transaction and compensating logout on failure. This concurrency and timing behavior must remain.
- Identity membership locks, throttle/session validity, credential fencing, and some authorization decisions still live in `identity/infra/persistence/browser_identity.py`. Pure decisions can move inward; locks and atomic writes remain in persistence.
- `developer_platform/domain/ledger.py` combines commands, read projections, catalog records, and a repository. `domain/application_delivery.py` similarly combines commands, projections, worker claims/results, and a large repository interface. These are record catalogs rather than clear aggregates.
- Useful platform domain logic already exists in `domain/leases.py` and `domain/resources.py`: lease rules, resource ownership, desired/observed state vocabulary, and transition rules.
- Critical lifecycle decisions remain embedded in SQL adapters. `infra/persistence/ledger.py` handles configured-project/environment checks, idempotency, quota locks/reservations, and resource/operation creation. `infra/persistence/lifecycle.py` handles revision fencing, renew/delete mutation, readiness, and connection access. `infra/persistence/worker_queue.py` mutates resource and operation states.
- Quota admission, idempotency, revision checks, and worker fencing require database locks and constraints. The domain may decide using loaded state, but repositories must retain atomic lock/load/save operations and translate conflicts safely.
- The worker correctly separates durable claim, external Docker/GitHub/provider effects, and completion/failure persistence. A database rollback cannot undo an external effect; this boundary must remain unchanged.

### Proposed domain structure

Use the requested DDD categories as lowercase Python packages. A package is created only when it contains an actual business concept; do not create placeholder base classes, generic repositories, or empty service folders.

```text
identity/domain/
  entities/
    internal_user.py
    browser_session.py
    api_token.py
    project_membership.py
  value_objects/
    user_name.py
    password_policy.py
    project_role.py
    token_scopes.py
    credential_version.py
    session_expiry.py
  aggregates/
    identity_account.py
  interfaces/
    account_repository.py
    session_repository.py
    membership_repository.py
    api_token_repository.py
  services/
    authentication_policy.py
    membership_policy.py
```

`IdentityAccount` is the initial aggregate root for user active state, credential version, and membership decisions. Browser sessions and API tokens are entities with their own lifecycle, but repository splits must preserve operations that are currently atomic. `AuthenticatedIdentity` and `LoginDecision` are domain results. Password hashing, token generation, secret digesting, clocks, and credential delivery remain application interfaces with infra implementations.

```text
developer_platform/domain/
  entities/
    project.py
    environment.py
    resource.py
    operation.py
    application.py
    delivery_step.py
    deployment.py
  value_objects/
    resource_name.py
    resource_spec.py
    lease.py
    idempotency_key.py
    resource_revision.py
    image_digest.py
    repository_slug.py
    resource_endpoint.py
    statuses.py
  aggregates/
    resource_lifecycle.py
    application_delivery.py
  interfaces/
    project_repository.py
    resource_repository.py
    application_repository.py
  services/
    resource_admission.py
    resource_access_policy.py
    delivery_policy.py
```

`ResourceLifecycle` owns resource identity, owner/project/environment, specification, lease, desired/observed state, revision/generation, and allowed transitions. It exposes business actions such as `request`, `renew`, `request_deletion`, `record_ready`, `record_failure`, and `allow_connection`. `ApplicationDelivery` owns application state and delivery-step rules. Quota/capacity admission can become a domain service only when represented by an explicit capacity snapshot; row locking remains a repository responsibility.

Commands and query results remain in the application layer beside their use cases. Provider interfaces for Docker, GitHub, templates, hashing, encryption, credential delivery, clocks, and worker queues remain application ports because they describe orchestration or technical effects. Domain `interfaces/` contains only repositories required to load and persist domain state.

## Scope and invariants

- **In scope:** Domain package organization; rich ORM-free entities, value objects and aggregates; domain repository interfaces; domain policies; application command/result placement; application-to-domain mapping; SQLAlchemy mapping boundaries; compatibility migration of callers for both bounded contexts.
- **Out of scope:** New API features, UI changes, schema redesign, social login, new providers, provisioning, deployment, migrations, or removal of compatibility exports before all callers move.
- **Required behavior to preserve:** Existing route and response contracts; internal-only authentication; dummy-hash timing behavior; credential-version fencing; CSRF/origin checks; login throttling; account/session/token revocation; membership locks; project/resource authorization; idempotency and concurrent quotas; resource revision/generation fencing; lease rules; encrypted credentials and audit; worker claim/heartbeat/retry/reconciliation semantics.
- **Resource and secret safeguards:** Passwords, raw tokens, database credentials, ciphertext/plaintext conversions, and connection strings must remain excluded from logs and ordinary representations. No live resources or secrets are accessed during this planning phase.
- **Transaction safeguard:** Application services do not receive a unit of work or SQLAlchemy session. Host composition owns transaction lifetime. SQL repositories perform lock/load/save atomically. External effects remain outside database transactions and complete through durable fenced records.

## Acceptance criteria

- [ ] Both bounded contexts expose meaningful `entities/`, `value_objects/`, `aggregates/`, `interfaces/`, and `services/` packages, without placeholder abstractions; package contents use real business names.
- [ ] Domain entities and aggregates are ORM-free and enforce their own state invariants. SQLAlchemy models remain under context `infra/persistence/` and map explicitly to/from domain objects.
- [ ] Identity application services depend on domain types and repository interfaces. Login preserves timing-safe verification outside SQL and version-fenced session completion; domain code no longer constructs API/host principal contracts.
- [ ] Platform request services validate application commands into domain value objects, create/load `ResourceLifecycle` or `ApplicationDelivery`, invoke domain behavior, and persist through focused repositories.
- [ ] Application commands, query DTOs, provider results, and worker-effect ports are not mislabeled as domain entities or repository interfaces.
- [ ] Broad repositories are replaced by focused aggregate/capability interfaces while operations requiring a shared atomic transaction still use the same request-scoped SQL session.
- [ ] Idempotency, quota admission, revision fencing, and worker completion remain concurrency-safe and backed by database constraints/locks; domain extraction does not weaken restart recovery.
- [ ] Import-boundary checks, domain characterization tests, application tests, focused PostgreSQL concurrency tests, and worker restart/retry checks pass during an authorized implementation phase. No runtime acceptance is claimed by this plan.

## Contracts and ownership

### Dependency direction

```text
api/host -> application -> domain
                   |          ^
                   v          |
          application ports   |
                   ^          |
                   |          |
             infra adapters --+
```

- Domain imports only Python standard-library types and its own context.
- Application imports its own domain and application ports; it does not import SQLAlchemy, Dishka, FastAPI, context containers, or concrete infra.
- Infrastructure implements domain repositories and application ports and performs ORM mapping.
- API/worker hosts map transport identity and commands, own transaction completion, and coordinate cross-context actions.
- `identity` and `developer_platform` remain independent; cross-context project/actor mapping stays at root composition.

### Value-object contract

- Value objects validate and normalize at construction and are immutable.
- Add wrappers only when they enforce a real invariant: `UserName`, `ProjectRole`, `TokenScopes`, `Lease`, `ResourceSpec`, `IdempotencyKey`, `ImageDigest`, and `RepositorySlug` qualify. Plain UUIDs do not require wrappers unless type confusion is demonstrated.
- Raw passwords and secrets are short-lived application inputs. Password hashes/digests may be private value objects with redacted representations, but hashing is an application port implemented in infra.

### Aggregate and repository contract

- A repository loads/saves one aggregate boundary or a named domain capability. It does not accept Pydantic models, application commands, HTTP identities, units of work, or sessions.
- Repositories may expose atomic methods where absent-row locking, quota reservations, idempotency, or fencing cannot safely be expressed as separate load/save calls. The method name must state the business operation and map to domain input/results.
- Query paths may use dedicated application read ports/projections rather than reconstructing an aggregate for read-only lists.
- SQLAlchemy adapters may implement several focused interfaces against the same request-scoped session to preserve a single commit/rollback boundary.

### Proposed file ownership for implementation

- **Coordinator:** shared contracts, migration order, root composition/API compatibility, boundary rules, task record, and integration.
- **Identity coder:** `backend/src/identity/domain/**`, `identity/application/**`, `identity/infra/**`, and identity-focused tests after shared contract decisions are fixed.
- **Platform coder:** `backend/src/developer_platform/domain/**`, `developer_platform/application/**`, `developer_platform/infra/**`, and platform-focused tests after identity-independent platform contracts are fixed.
- **Reviewer:** read-only review of the integrated diff, focusing on domain purity, behavior parity, transaction boundaries, concurrency, secrets, and recovery.
- Coders share the workspace, preserve unrelated changes, and must not edit root composition or another context without coordinator ownership.

## Plan and progress

1. **Characterize current behavior.** Before moving types, map existing domain/application/infra responsibilities and add or identify characterization coverage for login/session/token/membership, resource request/renew/delete/connection, delivery steps, worker retries, and error mapping. Record facts separately from desired design.
2. **Create domain vocabulary without changing persistence.** Introduce the real value objects and domain result types listed above. Move validation and normalization from application regexes and persistence into those objects. Keep compatibility imports temporarily so API and tests remain stable.
3. **Build the identity model.** Introduce identity entities and `IdentityAccount`; move active-state, credential-version, role/scope, session-expiry, and membership decisions into domain behavior. Split repository interfaces by account, session, membership, and API-token capability. Keep password hashing/generation as application ports. Preserve the current multi-transaction login flow and version fence.
4. **Update identity application services.** Convert commands into value objects, load domain state, invoke policies/aggregate methods, and persist through the focused interfaces. Map `AuthenticatedIdentity` to `AuthenticatedPrincipal` outside the domain. Adapt existing SQL repositories to map ORM rows and implement the new interfaces.
5. **Build the platform resource model.** Introduce `ResourceLifecycle`, resource/operation entities, lease/spec/revision/name/idempotency value objects, access/admission policies, and `ResourceRepository`. Move pure acceptance, renewal, deletion, connection eligibility, and transition decisions inward while repositories retain locks, unique constraints, quota reservation, encrypted-secret storage, and atomic operation creation.
6. **Update platform resource application services.** `RequestTestDatabase` becomes a clearly named request-database orchestrator that constructs domain input, checks replay/catalog/installation, creates the aggregate and persists durable intent. Renew/delete/connection actions load locked state, invoke aggregate behavior, and save/map results. Read queries use projections rather than aggregates where no behavior is required.
7. **Build the application-delivery model.** Introduce `ApplicationDelivery` aggregate plus application, delivery-step, and deployment entities; move image, repository, idempotency, retry and closed-application rules into value objects/policies. Keep GitHub/Docker/template/provider ports in application. Preserve claim -> external effect -> fenced completion and reconciliation.
8. **Retire broad compatibility modules.** After all callers migrate, remove record-catalog compatibility exports and broad repository protocols. Update DI bindings, boundary rules, backend architecture documentation, and imports. Do not remove compatibility paths earlier than their last caller.
9. **Verify in layers.** Run domain and application checks first, then static import/type checks, API contract tests, disposable PostgreSQL locking/idempotency/quota/revision tests, and finally isolated worker restart/retry/Docker acceptance where authorized. Obtain independent read-only review and address confirmed findings before calling the migration complete.

### Ordered dependencies

- Value objects and domain results precede aggregates.
- Aggregates precede repository signatures.
- Repository signatures precede SQL adapter and DI changes.
- Identity and platform implementations can proceed independently only after their context contracts are fixed.
- Platform resource lifecycle precedes application delivery attachment because delivery requests platform resources.
- Provider-effect execution remains last and does not enter the aggregate transaction.

### Decisions resolved in this plan

- Use rich domain objects separate from ORM rows.
- Use `value_objects/` for clarity; avoid `vos/`.
- Keep the five requested categories, but create concrete packages/files only for real concepts.
- Treat application commands and read projections as application types, not domain entities.
- Keep technical/external interfaces in application ports and repository interfaces in domain `interfaces/`.
- Start with one identity aggregate and two platform aggregates; add more only when an invariant boundary justifies them.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| `git status --short --branch` | Clean `main...origin/main` | Baseline only |
| `git rev-parse HEAD` | `08c316891c28d880c5578cf5d5534b22ce53363a` | Baseline only |
| `rg`, `sed`, `wc` over both contexts | Current types, rules, imports, repository surfaces, persistence mappings, and representative flows traced | Static source evidence only |
| Tests/runtime/provider acceptance | Not run | Planning-only phase; no pass claimed |

Review status: coordinator architecture self-review plus separate read-only investigator evidence; no implementation diff exists for review.

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| `/root/domain_language_trace` | Investigator; explicit user request, `AGENTS.md`, workflow guide, and architecture-review procedure | Read-only trace of domain/application communication in identity and developer platform at clean `main@08c3168` | Confirmed broad mixed repository/record modules, outer-contract leakage from identity domain, SQL-held lifecycle decisions, and required login/worker transaction safeguards. Recommended meaningful entities/value objects/aggregates/interfaces/services without empty symmetry. No edits, tests, DB or provider calls. |

## Handoff

- **Completed:** Current-state trace, recommended domain vocabulary and structure, dependency contracts, safeguards, acceptance criteria, ownership, and ordered migration plan.
- **Remaining:** Implementation authorization, characterization evidence, contract-first domain migration, adapter/caller integration, runtime verification, and independent diff review.
- **Next concrete action:** In an authorized implementation phase, create and verify the identity and resource-lifecycle value objects/domain results first, preserving existing import compatibility and runtime behavior.

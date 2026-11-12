# Identity services

Identity owns internal accounts, credentials, sessions, API tokens and project
membership. Developer Platform owns projects and requested resources; Identity
references project IDs. OPA evaluates Identity permissions and the HTTP boundary
enforces its answer before application dispatch.

## Application actions

| Capability | Action folders | Entry point |
| --- | --- | --- |
| Sign in and out | `login`, `logout`, `logout_all_sessions` | Existing `/api/v1/auth` routes through `IdentityModule` |
| Sessions | `authenticate_session`, `rotate_csrf`, `list_sessions`, `revoke_session`, `select_active_project` | Existing browser/session routes; authentication also refreshes session activity |
| Password changes | `change_password` | `/api/v1/me/password` |
| Membership | `list_project_members`, `manage_project_membership` | Existing project-member routes; trusted actor and session-based membership changes share one action folder |
| User administration | `create_user`, `set_user_status`, `bootstrap_first_admin`, `start_password_setup`, `complete_password_setup` | Existing internal host operations; no new global user-admin HTTP API |
| Automation tokens | `issue_api_token`, `revoke_api_token`, `authenticate_api_token` | Existing internal issuance/revocation and bearer authentication; additional token administration remains deferred |

Each action keeps its message and handler together. Internal credential checks and
CSRF checks are collaborators, not independently exposed user actions. Login creates
a session secret; it does not issue a project-scoped automation token.

## Domain and persistence

- `User` is the account aggregate: validated name, active status and credential version.
- `Session` owns expiry, revocation and the credential-version snapshot. It checks
  current account status and credential version before accepting access.
- `ProjectMembership` identifies one user/project relationship and validates roles.
- `LoginResult` and `SessionDetails` are application results. Persistence snapshots
  and authenticated session facts have explicit names in `domain/records.py`.
- `UserRepository`, `SessionRepository` and `ProjectMembershipRepository` describe
  required domain persistence capabilities. `SQLAlchemyIdentityRepository` implements
  them using one host-owned SQLAlchemy session. Hosts retain the existing transaction
  and lock order; the adapter and handlers do not commit.

Infrastructure is grouped under `persistence`, `security`, `authorization`, `hosts`
and `composition`. Transaction hosts and module-to-host adapters live in `hosts`;
composition contains DI providers and dispatch registration. Repository contracts
live in `domain/interfaces`, including API-token and project-access contracts.

Sessions retain a 30-minute idle limit and an eight-hour absolute limit. Password
setup lasts one hour. Existing automation tokens expire after 1–720 hours. Existing
username throttling locks known accounts after six failures within fifteen minutes
for fifteen minutes. No new schema migration is required by these changes.

## OPA contract and operation

`application/authorization` defines typed requests, decisions and the decision port.
`infra/authorization/opa.py` implements the port using an async HTTP client with a
bounded timeout. Dishka owns the client's lifetime. The API sends authenticated user
and project facts, action and resource attributes; passwords, session secrets and
raw API tokens never enter the policy input.

The policy in `infra/opa/identity.rego` permits session actions for the authenticated
owner and membership administration for an administrator of the requested project.
Unknown actions and missing facts deny access. Transactional membership and account
checks remain in place to handle races after the external policy decision.

OPA deny returns HTTP 403. Transport failures and invalid/missing OPA decisions
return HTTP 503 and block dispatch. Login remains available during an OPA outage.
`/health/live` checks the process, `/health/ready` checks the database/schema, and
`/health/authorization` verifies the OPA decision document and expected policy
revision. Decision metadata is logged without credentials; durable policy-decision
retention is not implemented.

Compose starts OPA beside the API, mounts policies read-only and publishes no OPA
host port. `PLATFORM_OPA_URL` is `http://opa:8181` in Compose and defaults to
`http://127.0.0.1:8181` for local processes. For a backend running directly on the
host, run a compatible OPA binary with:

```bash
opa run --server --addr=127.0.0.1:8181 infra/opa
opa test infra/opa
opa check --strict infra/opa
```

Use the repository's existing private configuration and setup instructions for
Compose. Platform resource permissions retain their existing implementation;
this Identity change does not migrate those policies to OPA.

Code and policy tests establish contracts. PostgreSQL concurrency and Docker
acceptance require a disposable configured environment before claiming integrated
readiness.

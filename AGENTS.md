# DevOps Hub agent guidance

## Product goal

Build a self-service developer platform for provisioning approved development resources on configured targets. A developer should be able to request a temporary, isolated database on a local runtime or configured server, see its status, securely obtain a usable database connection string, and have access revoked and resources removed when its lease expires or the related work closes. Extend the catalog through provider adapters as additional resource types and targets are implemented. Keep the developer experience simple and the resource lifecycle observable.

The [platform requirements](docs/platform-requirements.md) define the intended capabilities and delivery boundaries. They describe requirements, not implemented features or preassigned tasks.

## Agreed technology and execution environment

- Backend: Python with FastAPI, SQLAlchemy and Alembic over PostgreSQL. Read [backend/AGENTS.md](backend/AGENTS.md) for DDD, worker and API boundaries. Documentation describes intent, not proof of working behavior.
- Frontend: Next.js developer dashboard for requesting resources, viewing status and expiry, and managing authorized lifecycle actions. Read [frontend/AGENTS.md](frontend/AGENTS.md) for frontend boundaries.
- Initial runtime: local Docker. The core demo must run without AWS or Azure credentials and demonstrate real container provisioning, readiness and cleanup.
- Keep provider-specific infrastructure behind explicit interfaces for local Docker, configured server runtimes, and future Kubernetes or cloud providers. Resource types and targets must be registered and supported; arbitrary destinations and arbitrary infrastructure commands are not developer inputs. Add providers only within requested scope.
- CI checks must create their own isolated test resources; do not assume a hosted runner can reach a developer's laptop.

## Repository today

- `.github/workflows/` contains reusable CI and Docker image publishing workflows.
- `infra/ansible/` contains local bootstrap and server setup/deployment playbooks.
- `scripts/dev/platform_dev/` contains the Python local development CLI.
- `backend/` contains the API foundation, pure lifecycle rules, control-plane schema/migrations, internal token administration services and focused tests. See `backend/README.md` for setup and verification.
- Backend business context and API ownership are described in [backend/AGENTS.md](backend/AGENTS.md). Do not create a top-level Python package named `platform`, which would shadow the standard library.
- `docs/` contains onboarding and operations guides; [infra/AGENTS.md](infra/AGENTS.md) covers hosting configuration.
- `frontend/`, resource/application worker entrypoints, Docker provider adapters, `templates/`, Compose and delivery/operations assets are present in the working tree. Their presence does not establish integrated readiness or completed milestones. Check current wiring, authorization, provider verification and actual acceptance evidence before claiming support. Do not claim queued ledger rows are provisioned databases.

## Delivery responsibilities

Terraform provisions hosting infrastructure; Ansible configures hosts; CI/CD builds
and delivers immutable releases with readiness and rollback; platform API/workers
manage developer-requested resources. The core portfolio demonstration must work
locally without a cloud account. Identity is internal company authentication and
project permissions; do not add Google/social login without a new requirement.
Python/FastAPI is the first application template; other languages follow the same
operational contracts after that foundation works.

## When to use skills

Load only skills matching the task. Skills describe procedures; `.codex/agents/`
defines delegated actors. Small fixes need no task record or automatic agent sequence.

Guidance has one owner: this file holds repository-wide product and safety rules;
the nearest directory `AGENTS.md` holds component structure and invariants; skills
hold repeatable workflows; agent files hold role scope and handoff behavior. Avoid
copying the same rule across those layers.

| Task | Skill |
| --- | --- |
| Cross-component architecture, substantial planning and coordination | [system-design](.agents/skills/system-design/SKILL.md) |
| DDD, persistence, workers, resource lifecycle and backend checks | [backend-development](.agents/skills/backend-development/SKILL.md) |
| FastAPI routes, schemas, permissions and HTTP contracts | [api-development](.agents/skills/api-development/SKILL.md) |
| Next.js dashboard design, integration and checks | [frontend-development](.agents/skills/frontend-development/SKILL.md) |
| Docker, Compose, CI/CD, Ansible, Terraform, deployment and rollback | [delivery-engineering](.agents/skills/delivery-engineering/SKILL.md) |
| Create or revise a skill | Use skill-creator when available |

For cross-cutting work, load the relevant skills together. Use
[backend setup](backend/README.md), frontend package scripts and the
[operations guide](docs/operations.md) for current commands.

## Shared working rules

- Inspect the working tree before edits and preserve unrelated changes. Do not stage, commit, reset, or switch branches unless requested.
- Inspect existing code before changing it. State assumptions where the implementation does not yet exist.
- Keep frontend, backend, and platform responsibilities separate. Agree on API contracts and resource states before implementing cross-cutting flows.
- Keep identity and developer_platform independent; [backend/AGENTS.md](backend/AGENTS.md) defines DDD and FastAPI boundaries.
- Every temporary resource must have an owner, creation time, expiry, status, and cleanup path. Provisioning and deletion must be safe to retry.
- Never commit credentials or return a database password in logs, CI output, or ordinary API list responses.
- Use focused tests for lifecycle and failure behavior. Run relevant checks and report what was verified.
- Update the affected docs when developer commands, API contracts, or operational behavior change.
- Do not claim an image publish is a deployment; identify the actual deploy and rollback path.
- For substantial cross-component work, use `.agents/skills/system-design/SKILL.md` with the affected component skills. Delivery-only work uses `.agents/skills/delivery-engineering/SKILL.md`. Create task records only when the user requests them, using `.codex/workflow/templates/task.md`. Otherwise keep scope and progress in the conversation. Follow `.codex/workflow/README.md`; a planning request does not authorize implementation.

## Agent roles

- `coder`: implements assigned frontend, backend, or platform/CI work within explicit file boundaries.
- `investigator`: read-only tracing of existing behavior, contracts, and gaps before a substantial change.
- `reviewer`: independent read-only review of a scoped diff against acceptance criteria.

For work spanning roles, assign one owner for the contract first, then split implementation into independent files or stages. The coordinating agent integrates and verifies the full flow. Use investigator and reviewer when their separate work adds value; a configured role is not evidence that an agent ran. Record actual checks and review limits.

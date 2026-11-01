# DevOps Hub agent guidance

## Product goal

Build a self-service developer platform for provisioning approved development resources on configured targets. A developer should be able to request a temporary, isolated database on a local runtime or configured server, see its status, securely obtain a usable database connection string, and have access revoked and resources removed when its lease expires or the related work closes. Extend the catalog through provider adapters as additional resource types and targets are implemented. Keep the developer experience simple and the resource lifecycle observable.

The [platform requirements](docs/platform-requirements.md) define the intended capabilities and delivery boundaries. They describe requirements, not implemented features or preassigned tasks.

## Agreed technology and execution environment

- Backend: Python with FastAPI, SQLAlchemy and Alembic over PostgreSQL. The phase-1 foundation is implemented; resource lifecycle endpoints and provisioning workflows are subsequent work in the backend task record.
- Frontend: Next.js developer dashboard for requesting resources, viewing status and expiry, and managing authorized lifecycle actions. The dashboard consumes the backend API; provisioning logic belongs in the Python backend and worker.
- Initial runtime: local Docker. The core demo must run without AWS or Azure credentials and demonstrate real container provisioning, readiness and cleanup.
- Keep provider-specific infrastructure behind explicit interfaces for local Docker, configured server runtimes, and future Kubernetes or cloud providers. Resource types and targets must be registered and supported; arbitrary destinations and arbitrary infrastructure commands are not developer inputs. Add providers only within requested scope.
- CI checks must create their own isolated test resources; do not assume a hosted runner can reach a developer's laptop.

## Repository today

- `.github/workflows/` contains reusable CI and Docker image publishing workflows.
- `infra/ansible/` contains local bootstrap and server setup/deployment playbooks.
- `scripts/dev/platform_dev/` contains the Python local development CLI.
- `backend/` contains the API foundation, pure lifecycle rules, control-plane schema/migrations, local token administration and focused tests. See `backend/README.md` for setup and verification.
- Backend business contexts are `src/identity/` and `src/developer_platform/`, each containing `application/`, `domain/` and `infra/`. `src/api/` owns HTTP, `src/containers/` declares DI providers and outer operation completion, `src/entrypoints/` owns minimal executable hosts, and `src/shared/infra/` contains technical database/UoW/readiness infrastructure (plus the documented legacy audit adapter). Do not create a top-level Python package named `platform`, which would shadow the standard library.
- `docs/` contains onboarding and operations guides.
- There is no frontend, resource lifecycle API or provisioner yet. The backend currently exposes health, identity and an empty catalog; do not claim it provisions resources.

## Shared working rules

- Inspect the working tree before edits and preserve unrelated changes. Do not stage, commit, reset, or switch branches unless requested.
- Inspect existing code before changing it. State assumptions where the implementation does not yet exist.
- Keep frontend, backend, and platform responsibilities separate. Agree on API contracts and resource states before implementing cross-cutting flows.
- Keep identity and developer_platform independent. Application code imports its own domain/ports, never concrete infra or frameworks. Context infra implements those ports; API handlers delegate to applications and never query ORM sessions. Cross-context actor mapping and concrete wiring belong at the host/composition boundary. Shared infra must not contain either context's business rules. Each context owns its tables, ORM mappings and SQL repositories in `infra/persistence/`; pure domain/application code remains ORM-free. Application services receive repositories/interfaces, never units of work. Name classes/functions after specific business concepts/actions.
- Every temporary resource must have an owner, creation time, expiry, status, and cleanup path. Provisioning and deletion must be safe to retry.
- Never commit credentials or return a database password in logs, CI output, or ordinary API list responses.
- Use focused tests for lifecycle and failure behavior. Run relevant checks and report what was verified.
- Update the affected docs when developer commands, API contracts, or operational behavior change.
- Do not claim an image publish is a deployment; identify the actual deploy and rollback path.
- For substantial work, use `.agents/skills/platform-change/SKILL.md`. Create task records only when the user requests them, using `.codex/workflow/templates/task.md`. Otherwise keep scope and progress in the conversation. Follow `.codex/workflow/README.md`; a planning request does not authorize implementation.

## Agent roles

- `coder`: implements assigned frontend, backend, or platform/CI work within explicit file boundaries.
- `investigator`: read-only tracing of existing behavior, contracts, and gaps before a substantial change.
- `reviewer`: independent read-only review of a scoped diff against acceptance criteria.

For work spanning roles, assign one owner for the contract first, then split implementation into independent files or stages. The coordinating agent integrates and verifies the full flow. Use investigator and reviewer when their separate work adds value; a configured role is not evidence that an agent ran. Record actual checks and review limits.

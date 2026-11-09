---
name: backend-development
description: Implement or review DevOps Hub Python domain, application, persistence and worker changes. Use for DDD, CQRS, resource lifecycle, providers or reconciliation; API-only work uses api-development.
---

# Backend development

Follow [backend architecture](../../../backend/AGENTS.md).

1. Trace the use case from its host through application, domain, repository port
   and adapter. Identify its invariant, transaction boundary and failure paths.
2. Put each decision in its owning layer and keep the command/query beside its
   handler. Define typed success data, typed failures and host rollback
   before changing adapters and callers.
3. Wire the use case through its context module and DI, preserving API permission boundaries,
   domain ownership checks, idempotency, recovery and secret rules from
   `backend/AGENTS.md`.
4. Verify the changed invariant and its failure path. Report simulated and real
   provider evidence separately.

From `backend/`, select only affected checks:

```bash
.venv/bin/ruff check src tests migrations
.venv/bin/ruff format --check src tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q -m 'not postgres'
```

PostgreSQL tests require an explicit disposable `PLATFORM_TEST_DATABASE_URL`;
read `tests/conftest.py` before running `-m postgres`. Real Docker acceptance must
use owned disposable resources and private generated credentials. Never use global
prune, a shared developer database or printed connection secrets. A routine small
fix needs no task record.

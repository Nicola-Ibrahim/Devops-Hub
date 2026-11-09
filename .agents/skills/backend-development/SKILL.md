---
name: backend-development
description: Implement or review DevOps Hub Python backend domain, application, SQL persistence and resource workers. Use for DDD, CQRS, leases, providers, reconciliation or backend checks; API-only work uses api-development.
---

# Backend development

Follow [backend guidance](../../../backend/AGENTS.md). For an assigned backend
change:

1. Trace the use case from host through application command/query, domain rule,
   repository port and adapter. Identify callers, persistence, failure paths and
   the invariant the change must preserve.
2. Place the rule where it belongs: commands enforce domain invariants and save;
   queries read authorized projections. Use entities/value objects for real
   business concepts, not obligatory wrappers. Name actions in domain language.
3. Keep identity and developer_platform independent. Application handlers receive
   narrow interfaces, never sessions or units of work. Context infra owns ORM
   mappings, repositories and provider SDKs; domain/application stay framework
   free. The host owns DI, actor mapping and outer SQL commit/rollback. Persist
   external work and execute provider effects outside SQL transactions.
4. Verify the changed invariant and failure path with isolated checks below;
   report actual results and any missing real-provider evidence.

## Resource lifecycle

For requests, leases, credentials, providers or reconciliation, trace the
operation, owned tables, callers, migrations, worker claims and external target.
Read-only investigation must not initialize writers, repair resources or read
secret values. A queued row or successful fake adapter does not prove a database
is reachable.

- Authorize requests, reads, extensions, deletion and credential retrieval by
  project role and ownership. Keep credentials out of ordinary responses/logs.
- Persist intent, idempotency identity and quota reservation atomically; concurrent
  requests must not exceed quotas or duplicate allocations.
- Fence worker claims, generations and completion against duplicate delivery,
  crashes and late results. Keep SQL transactions short around external effects.
- Keep owner, creation time, expiry, status and cleanup for each resource. Expiry
  and deletion revoke access and remove owned storage as contracted.
- Retain recovery information and capacity for uncertain effects. A missing
  observation does not prove in-flight creation has ended.
- Restrict providers to approved types/targets and bounded limits. Use stable
  ownership labels; never adopt or delete foreign resources. Inspection must not
  recreate missing databases or silently discard stored data.
- Preserve encrypted credential/key references, audit history and migration
  compatibility. A schema downgrade is not automatically a safe data rollback.

Distinguish invalid input, provider unavailability, timeout, drift and cleanup
failure with sanitized errors and bounded retries. For authorized backup,
restore, migration or cleanup, establish source, destination and ownership;
preserve recoverable state, verify consistency and key availability without
exposing values, and reconcile restored state with provider observations. Stop
destructive follow-up when ownership or consistency cannot be established. Code
changes alone do not authorize live resource changes.

## Verification

Select focused checks for changed behavior; inspect fixtures and subprocesses
before running them. From `backend/`, with installed locked dependencies:

```bash
.venv/bin/ruff check src tests migrations
.venv/bin/ruff format --check src tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q -m 'not postgres'
```

Narrow paths or selectors as appropriate. `mypy` needs the backend pyproject.
The test marker alone does not prove isolation; inspect unmarked tests. Do not
implicitly install dependencies, rewrite snapshots or substitute SQLite for
PostgreSQL concurrency/migration checks. Planning work proposes checks; skill
edits need validation, not application suites.

PostgreSQL integration tests require explicit `PLATFORM_TEST_DATABASE_URL` for
a disposable local `devops_hub_test*`; read `backend/tests/conftest.py` and verify
the target before running `-m postgres`. Unique schemas do not make a shared
server disposable.

Real Docker acceptance, when in scope, needs a unique test identity, loopback
access, disposable storage, private generated credentials and cleanup of owned
resources via a finally/recovery path. Never prune globally, use a shared
developer database or print a DSN/password. Show request, readiness, restricted
connection, lease extension, deletion, duplicate request and worker restart;
verify storage removal. Check concurrent quotas and interrupted operations when
affected. Fake providers establish control flow only.

Report actual commands/results, environment, simulated versus real evidence and
limits. Recheck only affected behavior; independent review requires a separate
review. A routine small fix needs no task record.

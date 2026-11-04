---
name: platform-verification
description: Select and run focused checks for DevOps Hub backend, dashboard, providers and delivery assets using isolated resources; distinguish static validation from real lifecycle acceptance.
---

# Verify platform changes

Inputs are the changed behavior/diff, authorized execution scope and acceptance
criteria. Specialists supply contracts to check; platform-change owns coordination,
records and handoff. Inspect fixtures, imports and subprocess configuration before
execution. Planning-only work proposes checks; read-only verification runs only
permitted static checks. Prose/skill edits need links, frontmatter and command checks,
not application suites.

## Select checks from the behavior

From `backend/`, with installed locked development dependencies:

```bash
.venv/bin/ruff check src tests migrations
.venv/bin/ruff format --check src tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q -m 'not postgres'
```

Narrow paths/selectors for focused changes. Run mypy from backend so its strict
pyproject configuration applies. Inspect unmarked tests too: a marker exclusion is
not proof of isolation. Do not install dependencies or rewrite snapshots implicitly.

PostgreSQL integration tests require an explicitly supplied
`PLATFORM_TEST_DATABASE_URL` pointing to a disposable local `devops_hub_test*`
database. Read `backend/tests/conftest.py`: it validates libpq overrides and uses
unique schemas, but schema isolation does not make a shared server disposable.
Run selected `-m postgres` tests only with a verified test target. Do not substitute
SQLite for PostgreSQL locking, concurrency or migration acceptance.

From `frontend/`, use `npm run typecheck` and `npm run build` as applicable.
Build success does not prove login, authorization, proxy/CSRF or dashboard workflows.
For delivery assets, inspect current scripts before choosing shell syntax, Compose,
Ansible, workflow or Terraform validators. Distinguish syntax/config checks from
host convergence, image delivery, readiness and rollback execution.

## Real resource acceptance

A fake provider proves control flow only. When isolated Docker execution is within
scope, use a unique installation/test identity, loopback access, disposable storage
and generated private credentials. Record exactly which resources the test owns;
clean only those in a finally/recovery path. Never use global prune or target a
shared developer database. Do not print DSNs/passwords or raw secret-bearing SDK errors.

For the PostgreSQL foundation demonstrate request -> ready -> restricted SQL
connection -> lease extension -> deletion, plus duplicate requests and worker
restart. Verify data/ownership and actual container/volume removal, not only API
status. Add failure/concurrency tests where the affected contract requires them.
If Docker or another required tool is unavailable, report the specific unexecuted
acceptance; do not enable unsupported catalog options to make tests pass.

Return actual commands, environment, counts/results and limits. Separate pre-existing
failures from regressions using evidence. Repeat checks only for changes, failures
or unresolved concerns. Verification-only scope does not authorize application fixes,
live cloud calls, deployment or production migrations. Independent review requires
an actual separate review, not a role file or a planned command.

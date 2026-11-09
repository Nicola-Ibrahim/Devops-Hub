# Isolated backend checks

Select checks from changed behavior and acceptance criteria. Inspect fixtures,
imports and subprocess configuration before execution. Planning-only work
proposes checks; prose/skill edits need link/frontmatter/command validation, not
application suites. From `backend/`, using installed locked dependencies:

```bash
.venv/bin/ruff check src tests migrations
.venv/bin/ruff format --check src tests migrations
.venv/bin/mypy src
.venv/bin/pytest -q -m 'not postgres'
```

Narrow paths or selectors for focused changes. Run mypy from `backend/` for its
strict pyproject settings. Inspect unmarked tests: `not postgres` does not prove
every test is isolated. Do not implicitly install dependencies, rewrite
snapshots or substitute SQLite for PostgreSQL concurrency and migration behavior.

PostgreSQL integration tests need an explicitly supplied
`PLATFORM_TEST_DATABASE_URL` pointing to disposable local `devops_hub_test*`.
Read `backend/tests/conftest.py` first. Unique schemas do not make a shared
server disposable. Execute selected `-m postgres` tests only after verifying the
test target.

Real Docker acceptance, when in scope, needs unique installation/test identity,
loopback access, disposable storage and generated private credentials. Identify
owned resources and clean only those using a finally/recovery path. Never use a
global prune, shared developer database or printed DSN/password. For PostgreSQL
foundation show request, ready, restricted connection, lease extension, deletion,
duplicate request and worker restart; verify actual storage removal. Fake provider
tests establish control flow only. Check concurrent quota requests, interrupted
operations and restart recovery when those paths change. Report missing tools and
unexecuted acceptance without enabling unsupported catalog options.

Report commands, environment, counts and limits. Recheck only affected behavior
after changes; independent review requires an actual separate review.

# __APPLICATION_NAME__

Company-approved Python/FastAPI starter. Run `uv sync --locked`, `uv run ruff check app tests`, `uv run ruff format --check app tests`, and `uv run pytest`. Start locally with `uv run uvicorn app.main:app --reload`; `/healthz` is used by readiness checks.

Container builds run as a non-root user. Logs are structured JSON and should contain operational fields only. Never log credentials, connection strings, request authorization headers, or secret environment values.

The generated repository runs its own GitHub Actions CI workflow. It installs the locked dependencies with Python 3.12, checks formatting and lint with Ruff, and runs the test suite. Edit application files directly; template updates are proposed through pull requests and preserve files changed locally.

When a database is attached, the platform mounts a private read-only file and sets
`DATABASE_URL_FILE` to its path. No password or connection string belongs in an
environment value or repository. `/healthz` performs a bounded authenticated SQL
check when that reference is present, and returns only a generic failure if the
file or database is unavailable. Local services without an attached database do
not require that setting. Removing or expiring the database makes readiness fail.

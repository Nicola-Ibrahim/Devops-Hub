# Build the locked wheel once, then install only runtime dependencies and the wheel.
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.8.6 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/src ./src
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
RUN uv build --wheel --out-dir /wheels \
    && uv pip install --python /app/.venv/bin/python --no-deps /wheels/*.whl

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH"
RUN apt-get update \
    && apt-get install --yes --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 platform \
    && useradd --system --uid 10001 --gid 10001 --home-dir /app platform
WORKDIR /app
COPY --from=build --chown=10001:10001 /app/.venv /app/.venv
COPY --from=build --chown=10001:10001 /app/alembic.ini /app/alembic.ini
COPY --from=build --chown=10001:10001 /app/migrations /app/migrations
COPY --chown=10001:10001 templates /app/templates
COPY --chmod=0755 scripts/ops/backend-container-entrypoint.sh /usr/local/bin/platform-entrypoint
USER root
ENTRYPOINT ["/usr/local/bin/platform-entrypoint"]
EXPOSE 8000
CMD ["fastapi", "run", "--entrypoint", "api.asgi:app", "--host", "0.0.0.0", "--port", "8000"]

# Adding a New Service

This guide explains how to add a new microservice or background worker to the TOB ecosystem while maintaining compatibility with the standardized DevOps tools.

## 1. Create the Service Directory
Create a new directory for your service if it's a separate project, or a new sub-folder if it's part of a monorepo. Ensure it has a `pyproject.toml` (for Python services).

## 2. Infrastructure (Docker)
Update the local-only root `compose.yaml` to include your new service.

```yaml
services:
  my-new-service:
    build:
      context: ./path/to/service
      dockerfile: Dockerfile
    environment:
      - ENV=development
    depends_on:
      - redis
      - db
```

## 3. Secret Management
Provide ignored component env files and a tracked example containing names and
safe defaults only. Never put credentials in Dockerfiles, images, generated
application templates or ordinary API responses. Generated applications belong
in the versioned catalog under `backend/src/devops_platform/infra/templates/`;
operator hosting setup belongs in `ops/hosting/`. Developer-requested resource
behavior belongs behind a platform provider port and worker lifecycle.

## 4. Local orchestration

Keep the public command in `scripts/dev.sh` small. Add a service to local Compose
and to the explicit log allowlist when needed. Add standalone helpers only for a
specific filesystem or structured-data responsibility; never embed Python inside
Bash or introduce an installable developer CLI package.

## 5. Standardizing Commands
Ensure your service's `pyproject.toml` includes standard `poe` tasks if you want it to be compatible with the global orchestration:

```toml
[tool.poe.tasks]
serve = "fastapi dev src/main.py"
test = "pytest"
```

---

> [!IMPORTANT]
> Always use environment variables for configuration. Never hardcode credentials in your `Dockerfile` or `pyproject.toml`.

# Adding a New Service

This guide explains how to add a new microservice or background worker to the TOB ecosystem while maintaining compatibility with the standardized DevOps tools.

## 1. Create the Service Directory
Create a new directory for your service if it's a separate project, or a new sub-folder if it's part of a monorepo. Ensure it has a `pyproject.toml` (for Python services).

## 2. Infrastructure (Docker)
Update the root `docker-compose.yml` to include your new service.

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
Add a new project or config in **Doppler** for the new service. 

- Add required secrets (e.g., `API_KEY`, `DATABASE_URL`).
- Ensure the developer running `tob-dev up` has access to this new Doppler project.

## 4. Updates to `platform-dev` (Optional)
If your service requires specialized setup steps (e.g., seeding a specific database), you may need to extend a task in the `Devops` repository:

1.  Open `scripts/dev/platform_dev/tasks/workspace.py`.
2.  Add a function for your service's specific needs.
3.  Hook it into `scripts/dev/platform_dev/dev.py`'s `handle_up` logic.

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

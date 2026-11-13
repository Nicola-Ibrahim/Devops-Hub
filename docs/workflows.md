# GitHub Actions ownership

The root `.github/workflows/` directory contains workflows for the DevOps Hub
platform: CI and image publishing. Those jobs build and
operate this repository only.

Each approved application template owns its generated project's CI workflow:

| Template | Generated workflow | Checks |
| --- | --- | --- |
| Python/FastAPI | `catalogs/python-fastapi/1.0.0/.github/workflows/ci.yml` | Frozen uv install, Ruff, pytest |
| Node.js HTTP | `catalogs/nodejs-http/1.0.0/.github/workflows/ci.yml` | Frozen npm install and tests |
| ASP.NET Core | `catalogs/aspnet-core/1.0.0/.github/workflows/ci.yml` | Restore, build, health endpoint |

The catalog copies these hidden workflow files into the generated repository and
records them in `.platform-template.json` for managed updates. Generated projects
do not need access to a shared workflow repository or platform publishing secrets.
Changes to existing generated repositories follow the managed-file conflict
rules. Review template workflow changes together with the template's package
scripts and runtime version.

Application image publishing and deployment are separate operations. The platform
image publishing and deployment workflows in this repository do not grant generated
projects permission to publish images or deploy infrastructure.

The unused generic Docker publisher example and the legacy server deployment
workflow were removed. Compose is local-only. Server delivery requires a separately
authorized deployment contract with readiness and rollback before a workflow is added.

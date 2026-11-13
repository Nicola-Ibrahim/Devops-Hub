# TOB DevOps Component Hub

> Standardizing the developer experience through automated orchestration and operational intelligence.

The [Python API foundation](./backend/README.md) now provides health/readiness,
project-bound token authentication, lifecycle rules and control-plane migrations.
The local Docker provider and Next.js dashboard are present; integrated readiness
requires the acceptance checks in the [operations guide](./docs/operations.md).

Repository ownership:

- `ops/local/ansible/`: developer-machine bootstrap.
- `ops/hosting/`: optional Terraform hosting and Ansible host setup.
- `ops/monitoring/`: operator-managed monitoring configuration.
- `backend/src/identity/infra/authorization/policies/`: Identity OPA policy and tests.
- `backend/src/devops_platform/infra/`: platform adapters, workers and versioned application templates.

Compose is local-only. CI tests and builds images; publishing images does not
deploy them. The obsolete server release path has been removed.

---

## 💎 The Vision

In the Tracing Objectives Backwards (TOB) ecosystem, **DevOps is a product**, not a chore. This repository serves as the central "Command Center" for our engineering platform. By centralizing our CI/CD pipelines, local orchestration tools, and operational knowledge here, we ensure that every microservice inherits world-class engineering standards from day zero.

---

## 🏛 Ecosystem Architecture

The following diagram illustrates how this Hub empowers our service repositories (Backend, Frontend, etc.) with consistent automation and local tooling.

```mermaid
graph TD
    subgraph "Operations (ops/)"
        A[Reusable Roles] -->|Compose| D(Playbooks)
        D -->|STG/PRD| J[Cloud Servers]
        D -->|Local| E[Developer CLI]
    end

    subgraph "DevOps Hub (Scripts)"
        E -->|Executes| K[Local Environment]
        L[Reusable Workflows] -->|Import| M[GitHub Actions]
    end

    subgraph "Service Repositories"
        G[Backend Service]
        H[Frontend App]
    end

    K & M & G & H
```

---

## 🧱 The Three Pillars

Our platform is engineered around three fundamental pillars of reliability.

### 🚀 1. Continuous Automation (Workflows)
Hands-off, high-performance CI/CD pipelines that handle the heavy lifting of validation and distribution.
- **Unified CI**: Standardized linting and testing for Node.js and Python.
- **Image publishing**: Optional immutable ECR image publishing after successful CI.
- **[View Workflow Reference](./docs/workflows.md)**

### 🛠 2. Intelligent Orchestration (`platform-dev`)
The local "Dev Engine" that harmonizes your machine with our production-grade architecture.
- **Sync**: Locks backend dependencies via `uv`; private component env files configure the local runtime.
- **Boot**: One-command infrastructure startup with Docker Compose.
- **[Toolbox Deep-Dive](./docs/platform-dev.md)**

### 📖 3. Operational Intelligence (Knowledge)
The source of truth for everything from incident response to system scaling.
- **Runbooks**: Battle-tested recovery procedures for common infrastructure failures.
- **Scaling**: Standardized blueprints for adding new services to the cluster.
- **[Documentation Index](./docs/)**

---

## 🗺 Choose Your Path

### I'm a New Engineer
**Goal**: Get up and running in minutes.
- Follow the **[Zero-to-Hero Onboarding Guide](./docs/getting-started.md)** to configure your machine.

### I'm Feature Building
**Goal**: Daily development flow.
- Use `scripts/dev.sh up` and `scripts/dev.sh down` to manage your local stack.
- Check the **[Secrets Manual](./docs/secrets.md)** if adding new API keys.

### I'm Scaling the System
**Goal**: Adding a new service or infrastructure.
- Follow the **[Service Expansion Guide](./docs/new-service.md)** to ensure ecosystem compatibility.

---

## 🛠 Engineering Standards

| Area | Component | Philosophy |
| :--- | :--- | :--- |
| **Secrets** | Private runtime configuration | Local component env files are ignored; server secret delivery is separately scoped. |
| **Runtime** | [Docker](https://docker.com) | Local Compose; immutable application images. |
| **Python** | [uv](https://astral.sh) | Blazing fast, reproducible dependency management. |
| **Node.js** | npm | Lockfile-based frontend dependency management. |

---

*Internal / Proprietary - Nicola Ibrahim Ecosystem*



![Ansible Diagram](./docs/images/ansible.svg)
![Deployment Diagram](./docs/images/deploy_with_ansible.svg)

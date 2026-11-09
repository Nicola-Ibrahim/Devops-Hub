---
name: delivery-engineering
description: Implement or review DevOps Hub Docker, Compose, CI/CD, Ansible and Terraform delivery. Use for build, publish, deploy, readiness, rollback or hosting work; platform resource lifecycle uses backend-development.
---

# Delivery engineering

Follow [infrastructure guidance](../../../infra/AGENTS.md).

1. Trace source revision to immutable artifact, target, credentials, readiness,
   rollback and state ownership across the affected delivery files.
2. Define the failure and recovery contract before changing a stage. Preserve the
   responsibility boundaries in `infra/AGENTS.md`.
3. Implement one coherent stage with configurable environment values and no
   secrets in source, logs or generated artifacts.
4. Verify each stage independently: syntax, build, Compose health, Ansible
   convergence, Terraform plan, deployment readiness and rollback. Claim only the
   stages actually exercised.

Inspect exact targets before any live action. Code changes alone do not authorize
provisioning, migration, deployment, secret changes or destructive teardown.

---
name: delivery-engineering
description: Implement or review DevOps Hub Docker, Compose, CI/CD, Ansible and Terraform delivery work. Use for build, publish, deploy, readiness, rollback or hosting changes; resource provisioning inside the platform uses backend-development.
---

# Delivery engineering

Follow [infrastructure guidance](../../../infra/AGENTS.md). Keep the local Docker
demonstration usable without AWS or Azure credentials. For a delivery change:

1. **Trace the release path.** Inspect the affected Dockerfiles, Compose files,
   workflows, playbooks, Terraform modules, scripts and operations docs. Identify
   the source revision, immutable artifact, target environment, credentials,
   readiness signal, rollback path and state owner.
2. **Keep responsibility clear.** Terraform creates hosting infrastructure;
   Ansible configures hosts; CI/CD builds once, publishes and deploys; the platform
   API and workers provision developer-requested resources. Do not move runtime
   resource lifecycle rules into delivery automation.
3. **Design failure and recovery first.** Preserve protected Terraform state,
   least-privilege short-lived CI credentials, idempotent host configuration,
   immutable image identity and explicit migration compatibility. A published
   image is not a deployment, and a started container is not readiness.
4. **Implement the smallest coherent stage.** Keep environment-specific values
   configurable and secrets out of source, logs and generated artifacts. Do not
   add unsupported cloud targets or require cloud credentials for the core demo.
5. **Verify at the right level.** Run format, syntax and static validation first;
   then use disposable local acceptance where authorized. Distinguish workflow
   validation, image build, Compose health, Ansible convergence, Terraform plan,
   deployment readiness and rollback evidence. Never claim a later stage from an
   earlier check.

Inspect exact targets before provisioning, migration, deployment or cleanup.
Code changes do not authorize live infrastructure mutations, production secrets,
shared migrations or destructive teardown. Report commands, environment, artifact
identity, actual stage reached, recovery evidence and unverified limits.

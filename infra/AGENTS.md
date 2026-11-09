# Delivery architecture

Follow root [AGENTS.md](../AGENTS.md).

## Ownership

| Area | Responsibility |
| --- | --- |
| Terraform | Hosting network, compute, IAM and protected remote state |
| Ansible | Repeatable host configuration and platform service setup |
| CI/CD | Build once, publish immutable images, deploy, verify and roll back |
| Compose/Docker | Reproducible local platform and image runtime |
| Platform API/workers | Developer-requested databases and workloads |

Do not implement platform resource lifecycle rules in Terraform, Ansible or CI.
The core local demonstration must work without AWS or Azure credentials.

## Invariants

- Keep secrets out of source, plans, logs, images and generated artifacts. CI cloud
  access uses short-lived narrowly scoped credentials.
- Identify releases by immutable image digest. Publishing is not deployment;
  container start is not readiness.
- Ansible roles remain idempotent. Terraform state is protected and targets are
  explicit. Migration compatibility is part of deploy and rollback design.
- Validate syntax, build, convergence, deployment, readiness and rollback as
  separate evidence levels. Never claim an unexecuted level.
- Inspect the exact target before provision, migration, deployment or cleanup.
  Code changes alone authorize none of those live actions.

Use [delivery-engineering](../.agents/skills/delivery-engineering/SKILL.md) for the
delivery procedure. Add [system-design](../.agents/skills/system-design/SKILL.md)
only when a delivery contract crosses application components.

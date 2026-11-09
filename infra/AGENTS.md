# Infrastructure guidance

Follow the root [AGENTS.md](../AGENTS.md). Terraform provisions hosting
infrastructure; Ansible configures hosts; CI/CD builds, publishes and deploys
immutable application images with readiness and rollback. Platform API/workers
provision developer-requested databases and workloads.

Keep the local Docker demonstration usable without cloud credentials. Verify
syntax separately from host convergence, real deployment and rollback. Use
[delivery-engineering](../.agents/skills/delivery-engineering/SKILL.md) for Docker,
CI/CD and hosting changes; add [system-design](../.agents/skills/system-design/SKILL.md)
when contracts span application components. Inspect exact targets before any
provision, migration or cleanup; code changes alone do not authorize live
infrastructure operations.

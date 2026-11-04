---
name: architecture-review
description: Trace DevOps Hub context boundaries, application services, DI and worker ownership to review architecture or plan structural changes. Excludes routine local fixes.
---

# Review platform architecture

Follow `AGENTS.md`; platform-change owns phases, delegation and requested records.
Trace a representative API/CLI or worker path through composition, application,
domain and adapters. Inspect callers, imports, SQL access and DI lifetimes; folder
names are not proof of separation.

Evaluate identity and developer_platform independently. Application services receive
specific repositories and collaborator interfaces, not sessions, units of work or
containers. Contexts own their persistence mappings and repositories; technical
session/transaction handling lives outside core business code. The host owns
cross-context actor mapping, DI construction and outer commit/rollback. A request
transaction cannot roll back Docker or cloud effects; trace durable worker intent,
effect execution and recovery separately.

Keep delivery boundaries explicit: Terraform provisions hosting infrastructure;
Ansible configures hosts; CI/CD delivers releases; API/workers manage requested
developer resources. Next.js consumes contracts and does not provision infrastructure.
Use real business names and the smallest useful abstraction; do not add DDD layers,
generic repositories or forwarding wrappers solely for symmetry.

For findings give file/symbol, dependency or trigger, impact and smallest correction.
Separate defects from preferences. For proposals compare viable alternatives,
recommend one with reasons, identify affected callers/API/schema compatibility,
session lifetimes, concurrency, failure propagation and restart recovery. Include
ownership, ordered migration steps, rollback limits and observable checks. Label
current behavior and proposed diagrams distinctly.

For review/planning return evidence in chat or the permitted named task record;
stop before refactoring. Structural implementation requires implementation scope.
Use platform-verification for authorized check execution; do not duplicate its
isolation procedure or create extra design records.

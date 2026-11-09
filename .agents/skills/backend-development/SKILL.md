---
name: backend-development
description: Implement or review DevOps Hub Python backend domain, application, SQL persistence and resource workers. Use for DDD, CQRS, leases, providers, reconciliation or backend checks; API-only work uses api-development.
---

# Backend development

Follow [backend guidance](../../../backend/AGENTS.md). Trace the assigned use
case through application command/query, domain rules, repository port, adapter
and host before editing. Commands enforce domain invariants and save changes;
queries read authorized projections. Use entities and value objects for real
business concepts, not obligatory wrappers. Keep identity and developer_platform
independent; never import SQLAlchemy or provider SDKs into pure domain/application.

The host owns DI, cross-context actor mapping and outer SQL commit/rollback.
Application handlers receive narrow repositories/interfaces, never a session or
unit of work. Model external provider effects as durable work outside SQL
transactions. Put ORM mappings/repositories in the owning context's infra layer.
Keep methods and classes named for actual developer actions.

For temporary resource requests, leases, credentials, provider changes or
reconciliation, read [resource-lifecycle safeguards](references/resource-lifecycle.md)
before editing. Preserve atomic idempotency/quota, owner isolation, encrypted
secrets and interrupted-worker recovery. A passing fake adapter test does not
prove an actual database is reachable.

Use [backend checks](references/verification.md) to select focused isolated
verification. Record actual commands/results, simulated versus real provider
evidence and remaining limits. A routine small fix needs no task record.

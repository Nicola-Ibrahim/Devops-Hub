---
name: api-development
description: Implement or review DevOps Hub FastAPI endpoints, request/response schemas, authentication, DI wiring and HTTP tests. Use for API-facing changes; combine with backend-development when domain or worker behavior changes.
---

# FastAPI API development

Follow [backend guidance](../../../backend/AGENTS.md). Trace routes in
`backend/src/api/` to application handlers, composition providers and published
schemas before changing contracts. Keep endpoint functions thin: validate and
convert HTTP input, call injected application operations, and present explicit
responses. Domain rules and ORM access belong elsewhere. Prefer typed request
and response schemas, documented status codes, stable error codes and precise
dependency scopes; inspect the installed FastAPI/Dishka versions before adopting
framework features.

Authenticate internal users and authorize project/resource actions server-side.
Preserve idempotency keys and operation IDs for asynchronous requests. Use
appropriate HTTP status for queued work; expose status, ownership and expiry
without leaking credential values. Sensitive connection retrieval is an
explicit authorized action with safe logging and audit behavior. Ensure repeated
deletion and retries preserve the established contract.

When an API change crosses domain or persistence boundaries, read
[backend-development](../backend-development/SKILL.md) and agree on the application
contract first. For focused checks, use
[backend verification](../backend-development/references/verification.md),
including API contract and authorization tests. Distinguish static schema checks
from real provider acceptance. Update affected API/developer docs when contracts
or commands change.

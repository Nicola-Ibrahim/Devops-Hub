---
name: api-development
description: Implement or review DevOps Hub FastAPI endpoints, request/response schemas, authentication, DI wiring and HTTP tests. Use for API-facing changes; combine with backend-development when domain or worker behavior changes.
---

# FastAPI API development

Follow [backend guidance](../../../backend/AGENTS.md). For an API change:

1. Trace the affected route in `backend/src/api/` through the application
   handler, DI provider and published schema. Identify callers and existing
   request/response behavior before changing a contract.
2. Define the HTTP contract: typed input/output, authentication, project
   authorization, status codes, stable sanitized errors and retry semantics.
   Agree on an application contract first if domain or persistence changes.
3. Implement a thin endpoint that converts HTTP input, invokes an injected
   application operation and presents its result. Keep business rules and ORM
   access elsewhere. Inspect installed FastAPI/Dishka versions before using
   new framework features or changing dependency scope.
4. Check successful, denied, invalid and retry paths with focused HTTP tests;
   update affected API/developer docs and report what was actually verified.

Authenticate internal users and authorize project/resource actions server-side.
Preserve idempotency keys and operation IDs for asynchronous requests. Use
appropriate HTTP status for queued work; expose status, ownership and expiry
without leaking credential values. Sensitive connection retrieval is an
explicit authorized action with safe logging and audit behavior. Ensure repeated
deletion and retries preserve the established contract.

When an API change crosses domain or persistence boundaries, read
[backend-development](../backend-development/SKILL.md). For focused checks, use
[backend verification](../backend-development/SKILL.md#verification),
including API contract and authorization tests. Distinguish static schema checks
from real provider acceptance. Update affected API/developer docs when contracts
or commands change.

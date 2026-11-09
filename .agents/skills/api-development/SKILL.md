---
name: api-development
description: Implement or review DevOps Hub FastAPI routes, schemas, authentication, DI wiring and HTTP tests. Use for API-facing work; combine with backend-development when application or domain behavior changes.
---

# FastAPI development

Follow [backend architecture](../../../backend/AGENTS.md).

1. Trace the capability route through its schema, permission dependency, injected
   context module and DI binding; record current callers and contract behavior.
2. Define typed input/output, authentication, authorization, status codes, stable
   errors and retry/idempotency behavior. Resolve application contracts first.
3. Authenticate and check project/role permissions in API dependencies. Send a
   command or query through the context module; translate returned data and typed
   failures to HTTP without putting status codes in the application.
   Implement domain or persistence changes through
   [backend-development](../backend-development/SKILL.md).
4. Test successful, invalid, denied and retry paths. Update API/developer docs when
   a public contract or command changes.

Use the backend skill's focused checks. Distinguish HTTP/schema evidence from real
provider acceptance and report both accurately.

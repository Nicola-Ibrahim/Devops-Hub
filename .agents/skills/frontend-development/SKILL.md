---
name: frontend-development
description: Design and implement DevOps Hub Next.js dashboard flows, accessibility, API integration and frontend verification. Use for dashboard work; excludes backend-only changes.
---

# Frontend development

Follow [frontend guidance](../../../frontend/AGENTS.md).

1. Trace the developer action, API contract, affected components and current
   visual conventions. Define information priority before styling.
2. Design loading, empty, error, pending, ready, expired and denied states plus
   desktop, narrow-screen and keyboard behavior.
3. Implement within existing server/client boundaries and reusable visual tokens.
   Keep operation state tied to real API responses.
4. Run focused type/build checks and inspect responsive layout, focus, overflow
   and interaction when a browser is available. Report unavailable visual checks.

Use `npm run typecheck` and `npm run build` as applicable. A successful build does
not prove authentication, authorization, proxy/CSRF behavior or visual quality.

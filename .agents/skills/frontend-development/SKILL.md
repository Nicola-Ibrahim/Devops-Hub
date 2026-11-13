---
name: frontend-development
description: Design and implement DevOps Hub Next.js dashboard flows, accessibility, API integration and frontend verification. Use for dashboard work; excludes backend-only changes.
---

# Frontend development

Follow [frontend architecture](../../../frontend/AGENTS.md) and
[design guidance](../../../frontend/DESIGN.md). Those files own durable rules;
this skill owns the working procedure.

1. Trace the URL and developer action through page/layout, feature state, transport
   and backend contract. Inspect the current migration status and callers before
   moving code. Identify session/project ownership and failure behavior.
2. Assign route, feature and shared responsibilities before editing. For structural
   work, define preserved URLs, typed contracts and server/client boundaries first;
   migrate dependents together. Load system-design when contracts cross components.
3. For visual work, define information priority and precise capability wording.
   Start with a representative screen and its loading, empty, denied, error and
   operation states; apply the agreed tokens and motion consistently. Use available
   design tools when relevant and requested, without treating mockups as behavior.
4. Implement one coherent flow. Preserve project/session invalidation, CSRF,
   idempotency, secret clearing and polling cleanup under the architecture rules.
   Keep shared contracts settled before splitting independent file ownership.
5. Select checks for the changed behavior: direct links and history; project switch
   during a request; expiry versus outage; failed mutation/retry; and secret reveal
   cleanup where affected. Check narrow screens, keyboard/focus, overflow, textual
   status and reduced motion for visual changes. Report actual browser evidence
   separately from type/build results and identify unavailable checks.

Use `npm run typecheck` and `npm run build` as applicable. A successful build does
not prove authentication, authorization, proxy/CSRF behavior or visual quality.

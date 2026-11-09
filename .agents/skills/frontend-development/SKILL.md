---
name: frontend-development
description: Design and implement DevOps Hub's Next.js dashboard, styles, accessibility, API integration and focused frontend verification. Excludes backend-only changes.
---

# Next.js developer dashboard

Follow [frontend guidance](../../../frontend/AGENTS.md). For a dashboard change:

1. Trace the developer action and API contract. Read affected components,
   `frontend/src/app/globals.css` and package scripts; identify the screen's
   information hierarchy and current visual conventions.
2. Design the states and actions before coding: project/environment context,
   status, expiry, connection access, cleanup, loading, empty, error, pending,
   expired and denied. Decide how real operation status refreshes.
3. Implement within the existing Next.js server/client boundaries. Extend the
   visual system when it fits; substantial changes need a coherent direction.
   Preserve form values on errors and make narrow screens and keyboard use work.
4. Run focused type/build checks and inspect desktop/mobile layout and keyboard
   behavior when a browser is available. Report visual and integration limits.

Prioritize project/environment context, resource status, lease expiry,
connection access and cleanup actions. Use a consistent type scale, spacing,
surfaces, borders and semantic colors through reusable styles/components. Choose
deliberate typography and balanced density. Avoid charts without an operational
question. Make desktop tables readable and narrow-screen layouts intentional;
show timezone/expiry clearly and label destructive actions.

Provide loading, empty, error, pending, expired and permission-denied states;
retain form values on errors. Poll or refresh real operation status so queued
resources are never represented as ready. Use semantic HTML, labels, keyboard
navigation, visible focus, sufficient contrast, textual status indicators and
reduced-motion support.

Inspect Next.js server/client boundaries and dependencies before adding new
packages. Frontend permissions improve experience but backend authorization is
authoritative. Guest mode displays labeled demo data only. Never put credentials
in ordinary lists or persistent browser storage; retrieve sensitive connection
details only via authorized explicit API actions. Keep provider effects in backend.

Run `npm run typecheck` and `npm run build` as applicable. A build does not prove
login, authorization, proxy/CSRF or visual quality. When browser inspection is
available, check desktop/mobile layout, keyboard interactions and overflow;
report when visual checks were unavailable. Use image generation only when an
actual asset is needed. Return concise design and verification evidence.

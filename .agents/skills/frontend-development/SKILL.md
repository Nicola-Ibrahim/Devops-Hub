---
name: frontend-development
description: Design and implement DevOps Hub's Next.js dashboard, styles, accessibility, API integration and focused frontend verification. Excludes backend-only changes.
---

# Next.js developer dashboard

Follow [frontend guidance](../../../frontend/AGENTS.md). Read affected components,
`frontend/src/app/globals.css`, package scripts and API contracts. Identify the
developer's primary action and the screen's information hierarchy before coding.
Extend the existing visual system when it fits; substantial changes need a
coherent direction rather than isolated decorative components.

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

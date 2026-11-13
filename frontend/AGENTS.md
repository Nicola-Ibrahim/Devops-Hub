# Frontend architecture

Follow root [AGENTS.md](../AGENTS.md). The Next.js dashboard consumes backend
contracts; it never provisions resources or decides authorization.

## Target structure and dependency direction

```text
src/
  app/                     route composition, layouts and HTTP route handlers
    page.tsx               compact platform entry
    login/page.tsx         sign-in entry
    demo/page.tsx          explicitly synthetic preview
    dashboard/
      layout.tsx           persistent workspace shell
      page.tsx             overview
      resources/page.tsx
      resources/[resourceId]/page.tsx
      applications/page.tsx
      applications/[applicationId]/page.tsx
      account/page.tsx
      settings/page.tsx
      activity/page.tsx
    api/v1/[...path]/route.ts  same-origin backend proxy
  features/
    identity/              login, account, sessions and memberships
    workspace/             shell and shared session/project context
    resources/             catalog, lifecycle and connection interactions
    applications/          templates, previews and delivery views
    activity/              activity queries and presentation
  components/ui/           reused visual primitives
  lib/api/                 transport, typed errors and pagination primitives
  lib/formatting/          genuinely shared display formatting
```

Explicit pages, feature modules and the persistent workspace layout now follow
this structure. The former monolithic dashboard and screen catch-all are removed.
Create shared UI/formatting folders only when actual reuse warrants them. Route
structure is not evidence of authenticated provider acceptance; preserve URLs
and verify behavior when migrating further code.

- Pages compose feature views; layouts compose persistent shells. Use explicit
  routes for named screens and dynamic segments for entity identities. Keep
  catch-all routing for the backend proxy where it represents a real contract.
- Dependencies point from `app` to features to shared UI/technical helpers.
  Shared helpers and UI never import pages or features. Features expose narrow
  contracts; compose cross-feature views in the route or workspace layer rather
  than importing another feature's internal implementation.
- Keep feature API types, queries, hooks and UI with their owner. Extract shared
  contracts only when genuinely reused. Avoid a generic services/utils bucket.
- Pages/layouts remain Server Components by default. Put `use client` around
  interactive boundaries; compose client providers as narrowly as practical.
  Do not add `use server` merely to label an ordinary server helper.
- Shared session/project context owns identity and selection only. Features own
  their forms, queries, pagination and polling. Account screens must not start
  unrelated resource polling. Cancel requests and timers on disposal; discard
  responses from an earlier session or project generation.
- Keep client transport separate from server-only backend access. Browser calls
  use `/api/v1`; `BACKEND_URL` stays server-only. Personalized server requests
  forward only required credentials and never use a shared user-data cache.
- `src/app/globals.css` owns global tokens/base styles; scoped feature styles
  belong with their feature. Follow [DESIGN.md](DESIGN.md) for visual and copy rules.
- Never edit `.next/` as source. Avoid new dependencies unless an actual capability
  justifies them; a folder refactor does not require a new state or UI framework.

## Invariants

- Show project/environment context, operation status and lease expiry explicitly.
  Queued, ready, failed, deleting and expired are distinct states.
- Backend authorization is authoritative. Guest mode uses clearly labeled demo
  data and cannot expose privileged actions or real credentials.
- Connection secrets never enter ordinary lists, logs or persistent browser
  storage; retrieve them only through an explicit authorized action.
- Clear revealed credentials on dialog close, navigation, project change and
  session expiry. Clear passwords after submission; preserve only nonsecret form
  input on recoverable failures.
- Preserve same-origin proxy, cookie, CSRF and request-header contracts. Layout
  redirects and hidden controls are not authorization. Backend checks remain
  authoritative for every request; distinguish expired sessions from outages.
- Do not automatically retry a mutation with a new idempotency identity. Keep
  pending operations observable and do not present acceptance as readiness.
- Direct links, refresh and browser history must work. Unknown routes and invalid
  identifiers fail explicitly. Loading/error boundaries supplement feature-level
  denied, empty and recoverable error states; they do not replace them.
- Every flow handles loading, empty, error, denied and retry states. Preserve form
  input after recoverable errors.
- Use semantic HTML, labels, keyboard navigation, visible focus, sufficient
  contrast, textual status cues and intentional narrow-screen layouts.

Use [frontend-development](../.agents/skills/frontend-development/SKILL.md) for
the implementation and verification procedure.

<!-- BEGIN:nextjs-agent-rules -->

## This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->

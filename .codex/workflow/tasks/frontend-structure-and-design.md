# Frontend page structure and developer workspace redesign

## Current state

- **Updated:** 2026-11-13.
- **Authorized phase and scope:** frontend implementation complete with local build, source review and synthetic browser verification. No live resource or deployment authorization.
- **Next step:** user visual review, then separately authorized authenticated backend/provider acceptance if required.
- **Open decisions:** exact palette, density and motion should be validated on the workspace shell and Resources screen; no blocking product decision for this plan.
- **Baseline:** main, `0b9fcbc83f6ef00390f7aacd4854ae83de68d3ed`; implementation starts with prior guidance edits in frontend/AGENTS.md and frontend skill, plus untracked DESIGN.md and this task; preserve them. Index clean.
- **Latest verification:** production build, normal typecheck, four transport tests and diff checks passed. Synthetic Chrome interactions and desktop/narrow-screen screenshots inspected; independent source review findings fixed and rechecked. Real backend/provider acceptance remains unverified.

## Goal and evidence

Create a polished internal developer workspace with explicit pages, narrow client
boundaries and concrete operational wording. Preserve existing verified behavior.
`frontend/src/components/dashboard.tsx` is 843 lines and owns login, transport,
session/project state, polling, navigation and six screens. The optional catch-all
`src/app/dashboard/[[...section]]/page.tsx` manually selects screens; login renders
the dashboard. Detail pages have separate fetching. Module-level mutable token,
project and request-generation state currently protects against stale responses;
that behavior must survive extraction. These are source findings, not runtime proof.

Canonical rules now live in [frontend architecture](../../../frontend/AGENTS.md),
[design guide](../../../frontend/DESIGN.md) and the
[frontend skill](../../../.agents/skills/frontend-development/SKILL.md).
Explicit routes, feature ownership and the workspace shell are now implemented.
This task governs the new structure/design work. The earlier
[experience redesign record](frontend-experience-redesign.md) remains historical
evidence; its earlier implementation authorization does not expand this task.

## Scope and invariants

- In scope: explicit routes, workspace shell, typed API
  transport, session/project provider, feature extraction, scoped styles, visual
  tokens, restrained motion, useful landing page and precise interface copy.
- Out of scope: backend API changes, social login, new provisioning capabilities,
  deployment, cloud resources, secrets changes and a new frontend framework.
- Preserve existing landing/login/demo/dashboard URLs, entity deep links, safe
  post-login return paths, pagination, lifecycle actions and identity administration.
  Retain `/dashboard/overview` as an alias/redirect if `/dashboard` is canonical.
- Preserve authoritative backend permissions, cookie/CSRF proxy behavior,
  idempotency, project/session invalidation and explicit secret retrieval.
- Verification uses synthetic or explicitly disposable owned data. Do not read
  or print developer env files, expose connection credentials or start provisioning
  merely to inspect the design. No staging, commits or live deployment authorized.

## Acceptance criteria

- [x] Named dashboard screens have explicit page files; details use dynamic IDs;
  the catch-all screen dispatcher and obsolete monolithic dashboard are removed.
- [x] Login owns its form; workspace layout owns a persistent shell; account
  navigation does not trigger resource/application polling.
- [x] Shared transport imports no UI; session/project state has an explicit owner;
  late responses and timers cannot update a previous project or expired session.
- [x] Direct links, reload, back/forward, invalid IDs/routes and safe login returns
  work without relying on previous in-memory page state.
- [x] Existing actions, pagination, CSRF, denied/expired/outage behavior and
  idempotent retries remain correct; revealed secrets clear on relevant exits.
- [x] Shell and pages use coherent typography, spacing, status and action hierarchy;
  landing copy describes actual capability without slogans or unsupported claims.
- [x] Loading, empty, error, queued, ready and failed states are distinct; keyboard,
  narrow-screen layouts, focus, dialogs and reduced motion are inspected.
- [x] Typecheck/build and focused behavioral checks pass; actual visual and runtime
  evidence and remaining limitations are recorded independently.

## Contracts and ownership

- Coordinator owns URL compatibility, dependency direction, session/project
  contracts, migration integration and acceptance evidence.
- First coder stage owns `src/lib/api/` and agreed identity/workspace contracts;
  preserve existing API schemas and same-origin `/api/v1` transport.
- Shell stage owns dashboard layout and workspace feature; shared context contains
  session/selection, while feature hooks own queries and polling.
- Subsequent bounded coders own resources, applications, identity/account/settings
  and activity routes/features in separate stages or disjoint files after contracts
  settle. Assign exact paths at handoff; avoid overlapping `globals.css` ownership.
- Design/token owner owns shared CSS and UI primitives; page owners consume them.
- Independent reviewer reads the actual integrated diff against these criteria.

## Plan and progress

1. Completed: inspect current code and guidance; document target architecture,
   design direction and repeatable skill procedure.
2. Define/extract typed transport, error mapping, request invalidation and narrow
   session/project contracts. Add meaningful focused regression coverage.
3. Build persistent shell and Resources screen using DESIGN.md. Validate hierarchy,
   density, responsive behavior and motion before rolling the style across pages.
4. Extract login and explicit dashboard routes; migrate resource details/actions.
5. Migrate applications and delivery views, account/settings and activity. Parallel
   work is allowed only after shared contracts stabilize and ownership is disjoint.
6. Refine compact landing/demo, remove unused code/styles and update frontend README.
7. Independent diff review; fix confirmed findings, recheck affected behavior and
   update this task with actual commands/results and remaining limits.

Use official Next.js guidance for [layouts/pages](https://nextjs.org/docs/app/getting-started/layouts-and-pages),
[server/client composition](https://nextjs.org/docs/app/getting-started/server-and-client-components)
and [authentication](https://nextjs.org/docs/app/guides/authentication).
Feature-folder names are repository conventions, not a Next.js mandate. Layout
checks alone cannot secure nested routes or mutations.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| git status --short; git rev-parse HEAD | Clean baseline and revision recorded | Before documentation edits |
| rg --files frontend/src; wc -l dashboard.tsx | Route inventory and 843-line component confirmed | Source only |
| git diff --check | Passed | Documentation only |
| Skill frontmatter validation | Passed using backend/.venv/bin/python | System Python failed because PyYAML is absent; no dependency installation |
| Independent review | Poincare: no actionable findings | Actual guidance diff/new files; no runtime or visual checks |
| Application typecheck/build/browser checks | Passed within recorded local/synthetic scope | See implementation closeout below |

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| Bernoulli / 01a1d559-ce21-7031-bcbd-8e1a8edb741f | coder; repository role | New frontend/DESIGN.md only; clean baseline | Implemented design guide; reported diff/link checks passed |
| Coordinator | system-design, frontend-development, skill-creator | Guidance/task, CSS and application integration | Source review, final build/typecheck, four tests and synthetic browser verification |
| Poincare / 01a1d55c-efd2-7353-8f45-973551c8bab4 | reviewer; repository role | Actual documentation diff and new guide/task | No actionable findings; relative links and diff check passed |
| Arendt / 01a1d55e-9493-7360-9819-67c899be8fb6 | coder | Frontend TS/TSX and README; contracts before dependent routes/features | Completed; build/typecheck/tests passed; coordinator integrated and reviewed parity corrections |
| Dalton / 01a1d564-a173-7aa1-bdd1-1f795e7f5bb4 | investigator | Read-only baseline feature/endpoint parity checklist | Confirmed resource, template, local-preview, identity and pagination contracts; no live actions |

Implementation notes: coordinator owns CSS and regression tests, preserving
non-overlapping coder ownership. Four transport tests pass with mocked fetch
(`node --test tests/client.test.mjs` from frontend): CSRF/credentials, stale project
responses, expiry versus outage, and logout invalidation retaining CSRF. A synthetic
Chrome account-page check confirms no resource/application calls and no horizontal
overflow. These were intermediate checks; final results follow below. Initial root-relative test invocation
was corrected to run from frontend. Chrome required sandbox escalation; no package
installation or provisioned resources were used. Next dev appended its generated
version guidance to frontend/AGENTS.md; bundled Next docs were consulted.

Review status: independent implementation review by Zeno; confirmed findings
addressed and follow-up reports no actionable findings. Acceptance checkboxes
reflect implementation, source review and synthetic evidence below; they do not
claim every action was exercised against a real backend.

### Implementation closeout

- Arendt implemented TS/TSX feature/page extraction and README. Coordinator integrated
  CSS, feature-owned types, summaries, cancellation, session transition locking,
  loading/focus fixes and transport tests. No separate live-provider agent ran.
- The old dashboard, entity-detail, guest and identity component paths are removed;
  guest and identity views now belong to workspace/identity features. Explicit
  route pages compose feature views; `/dashboard/overview` remains an alias.
- Sessions/projects live in the persistent provider. Project/logout transitions
  unmount page content and prevent overlapping identity changes. Feature polling
  aborts superseded reads and disposal; late session/project results are rejected.
- Landing copy and styling follow DESIGN.md, with the promotional callout removed.
  Shared tokens and responsive composition remain in globals; feature base styles
  live beside their owners. Narrow navigation uses a readable grid; motion respects
  reduced-motion preferences.
- Reviewer Zeno (`01a1d59f-35dc-7391-bf4e-79499c275b23`) reviewed the actual source
  diff/new files read-only. Findings: initial false empty state and counting expired
  resources as expiring soon. Both fixed; follow-up also checked pagination cursors,
  feature type ownership, cancellation, catalog failure isolation and dialog focus.
  Reviewer ran no tests/browser; coordinator owns runtime evidence.

| Final command/check | Actual result | Limits |
| --- | --- | --- |
| `npm --prefix frontend run build` | Passed; explicit routes and dynamic detail routes emitted | Build loaded existing local env without printing values; no provider readiness claim |
| `npm run typecheck` from frontend | Passed after final integration | Earlier stale generated catch-all types resolved by build; one root-directory invocation was corrected |
| `node --test tests/client.test.mjs` from frontend | 4 passed | Mocked fetch: CSRF/credentials, stale generation/project, expiry/outage, logout CSRF |
| `git diff --check` | Passed | No staging/commits |
| `node /private/tmp/devops-hub-structure-review.mjs` with landing/resources/mobile/applications/account modes | Passed rendering; desktop 1440px and narrow 390px screenshots inspected, no page overflow | Temporary local CDP harness; API responses synthetic |
| Harness `interaction` | Dialog receives focus; Escape clears synthetic connection and restores Connect focus; Account navigation stops resource polling beyond a 5s interval | No real credentials retrieved |
| Harness `mutations` | Resource retry uses identical key/body; renew sends expected_revision/expires_at; confirmed delete sends DELETE | Browser requests intercepted; no resources provisioned/deleted |
| Harness `slow`, `expired`, `outage`, `reduced`, `overview` | Loading instead of empty; 401 routes to login; 503 retains Retry; reduced motion disables animation; expired resource excluded from soon-expiring count | Synthetic state checks; no real backend session test |
| Standalone `PORT=3100 HOSTNAME=127.0.0.1 node .next/standalone/server.js` | Started; static assets copied into generated runtime directory for local check | Sandbox escalation needed; no source/image/deployment mutation |
| HTTP GET route inventory | Named pages 200, unknown route 404; invalid IDs render not-found content | Invalid dynamic IDs return HTTP200 due streaming; no 404 status claim for them |

An initial `next start` attempt hit sandbox EPERM; after escalation it warned about
standalone output, so final runtime checks used the standalone entrypoint instead.
Intermediate browser checks during file replacement encountered compile errors;
final build and standalone checks passed. System skill validator lacked PyYAML;
the backend venv validator passed during the documentation phase. No dependencies
were installed and no env/secret files were changed.
Temporary standalone server and headless Chrome were stopped after verification;
the existing local Compose stack was not changed.

Remaining limits: real authenticated membership/password flows, provider delivery,
lease cleanup and database connectivity were not exercised. Application template/
preview parity was checked against baseline endpoints and independently reviewed;
synthetic application rendering was checked, not every application mutation. Full
browser history/project-switch race coverage beyond source guards and transport
tests remains a follow-up verification opportunity. These are verification limits,
not a claim of provider support or permission for live resources.

## Handoff

- Completed: guidance, explicit routes/features, workspace redesign, preserved
  baseline action contracts, build/type checks, focused tests and independent review.
- Remaining: user visual feedback and separately authorized real backend/provider
  acceptance; verification limits are recorded above.
- Next concrete action: review the workspace visually using the local stack;
  identify any requested refinements without provisioning resources implicitly.

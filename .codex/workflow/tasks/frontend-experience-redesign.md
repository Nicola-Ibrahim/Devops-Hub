# Developer portal experience redesign

## Current state

- **Updated:** 2026-11-13.
- **Authorized phase and scope:** planning only. This task record is the only authorized repository edit. No implementation, generated design files, provisioning, deployment, secret changes, staging or commits.
- **Next step:** agree on the visual direction and account-management scope, then explicitly authorize a bounded implementation phase.
- **Open decisions:** company branding/reference design; approval of the recommended visual direction; whether profile means existing identity/security capabilities or new editable profile fields; whether guest preview remains prominent.
- **Baseline:** branch `main`, HEAD `cd1114615c754c785a2bbf64855009c502c0337a`. Working tree is dirty. Staged work includes local preview API/domain/provider/contracts/tests, frontend dashboard/CSS/README, Compose and operations changes. Additional unstaged work includes local env/Compose cleanup and CI validation. Later inspection also shows component env examples and local env helper among existing changes. Preserve both index and worktree; do not treat these changes as part of this task or revert them.
- **Latest verification:** read-only source/API inspection and investigator report. No application, browser, build, accessibility or provider acceptance checks run for this plan.

## Goal and evidence

Create a welcoming landing page and a coherent workspace for company developers. Developers should find project resources, application delivery, operation progress and account security without navigating a single long mixed-purpose page.

Observed facts:

- `frontend/src/app/page.tsx` renders `Dashboard`. Login, guest and authenticated views currently share `/`; there are no distinct account or workspace routes.
- `frontend/src/components/dashboard.tsx` owns session bootstrap, project selection, resource lifecycle, application/template workflows and local previews. Sidebar destinations for templates/deployments are disabled despite related inline content. Avatar interaction signs out immediately.
- `frontend/src/components/identity-administration.tsx` already provides password, session and project-member controls. Reorganize and preserve these capabilities rather than claiming they are absent.
- Delivery retry has an API but no UI caller. Template applications lack some controls available for local previews. Application creation selects the first environment. Cursor pagination exists in resource/activity contracts but the UI loads fixed limits. Operation IDs held only in memory lose visibility on reload.
- Bootstrap errors can appear as unauthenticated state. Catalog/activity errors can appear as empty data; some preview/history polling errors are swallowed. A static connected footer does not establish service health.
- Identity API exposes identity/session/password/membership operations, but no inspected endpoint supports editing profile/email/avatar, MFA, account deletion, public registration or password recovery. Those features require a separate contract decision.

Sources: `frontend/src/app/api/v1/[...path]/route.ts`, `backend/src/api/identity/`, `backend/src/api/platform/`, and staged `backend/tests/contracts/openapi.json`. Source presence proves neither provider readiness nor successful runtime behavior.

## Scope and invariants

- In scope for the proposed implementation: landing, authentication transition, workspace routes/navigation, responsive visual foundations, existing account/security controls, and complete coverage assessment for developer-facing HTTP APIs.
- Out of scope unless separately authorized: new identity capabilities, social login, new providers, infrastructure changes, backend business-rule rewrites, public marketing claims about unsupported cloud features, live operations, and design publication.
- Preserve cookie authentication, same-origin proxy and CSRF protection, project permissions, idempotency keys, revision conflicts, lifecycle states, expiry and explicit audited connection reveal.
- No credentials in design tools, screenshots, fixtures, logs or persistent browser storage. Use synthetic design data. Account screens never receive platform infrastructure secrets.
- Keep guest mode demonstrably synthetic and read-only. Render backend/provider failures distinctly from empty results and anonymous sessions.

## Proposed experience and visual direction

Recommended direction: a calm enterprise developer workspace with light neutral surfaces, dark navy navigation, restrained teal/blue accents, clear typography and compact readable tables. Use monospaced text for IDs and technical details. Status badges always include text; reserve saturated colors for meaningful state and primary actions. Avoid oversized marketing cards inside operational screens.

Landing `/`: concise value proposition, honest supported capabilities, a synthetic workspace preview, documentation/access guidance and one primary “Open workspace” action. Keep the landing accessible regardless of session state. On continue, resolve the existing session: authenticated users enter the workspace; anonymous users go to sign-in; a service error offers retry rather than asserting logout. Preserve only validated same-origin return paths.

Proposed destinations:

| Area | Routes and purpose |
| --- | --- |
| Entry | `/`, `/login`; optional explicit demo entry |
| Overview | `/dashboard`; selected project, actual resource/operation summaries and recent activity |
| DevOps | `/dashboard/resources`, resource details, `/dashboard/applications`, application details, templates and operation/activity views |
| Account | `/dashboard/account`; current identity, password, sessions, logout-all |
| Project settings | Membership administration scoped to the selected project and authorized role |

The avatar opens an account menu with explicit sign-out. Project and environment remain visible in the workspace shell. Deep links and browser navigation preserve context without storing secrets.

## Acceptance criteria

- [ ] Landing loads without authentication and gives a clear next action; no unsupported provisioning claims.
- [ ] Continue handles authenticated, anonymous, expired-session and unavailable-backend cases distinctly; return paths cannot redirect off-site.
- [ ] Workspace, Account and DevOps destinations have working URLs, active navigation and responsive layouts at 360, 768 and 1440 CSS pixels without page overflow.
- [ ] Existing password/session/member controls remain usable, permission checked and discoverable. Unsupported profile actions are omitted or separately scoped, never simulated as successful.
- [ ] Before coding API integrations, produce a method/path coverage matrix for every current OpenAPI operation: destination, permission, loading/empty/error/success behavior, or justified exclusion. Operator-only workflows, webhooks, health and metrics are not exposed as arbitrary developer actions.
- [ ] Resource request/detail/renew/delete/connection, cursor pagination, operation recovery and activity show real server state. Queued does not mean ready.
- [ ] Templates, application registration, environment selection, details, database attachment, deployments/history and retry map to supported contracts and permissions.
- [ ] Loading, empty, denied, conflict, offline and retry states are explicit; recoverable failures preserve form input and request idempotency identity.
- [ ] Keyboard navigation, visible focus, labelled inputs, dialog focus/return, screen-reader announcements, contrast and reduced motion are checked.
- [ ] Existing affected behavior passes focused checks; browser evidence covers auth/CSRF and critical flows. Mock and real-provider evidence are labelled separately.

## Contracts and ownership

- Coordinator owns route/auth transition contract, API coverage matrix, scope decisions and integration. Confirm contracts before dependent screen work.
- Frontend owns presentation, routing, state and HTTP adaptation. Backend remains authoritative for access, ownership, quotas, lifecycle and supported provider capabilities.
- Identity payloads currently use camelCase; platform payloads use snake_case. Preserve or explicitly adapt at the API client boundary.
- Proxy accepts GET/POST/PUT/DELETE, forwards cookies and selected headers, requires same-origin mutations and CSRF except login, and returns 503 for missing configuration/502 for upstream failure. Preserve these distinctions.
- Proposed coder A ownership: landing/login routes and shared shell after route contract agreement. Coder B: resource/application views after API client contracts settle. Coder C: account/membership views. Assign exact paths before spawning; shared CSS/tokens/client modules have one owner. Do not parallelize edits to the current monolithic dashboard.

## Plan and progress

1. Completed: inspect branch/HEAD/index/worktree and trace current routes, API consumers and failure handling.
2. Pending: resolve visual/account decisions. Compare three directions in a later authorized design phase: recommended light enterprise workspace, dark technical console, or light editorial portal with a dark navigation rail. Prefer the first for daily use and readable operational data.
3. Inventory current OpenAPI methods against user journeys and permissions; classify unsupported desired account actions and agree any new contracts before dependent edits.
4. Define tokens, typography, spacing, status language and accessible primitives; approve landing, resource list/detail and account screen references before full rollout.
5. Establish route/session/client contracts and extract the shell from the monolith in a bounded stage. Sequence contracts before screens; preserve existing local-preview work.
6. Implement landing/auth transition, then account and DevOps destinations. Parallelize only agreed independent file sets after shared foundations land.
7. Integrate API coverage, pagination, reload recovery and failure states; verify critical paths and responsive accessibility.
8. Request an independent reviewer against the actual implementation diff and criteria; address confirmed findings and recheck affected behavior. Update this record with actual results and remaining limits.

## Design tools and constraints

- Canva: read-only `list_brand_kits(limit=3)` returned no brand kits. No designs generated or edited; no Canva design recommendation is claimed.
- Figma: `whoami` succeeded after an authentication retry. No target design file or selection was supplied. No library assets inspected and no design created; account access is not design evidence.
- Superdesign: loaded the requested plugin skill. Its existing-codebase design workflow requires initialization files. User authorization permits only this task record to change, so initialization, CLI generation and canvas drafts were deferred. No Superdesign output is claimed.
- Later design authorization should permit draft artifacts and synthetic context explicitly, and identify a Figma file/company reference if one exists. The visual recommendation above is the coordinator's proposal, not a result generated by these tools.

## Verification and review

| Check or review | Actual result | Scope and limits |
| --- | --- | --- |
| Git baseline and source inspection | Completed | Read-only; dirty baseline retained |
| Investigator trace | Completed | Source/contract inspection only, no runtime checks |
| Canva/Figma availability | Completed as described above | No generated mockups or visual evaluation |
| Task-record self-review | Completed | Plan reviewed for scope and safeguards; no independent implementation review |
| Build, typecheck, browser, API/provider tests | Not run | No implementation authorized |

### Agent activity

| Runtime agent/thread | Role and instruction source | Assigned scope and baseline | Actual findings and checks |
| --- | --- | --- | --- |
| Hegel, `01a1d261-de00-7651-9e4d-324d35731d48` | Existing coder runtime reused with explicit read-only investigator assignment; repository investigator responsibilities | Current frontend routes/components, backend identity/platform HTTP contracts; dirty main baseline above | Returned source references, coverage gaps, unsupported account actions, auth/error failure paths and open questions; no edits or runtime verification |

## Handoff

- Completed: planning record, current behavior trace, proposed navigation/design direction, ordered ownership/dependencies and measurable acceptance criteria.
- Remaining: visual approval, account-scope decision, API coverage matrix, authorized mockups and implementation, actual verification and independent diff review.
- Next concrete action: user reviews this plan and chooses the visual/account scope; implementation requires explicit authorization.

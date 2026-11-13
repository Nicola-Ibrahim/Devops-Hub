# Developer portal experience redesign

## Current state

- **Updated:** 2026-11-13.
- **Authorized phase and scope:** implementation authorized by the user on 2026-11-13. Existing API capabilities and recommended enterprise styling; no live resources, deployment, production-secret changes, staging or commits.
- **Next step:** user visual review; real authenticated API/provider acceptance remains an explicitly separate live-resource activity.
- **Decisions:** proceed with light enterprise surfaces, navy navigation and teal accents; Account uses existing identity/security capabilities; preserve explicit synthetic guest preview. New profile fields, MFA and account deletion remain separate contract work.
- **Baseline:** branch `main`, HEAD `cd1114615c754c785a2bbf64855009c502c0337a`. Working tree is dirty. Staged work includes local preview API/domain/provider/contracts/tests, frontend dashboard/CSS/README, Compose and operations changes. Additional unstaged work includes local env/Compose cleanup and CI validation. Later inspection also shows component env examples and local env helper among existing changes. Preserve both index and worktree; do not treat these changes as part of this task or revert them.
- **Latest verification:** production build, TypeScript, diff checks, responsive browser checks and synthetic session/lifecycle UI checks passed. Independent reviewer finding fixed and rechecked. No real provider resources were created.

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

- [x] Landing loads without authentication and gives a clear next action; no unsupported provisioning claims.
- [x] Continue handles authenticated, anonymous and unavailable-backend cases distinctly; return paths cannot redirect off-site. Existing 401 session-expiry behavior is preserved.
- [x] Workspace, Account and DevOps destinations have working URLs and active navigation. Landing checked at 360/768/1440, all six workspace destinations at 360 and overview at 1440; no horizontal overflow in tested states.
- [x] Existing password/session/member controls remain discoverable with backend permissions preserved; unsupported actions are omitted. Real account mutation acceptance remains unexecuted.
- [x] Method/path coverage matrix recorded below; operational endpoints and alternate transports are explicitly excluded. Contracts were inspected before additional integrations.
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

- Completed: public landing, login/session transition, six workspace destinations, entity details, Account/Project Access separation, redesigned responsive styling, developer API coverage assessment, resource pagination, operation reload recovery, delivery controls and independent review fixes.
- Remaining: real authenticated backend/provider acceptance; exhaustive assistive-technology and contrast audit; company-specific branding refinements. No cloud/provider readiness is claimed.
- Next concrete action: review the implemented visual direction locally, then schedule any authorized real API/resource acceptance separately.

## Implementation API coverage contract

Coordinator owns landing, routes, CSS, entity details and integration. Coder Kuhn owns dashboard.tsx and identity-administration.tsx. Route/session contracts precede dependent edits. Backend authorization, cookies, CSRF, idempotency and revision checks remain canonical. Every read must handle loading/empty/error/retry/denied; mutations handle pending, validation/conflict, failure and success.

| Method | Path | UI destination or exclusion |
| --- | --- | --- |
| GET | `/api/v1/applications` | Applications |
| POST | `/api/v1/applications` | Applications |
| POST | `/api/v1/applications/local-preview` | Applications |
| GET | `/api/v1/applications/{application_id}` | Applications |
| GET | `/api/v1/applications/{application_id}/deployments` | Applications |
| POST | `/api/v1/applications/{application_id}/deployments` | Applications |
| POST | `/api/v1/applications/{application_id}/resources` | Applications |
| POST | `/api/v1/applications/{application_id}/steps/{step_id}/retry` | Applications |
| POST | `/api/v1/auth/login` | Login / Account / session bootstrap |
| POST | `/api/v1/auth/logout` | Login / Account / session bootstrap |
| POST | `/api/v1/auth/logout-all` | Login / Account / session bootstrap |
| POST | `/api/v1/auth/project` | Login / Account / session bootstrap |
| GET | `/api/v1/catalog` | Resources |
| GET | `/api/v1/me` | Token principal alternative; UI uses browser principal |
| GET | `/api/v1/me/browser` | Login / Account / session bootstrap |
| POST | `/api/v1/me/password` | Login / Account / session bootstrap |
| GET | `/api/v1/me/sessions` | Login / Account / session bootstrap |
| DELETE | `/api/v1/me/sessions/{session_id}` | Login / Account / session bootstrap |
| GET | `/api/v1/operations/{operation_id}` | Resource operation tracking |
| GET | `/api/v1/projects` | Workspace project selector |
| GET | `/api/v1/projects/{project_id}` | Metadata alternative; UI uses project collection |
| GET | `/api/v1/projects/{project_id}/activity` | Overview / Activity |
| GET | `/api/v1/projects/{project_id}/members` | Project Access |
| DELETE | `/api/v1/projects/{project_id}/members/{user_id}` | Project Access |
| PUT | `/api/v1/projects/{project_id}/members/{user_id}` | Project Access |
| GET | `/api/v1/projects/{project_id}/resources` | Resources |
| POST | `/api/v1/resources` | Resources |
| DELETE | `/api/v1/resources/{resource_id}` | Resources |
| GET | `/api/v1/resources/{resource_id}` | Resources |
| POST | `/api/v1/resources/{resource_id}/connection` | Resources |
| POST | `/api/v1/resources/{resource_id}/renew` | Resources |
| GET | `/api/v1/templates` | Applications |
| POST | `/api/v1/webhooks/github` | Excluded signed server webhook |
| GET | `/health/authorization` | Excluded operational probe |
| GET | `/health/live` | Excluded operational probe |
| GET | `/health/ready` | Excluded operational probe |

Hidden /metrics is excluded from developer actions. Permissions remain defined by backend routes and platform authorization; API availability does not establish provider readiness.

## Implementation results and review

The implementation authorization supersedes the earlier planning-only steps and design-generation deferral. The coordinator selected the proposed visual direction and existing account scope without adding unsupported backend contracts. No external design artifacts were generated or published. Staged changes were preserved; this task adds unstaged frontend changes and this record only.

- Public `/` has a synthetic workspace illustration, capability/lease explanation and session-aware workspace entry. `/demo` is explicit synthetic exploration.
- `/login` handles sign-in and safe dashboard return paths; bootstrap outages show retry instead of masquerading as logged-out state.
- Routed Overview, Resources, Applications, Account, Settings and Activity have working navigation. Resource/application UUID detail routes use authorized GET APIs, with error/denied/sign-in states and management links.
- Account separates existing password/session controls from project membership administration. Avatar opens Account; sign-out is explicit.
- Resource cursors load more and polling follows fresh cursors while retaining loaded depth. Operations recover from activity after navigation/reload. Activity has **no backend cursor contract** (correction to initial investigator assumption); load-more expands the API-returned activity collection locally, without promising unbounded history.
- Applications now offer explicit environment selection, failed step retry, template and local-image delivery/history controls. Non-preview template attachment uses a one-hour lease clamped to catalog policy; preview attachment remains bounded by its remaining lease. Target/provider rejection remains authoritative. Preview links allow only credential-free HTTP(S) loopback URLs.
- Catalog/activity/history failures are visible. Modal focus enters the dialog, Tab cycles, Escape dismisses and focus returns. Resource/connection secrets remain in page memory only.
- Self-review fixed an effect dependency loop, cursor refresh drift and duplicated summary counts. Reviewer found nullable activity actors could crash rendering: type now admits null and labels those events “system.” Reviewer confirmed the fix and found no concrete regression in the attachment/operation corrections.

| Actual command/check | Result | Limits |
| --- | --- | --- |
| `npm run typecheck` from frontend | Passed | Final checks include new routes and components |
| `npm run build` from frontend | Passed | Next.js production compilation, type validation and route generation; no runtime provider evidence |
| `git diff --check` | Passed | Working-tree whitespace only |
| `node /private/tmp/devops-redesign-browser.mjs` | Passed | Headless Chrome/CDP: landing 360/768/1440, six workspace pages at 360, overview 1440, anonymous redirect, unavailable-backend state, no JS exceptions or horizontal overflow in fixtures |
| `node /private/tmp/devops-redesign-flows.mjs` | Passed | Synthetic API interception: pagination survives polling, operation recovery, connection modal focus/Escape, null actor, non-preview template attach enabled, unsafe return rejected. Actual local proxy rejected missing origin/CSRF. No real resource mutations |
| Screenshot inspection | Completed | `/private/tmp/devops-landing.png` and `/private/tmp/devops-workspace.png`; synthetic screenshots, not committed artifacts |
| Real API/account mutations/provider readiness | Not run | No provisioning, production secrets, deployment, staging or commits |

An early typecheck was accidentally invoked from the repository root and failed because there is no root package.json; rerun from frontend passed. A transient type mismatch during coder edits was corrected before final checks. Browser scripts initially required local network permission and handling cancelled CDP interception IDs; corrected runs above passed. Next dev generated an AGENTS rules block and dev type paths; generated incidental changes are removed after stopping the owned dev process.

### Implementation agent activity

| Runtime thread | Role and ownership | Actual outcome |
| --- | --- | --- |
| Kuhn `01a1d459-c260-7531-b353-a90cbc91d025` | `coder`; only dashboard.tsx and identity-administration.tsx; explicit contracts and criteria assigned | Routed sections/auth, environment selection/retry, then pagination/recovery/errors/general delivery and dialog handling. Reported typecheck/diff checks passing. Coordinator inspected integration and corrected issues above. Agent's initial “clean baseline” description was inaccurate: coordinator baseline was staged/dirty and preserved |
| Beauvoir `01a1d464-4e98-7ad3-abf5-846047d1c936` | Independent `reviewer`; read-only actual frontend diff against INDEX, including new routes/components and relevant API contracts | Confirmed P2 null actor crash; fix addressed and source-rechecked. No other confirmed defects. No reviewer runtime/provider checks |

Review status: independent read-only review performed, confirmed finding resolved. Current completion is frontend implementation with simulated browser/HTTP safeguards evidence; remaining live and exhaustive accessibility checks are explicitly unclaimed.

# DevOps Hub developer dashboard

The Next.js App Router dashboard calls the Python API through a same-origin
server route. The browser never receives the API's internal address and does not
store session or bearer tokens in web storage.

## Local development

The public landing page is `/`. Open workspace checks the existing browser session
before entering `/dashboard` or continuing to `/login`. Workspace navigation has
separate Resources, Applications, Account, Project Settings and Activity pages;
resource and application IDs have read-only detail URLs. `/demo` contains only
synthetic preview data. Account settings cover the current identity, password and
sessions; editable profile fields and public registration are not supported by
the current backend contracts. A backend outage shows a retry state separately
from an expired session.

Use Node.js 22 or newer. From this directory:

```sh
npm ci
BACKEND_URL=http://localhost:8000 npm run dev
```

`BACKEND_URL` is read by the server-side API proxy. The non-secret
`frontend/.env.example` template records the value for Compose to inject into the
frontend container, where the backend is reachable as `http://api:8000`. When
running `npm run dev` directly on your machine, use `http://localhost:8000`
instead; the Compose service hostname `api` is available only inside the Compose
network.

Configure the backend to accept the dashboard's exact browser origin (normally
`http://localhost:3000`) for cookie-authenticated mutations. Internal accounts
must be created by an operator; the dashboard has no public registration flow.

The proxy accepts only GET, POST, PUT and DELETE, forwards only the request headers
needed by the API, and marks responses private and non-cacheable. Configure
`BACKEND_URL` only on the server. Browser mutations require same-origin requests;
all mutations except login also require the in-memory CSRF token returned by the
browser identity API. The identity service owns the HttpOnly session cookie.

The resource form follows the typed catalog. It remains disabled while an
option is not requestable, so a queued API ledger entry is never presented as a
ready database. Connection details are fetched only after the developer chooses
Connect and are held in page memory until the dialog is closed. Deletion asks for
confirmation and explains that the database volume and its data will be removed.

## Checks

```sh
npm run typecheck
npm run build
```

## Account and project administration

Visitors can choose **Visit as guest** on the sign-in screen to explore a read-only
dashboard preview without an account. Preview content is illustrative; resource
actions require sign-in and guest mode grants no API access.

The Identity administration panel uses the existing internal identity APIs:

- Review active session IDs and timestamps; revoke another session, end the current
  session, or sign out all sessions. Ending the current session requires sign-in again.
- Change the current password with confirmation. A successful change invalidates
  all sessions; password fields are held only in page memory and cleared after an attempt.
- Project administrators can add an operator-created account by its existing user
  UUID, change project roles, and remove members. This does not create accounts.
  The server rejects unauthorized changes and changes that would remove required
  administrator access; the panel displays those rejections.

Account creation and password recovery remain trusted operator workflows documented
in [the backend guide](../backend/README.md). Project controls follow the selected
project; application code does not replace backend permission checks.

## Local preview prototype

The local preview panel is separate from creating an application from a template.
It registers a named application with a lease, then asks for an image digest on
each explicit deployment action and offers separate database attachment. When a database is attached,
deployment stays disabled until its resource status is `ready`; deployment without
a database remains available. A successful deployment address is displayed only
when it is a loopback URL, and is labeled for access from this machine only.

Deploy input accepts a repository digest (`repo/image@sha256:…`) or a configured
immutable local Docker image ID (`sha256:` followed by 64 lowercase hex digits).
Mutable image tags are not accepted. The backend owns digest validation and its
approved image allowlist. No credentials are stored by this flow.

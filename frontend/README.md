# DevOps Hub developer dashboard

The Next.js App Router dashboard calls the Python API through a same-origin
server route. The browser never receives the API's internal address and does not
store session or bearer tokens in web storage.

## Local development

Use Node.js 22 or newer. From this directory:

```sh
npm ci
BACKEND_URL=http://localhost:8000 npm run dev
```

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

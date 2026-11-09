# Frontend guidance

Follow the root [AGENTS.md](../AGENTS.md). This Next.js dashboard lets developers
find their projects, request approved resources, track operations and expiry, and
perform authorized lifecycle actions. Consult [frontend setup](README.md), current
API schemas and [frontend-development](../.agents/skills/frontend-development/SKILL.md).

Backend API/worker owns provisioning, permissions and secrets. Frontend checks
improve experience but never replace backend authorization. Guest mode shows only
clearly labeled demonstration data. Do not persist connection credentials in browser
storage or display them in ordinary resource lists. Distinguish queued, ready,
failed, deleting and expired states; never present a request as ready before the
operation completes.

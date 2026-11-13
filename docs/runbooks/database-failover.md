# Local database connection recovery

The control-plane service is named `postgres`. This repository does not implement
automatic database failover. Diagnose without removing its data:

```sh
docker compose --profile app ps
docker compose --profile app exec postgres pg_isready -U platform -d platform
```

If authentication fails, restore the existing private `backend/.env` credentials.
Changing POSTGRES_PASSWORD does not change an already initialized database's
password. Do not generate replacement encryption keys or delete volumes to fix a
connection problem. Check storage capacity, Docker availability and the API's
readiness endpoint before planning recovery.

For corruption, preserve the failed volume and follow the isolated restore and
reconciliation procedure in [operations](../operations.md). Restoring control-plane
rows does not prove that developer resource containers or credentials agree with
that state. Resume worker effects only after ownership and keys are verified.

# Local development setup

Install Docker Engine/Desktop with Compose v2, Python 3.12/uv for backend checks,
and Node.js 22/npm for frontend development. Start Docker before the local stack.

From the repository root:

```sh
scripts/dev.sh up
```

The script initializes missing private component env files and starts the core
local services. Backend and dashboard setup/check commands are documented in
[backend](../backend/README.md) and [frontend](../frontend/README.md).

Optional developer-machine bootstrap lives in `ops/local/ansible/`; it installs
local tools and the repository pre-commit hook. Server setup is separate under
`ops/hosting/ansible/` and must never target a developer machine accidentally.
Doppler, AWS and Azure are not prerequisites for the local demonstration.

Workers are opt-in. Follow [operations](operations.md) before enabling resources
or application delivery; startup does not establish provider readiness. Stopping
Compose preserves data volumes. Never use global prune or volume deletion for
routine shutdown. Preserve component env files while their database data exists.

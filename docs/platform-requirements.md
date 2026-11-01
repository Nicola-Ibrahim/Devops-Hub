# Developer platform requirements

This document captures the intended product. The repository contains automation
tooling and a Python API foundation with health, identity and catalog contracts.
Resource lifecycle endpoints, the dashboard and provisioning service are not implemented.
This is a requirements reference, not a task list or implementation authorization.

## Developer outcome

A developer selects an available resource template and target, supplies a project,
branch reference and lease duration, and requests provisioning. Once the database
is ready, the developer can securely retrieve a connection string and use it from
the documented network location. The platform tracks ownership and usage, enforces
limits, and revokes access and removes resources when the lease ends.

## Technology and provider boundaries

- Python backend/API and provisioning worker; Next.js developer dashboard.
- A complete local Docker demonstration without cloud accounts is the first delivery.
- Configured servers are an intended additional target. A server may run Docker;
  the platform must have an explicitly configured execution and credential path.
- Keep resource templates separate from target/provider configuration. Each provider
  advertises supported resource types, sizes, versions and operations. Unsupported
  combinations must be rejected before provisioning.
- Future Kubernetes or cloud adapters should preserve the common lifecycle while
  documenting provider-specific capabilities. Universal provider support is not
  implied by the interface.

## Essential capabilities

| Area | Required behavior |
| --- | --- |
| Catalog | Approved templates, supported versions, sizes, targets and lease limits; start with PostgreSQL |
| Identity | Authenticated users, project/team membership and roles for developer and administrator actions |
| Requests | Validate template, target, ownership, capacity and policy before accepting a request; return an operation/resource ID |
| Persistence | Record owner, project, branch, template, target, provider resource ID, requested configuration, status, timestamps and expiry |
| Provisioning | Run asynchronously; check readiness; record sanitized progress and useful failure reasons |
| Access | Dedicated resource credentials and authorized retrieval of a usable connection string; revoke access during teardown |
| Limits | Bound active resources, lease duration, CPU, memory and storage; reserve capacity consistently when requests arrive concurrently |
| Lifecycle | Inspect, renew within policy, cancel provisioning, request deletion and automatically expire resources |
| Recovery | Retry-safe creation/deletion, bounded retries, periodic reconciliation and recovery after worker restart |
| Audit | Record requests, state changes, renewals, access retrieval and deletion without credential values |
| Dashboard | Catalog, request form, resource inventory/detail, readiness, expiry, connection guidance and authorized lifecycle actions |
| Operations | Health checks, lifecycle metrics, sanitized logs, failed-cleanup visibility and recovery guidance |

## Connection strings and network access

The platform must return an endpoint reachable from the developer's intended
network, not merely an internal container hostname. Local, server, VPN or tunnel
access must be described explicitly for each target. Verify database readiness
separately from external network reachability; do not claim a connection is usable
from an untested location.

Full connection strings containing passwords belong behind an authenticated,
owner/role-checked retrieval operation. Exclude them from ordinary inventory and
status responses, logs, URLs and audit payloads. Protect stored credentials and
transport, mask them in the dashboard, and avoid persistent browser storage.
Do not use shared administrator credentials as developer database credentials.
Target administration and provider credentials must remain separate from resource
credentials. Server exposure and allowed network paths are configured by an
administrator, not chosen freely by request payloads.

## Lifecycle correctness

Define explicit states and allowed transitions before implementation. A successful
request acceptance does not mean the resource is ready. Track desired actions and
observed provider state so reconciliation can repair interrupted operations.

Repeated requests with the same idempotency key must not allocate duplicate
resources. Persist provider identity and ownership labels so a crash between
allocation and status recording can be reconciled. Deletion must tolerate an
already missing resource. Cancellation and deletion must not race with allocation
and leave a late-created database behind. Renewal and expiry must have consistent
ordering. Retain actionable cleanup failures and retry them; never mark deletion
complete while known resources or access remain.

## CI/CD and demonstrability

Containerize the backend, worker and dashboard with reproducible configuration and
health checks. CI validates the affected applications and exercises the provisioning
lifecycle using isolated resources available inside the runner. It must not depend
on a developer's laptop or cloud credentials.

Add branch/PR-triggered requests and closure cleanup after the basic API-driven
lifecycle works. Verify webhook identity, reject duplicates and scope cleanup to
the owning project and resource. Secrets must not be posted in PR comments or logs.

The initial demonstration should prove request, readiness, authorized connection,
expiry and deletion for independent resources, including recovery after restarting
the worker. Server provisioning is a later integration that requires a configured,
reachable target; local success alone does not establish server support.

## Expansion

Additional databases, caches, full preview environments, seeded test data, credential
rotation, notifications and cost reporting can extend the catalog when requested.
Their semantics and provider support must be designed explicitly. Backup/restore
and retained environments require their own data-retention policy; temporary
resource deletion should never silently become a backup strategy.

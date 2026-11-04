# Task records

Create a task record only when the user requests it. Use the
[task template](../templates/task.md) and keep scope, decisions, verification
and handoff together. This directory now keeps unfinished tasks only.

No feature tasks are preassigned. A record does not authorize implementation,
live provisioning, deployment, migrations or paid services.

## Deferred implementation tasks

The user requested this split on 2026-11-04. Select **one named task** for the next
work session. These are backlog specifications, not automatic assignments. Existing
partial code stays in the working tree; it has not been removed or marked complete.

- **Simple:** bounded coding/checks; no new architectural contract expected.
- **Design required:** investigate contracts, dependencies and failure behavior before
  implementation; the size indicates the amount of integration, not a promised time estimate.

| Order | Task | Priority | Classification | Size | Current state |
| --- | --- | --- | --- | --- | --- |
| **02** | [PostgreSQL recovery acceptance](02-postgres-recovery-acceptance.md) | P1 | Design required | Medium | Verification / remaining coverage |
| **03** | [Dashboard identity administration](03-dashboard-identity-administration.md) | P1 | Design required | Medium | Missing UI / existing API |
| **04** | [Platform observability acceptance](04-platform-observability-acceptance.md) | P2 | Design required | Medium | Partial / verification |
| **05** | [Control-plane backup and restore acceptance](05-control-plane-restore-acceptance.md) | P2 | Design required | Large | Existing assets / unverified recovery |
| **06** | [Ansible host and HTTPS acceptance](06-ansible-host-acceptance.md) | P2 | Design required | Medium | Existing assets / verification |
| **07** | [Platform release and rollback acceptance](07-platform-release-recovery.md) | P2 | Design required | Large | Existing assets / integration |
| **08** | [Secure application database attachment](08-application-database-attachment.md) | P3 | Design required | Large | Partially implemented |
| **09** | [GitHub template delivery acceptance](09-github-template-delivery.md) | P3 | Design required | Medium | Partial / external verification |
| **10** | [Application deployment visibility](10-application-runtime-visibility.md) | P3 | Design required | Medium | Partial / missing API |
| **11** | [Node and ASP.NET template validation](11-additional-template-validation.md) | P4 | Simple | Small | Verification / bounded fixes |
| **12** | [Pull-request preview workflows](12-pr-preview-workflows.md) | P4 | Design required | Large | Partially implemented |
| **13** | [Configured-server database connectivity](13-remote-database-access.md) | P2 | Design required | Large | Not implemented |
| **14** | [AWS hosting infrastructure validation](14-aws-hosting-validation.md) | P2 | Design required | Large | Existing assets / cloud deferred |

**Start with 02, then 03.** Task 01 is complete and its plan has been removed.
There are 13 unfinished tasks. Existing numbers are retained so references stay stable.

| Stage | Tasks | Outcome |
| --- | --- | --- |
| Local foundation | 02–03 | Stable backend, recovery confidence and internal administration |
| Operations and delivery | 04–07 | Monitoring, recovery, host setup and safe releases |
| Application self-service | 08–10 | Database attachment, templates and deployment visibility |
| Advanced developer experience | 11–12 | Additional languages and PR previews |
| Optional remote/cloud extension | 13–14 | Remote DB access and AWS hosting |

Numbers are the recommended sequence; the Dependencies field in each task lists
its actual prerequisites. If a host, registry or cloud account is unavailable,
leave that task deferred and continue a later task whose dependencies are satisfied.
Tasks 13–14 are optional for the cloudless portfolio demo. Do one named task at a
time; numbering does not authorize external operations or expand a task's scope.

## Completed prerequisites

Backend foundation, the boundary refactor and task 01 integration closeout are
implemented. Task 01 recorded 228 passing tests, 3 explicitly skipped Docker cases,
and 40 passing subtests; Ruff and strict mypy passed. These are historical results,
not proof that unfinished attachment, recovery, deployment or cloud tasks are done.
The relevant Docker/recovery acceptance remains in tasks 02 and 08.

Completed and superseded legacy plans were removed at the user's request. Their
unfinished scope is represented by the numbered records above. Use
[platform requirements](../../../docs/platform-requirements.md) for durable product
requirements. No implementation files were removed.

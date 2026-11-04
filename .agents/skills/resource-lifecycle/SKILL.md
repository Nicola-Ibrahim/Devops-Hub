---
name: resource-lifecycle
description: Inspect or change DevOps Hub resource requests, leases, SQL persistence, provider adapters and reconciliation while preserving ownership, secrets and restart recovery.
---

# Preserve requested resource lifecycles

Identify the requested operation, context-owned tables, callers and external target.
Follow AGENTS.md; platform-change owns coordination and any requested task record.
Read the relevant migrations, repositories, worker claims and provider implementation.
Do not infer working provisioning from a queued row or a successful fake adapter.

For read-only inspection, report evidence and recovery gaps without initializing
writers, repairing resources or reading secret values.

For authorized code changes, establish the affected invariants:

- Project/role authorization and ownership apply to requests, reads, extensions,
  deletion and credential retrieval; ordinary responses and logs exclude credentials.
- Persist request intent, idempotency identity and quota reservation atomically.
  Concurrent requests must not exceed limits or duplicate external allocations.
- Worker claims, generations and completion fencing survive duplicate delivery,
  crashes and late results. Keep database transactions short around external effects.
- Every temporary resource has creation time, owner, expiry, status and cleanup.
  Expiry and deletion revoke access and remove owned storage according to the contract.
- Uncertain effects retain recovery information and capacity until reconciled.
  An absent observation is not proof an in-flight creation cannot finish later.
- Provider operations use approved types/targets, deterministic ownership labels and
  bounded limits. Never adopt or delete foreign resources. Inspection must not
  silently recreate a missing database or lose its data.
- Preserve encrypted credential/key references, audit history and migration
  compatibility. A schema downgrade is not automatically a safe data rollback.

Distinguish invalid requests, provider unavailability, timeouts, drift and cleanup
failures. Define useful sanitized errors and retry limits rather than hiding them
as success. Keep provider SDKs and SQLAlchemy in adapters, not domain/application.

Use platform-verification for disposable SQL/Docker execution. Specify checks for
successful connection, duplicate requests, concurrent quotas, lease extension,
expiry/deletion, interrupted work and restart recovery as affected.

For explicitly authorized backup, restore, migration or cleanup, identify exact
source/destination and ownership first. Preserve recoverable state, verify consistency
and key availability without exposing values, and reconcile restored control-plane
state with provider observations. Stop before destructive follow-up when ownership
or consistency cannot be established. Code changes alone authorize no live data operation.

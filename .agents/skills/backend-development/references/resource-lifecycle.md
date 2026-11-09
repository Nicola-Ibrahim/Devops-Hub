# Resource lifecycle safeguards

Identify the operation, context-owned tables, callers and external target.
Inspect migrations, repositories, worker claims and provider adapters. For
read-only investigation, report gaps without initializing writers, repairing
resources or reading secret values.

- Enforce project/role authorization and ownership for requests, reads, lease
  extensions, deletion and sensitive credential retrieval. Ordinary responses and
  logs exclude credentials.
- Persist intent, idempotency identity and quota reservation atomically. Concurrent
  requests must not exceed quotas or duplicate allocations.
- Fence worker claims, generations and completion so duplicate delivery, crash
  recovery and late results are safe. Keep SQL transactions short around effects.
- Every resource has owner, creation time, expiry, status and cleanup. Expiry and
  deletion revoke access and remove owned storage according to the contract.
- Uncertain provider effects retain recovery information and capacity until
  reconciled. A missing observation does not prove in-flight creation has ended.
- Providers use approved resource types/targets, deterministic ownership labels
  and bounded limits. Never adopt or delete foreign resources. Inspection must
  not recreate missing databases or silently discard stored data.
- Preserve encrypted credential/key references, audit history and migration
  compatibility; a schema downgrade is not a safe data rollback by default.

Distinguish invalid input, provider unavailability, timeout, drift and cleanup
failure. Use sanitized error codes and bounded retries. For authorized backup,
restore, migration or cleanup, identify exact source/destination and ownership
first; preserve recoverable state,
validate consistency and key availability without exposing secrets, then
reconcile restored control-plane state with provider observations. Stop before
destructive follow-up if ownership or consistency cannot be established. Code
changes alone do not authorize live resource changes.

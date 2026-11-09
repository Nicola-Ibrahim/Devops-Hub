---
name: system-design
description: Trace and plan substantial DevOps Hub architecture, bounded context, delivery or cross-component changes; coordinate an authorized implementation and its handoff. Excludes routine local fixes.
---

# Design and coordinate platform changes

Follow the root and affected directory `AGENTS.md` files. Check branch, HEAD,
staged/unstaged work, current callers and any named task record before trusting
documentation. Use [workflow guidance](../../../.codex/workflow/README.md) and
create a task record from its template only when the user requests one. Planning
records do not authorize implementation, deployments or provisioning.

Trace a representative API/worker path through composition, application, domain
and adapters. Inspect imports, SQL access, DI lifetimes, provider effects, error
paths and restart recovery. Treat identity and developer_platform as separate
contexts. Model behavior with specific business names and the smallest useful
abstraction; do not add DDD layers or generic wrappers solely for symmetry.

For proposals, separate observed facts from hypotheses. Define acceptance
criteria, preserved behavior, contracts, dependencies, file ownership, ordered
steps and material user decisions. Compare alternatives when meaningful;
identify API/schema compatibility, transaction boundaries, concurrency, failure
propagation and rollback limits. Terraform provisions hosting; Ansible configures
hosts; CI/CD delivers releases; API/workers manage requested developer resources.

For authorized implementation, resolve shared contracts first; delegate bounded
independent files when useful. The coordinator integrates and verifies. Request
an independent read-only review of substantial diffs when available. Report
actual agent activity, commands, results and unresolved limits. If no separate
review ran, identify a self-review. Preserve previous evidence when its code and
assumptions remain valid; update the requested task record or report in chat.

For changes to delivery scripts, providers, CI, Ansible or Terraform, inspect
the exact assets before selecting validators. Distinguish syntax from host
convergence, actual deployment/readiness and rollback. Do not equate published
images or queued ledger rows with a completed release or ready database. Code
changes alone do not authorize live infrastructure, shared migrations or secrets.

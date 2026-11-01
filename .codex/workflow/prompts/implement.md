# Implement a change

## Small fix

```text
Fix <specific behavior> in <component>. Follow AGENTS.md. Inspect the working
tree, current implementation, and affected callers. Preserve unrelated work.
Make the bounded change, run focused checks, and report actual results and limits.
If the work changes a cross-component contract, clarify scope and dependencies
first. Create a task record only if I request one.
```

## Agreed substantial task

```text
Use $platform-change to implement the authorized scope in
.codex/workflow/tasks/<task-name>.md.
Follow AGENTS.md and .codex/workflow/README.md. Inspect the working tree and
reconcile the task record with current code before editing. Preserve unrelated
changes and the task's resource and secret safeguards.

Use coder for a bounded implementation
area with explicit file ownership and acceptance criteria. Sequence contract
changes before dependent edits. Parallelize only independent, non-overlapping
work. The coordinating agent integrates the changes and verifies the full flow.

For substantial changes, request an independent read-only review of the actual
diff using reviewer. Address confirmed findings and recheck affected behavior.
If no separate agent ran, label the work and review accurately.

Update the task with actual commands/results, agent activity, decisions,
remaining limits, and the next action. Do not provision live resources, deploy,
change production secrets, stage, or commit unless the requested scope includes it.
```

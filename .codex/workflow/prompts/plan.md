# Plan a substantial change

Replace the placeholders and send this prompt to Codex.

```text
Use $platform-change to investigate and plan <desired developer outcome>.
Create or update the task record I request at
.codex/workflow/tasks/<task-name>.md.

Follow AGENTS.md and .codex/workflow/README.md. Inspect the current branch,
HEAD, staged/unstaged changes, and relevant implementation. Read the task record
or create it from the template if absent. Preserve unrelated work.

Ask the investigator agent to trace <relevant paths> read-only when separate
investigation will clarify the work. Require facts, file references, assumptions,
failure paths, and open questions. If no agent runs, investigate directly and
record that accurately.

Define observable acceptance criteria, safeguards, contracts, dependencies,
file ownership, and an ordered plan. Record decisions that need user input.
Update only the task record. Do not implement, provision resources, deploy,
change secrets, or treat this plan as implementation authorization.
```

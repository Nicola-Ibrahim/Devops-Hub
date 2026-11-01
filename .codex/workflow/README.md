# Codex workflow for DevOps Hub

[Shared guidance](../../AGENTS.md) · [Task template](templates/task.md)

Start with the [prompt library](prompts/README.md). The reusable procedure lives in the [platform-change skill](../../.agents/skills/platform-change/SKILL.md). Create task records only when the user requests them; otherwise keep scope, decisions and progress in the conversation. This folder does not run automatically.

## Roles and sequence

1. The coordinating agent checks the working tree, defines the requested outcome, and owns the task record and integration.
2. `investigator` traces existing behavior read-only when the change crosses components or has uncertain contracts.
3. The coordinating agent resolves the cross-component contract and records acceptance criteria before implementation.
4. `coder` implements a bounded area after the scope is authorized. Assign file ownership and expected checks. Parallelize only independent work with separate files.
5. `reviewer` independently checks the actual diff against acceptance criteria when the change is substantial.
6. The coordinating agent addresses findings, verifies the full flow, and records actual results and limits.

[Coder](../agents/coder.toml) uses `gpt-6-luna`, medium reasoning and low verbosity. [Investigator](../agents/investigator.toml) and [reviewer](../agents/reviewer.toml) inherit parent model settings. Report unavailable model configurations rather than silently substituting. All agents inherit parent tools and permissions. These definitions configure future agents; they do not start agents or prove a review occurred.

## Task records

When the user requests a record, create `.codex/workflow/tasks/<descriptive-name>.md` from [the template](templates/task.md). Keep requirements, decisions, verification and handoff together. See [task record guidance](tasks/README.md). Planning stops after the plan; implementation requires authorized scope. Record actual agent activity and checks. Never put credentials in task records.

Keep shared schemas, resource states and provider contracts with the coordinator before assigning bounded implementation work to coder.

## Handoff and evidence

Give a spawned agent the objective, named task file, owned paths, baseline, acceptance criteria, safeguards, and expected output. The agent must check the current files rather than assuming the task record is current. The coordinator checks the agent's actual changes and verification. Record the runtime agent identity and reviewed diff when available. If no separate reviewer ran, call it a self-review. The read-only roles have behavioral constraints; parent session permissions still apply.

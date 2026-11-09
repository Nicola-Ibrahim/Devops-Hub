# Codex workflow for DevOps Hub

[Shared guidance](../../AGENTS.md) · [Task template](templates/task.md)

Start with the [prompt library](prompts/README.md). Substantial cross-component work uses [system-design](../../.agents/skills/system-design/SKILL.md). Create task records only when the user requests them; otherwise keep scope, decisions and progress in the conversation. This folder does not run automatically.

## Where guidance lives

| Location | Responsibility |
| --- | --- |
| `AGENTS.md`; `backend/`, `frontend/` and `infra/AGENTS.md` | Shared and directory-specific rules |
| `.agents/skills/` | Focused reusable procedures, loaded only as needed |
| `.codex/agents/` | Investigator, coder and reviewer role definitions |
| `.codex/workflow/prompts/` | Human-directed plan, implement and resume prompts |
| `.codex/workflow/tasks/` | User-requested requirements, decisions and evidence |

System-design owns substantial phase, scope, cross-component boundaries and handoff.
Backend-development owns DDD, workers, resource safety and isolated backend checks;
api-development owns HTTP; frontend-development owns Next.js UI and its checks;
delivery-engineering owns Docker, CI/CD and hosting delivery.
See the skill links in [AGENTS.md](../../AGENTS.md).
No skill automatically starts another task or grants permission for external effects.

## Roles and sequence

Use the roles where separate work adds value; this is not a mandatory agent pipeline
for every task. Keep the three existing roles rather than duplicating them per stack.


1. The coordinating agent checks the working tree, defines the requested outcome, and owns the task record and integration.
2. `investigator` traces existing behavior read-only when the change crosses components or has uncertain contracts.
3. The coordinating agent resolves the cross-component contract and records acceptance criteria before implementation.
4. `coder` implements a bounded area after the scope is authorized. Assign file ownership and expected checks. Parallelize only independent work with separate files.
5. `reviewer` independently checks the actual diff against acceptance criteria when the change is substantial.
6. The coordinating agent addresses findings, verifies the full flow, and records actual results and limits.

| Role | Default model | Reasoning | Use |
| --- | --- | --- | --- |
| [Coder](../agents/coder.toml) | `gpt-6-luna` | medium | Focused backend and Next.js implementation within agreed contracts |
| [Investigator](../agents/investigator.toml) | `gpt-6-luna` | low | Bounded read-only tracing and evidence gathering |
| [Reviewer](../agents/reviewer.toml) | `gpt-6-luna` | medium | Independent review of the assigned diff and affected callers |

All roles use low verbosity. These are starting choices, not measured guarantees
of cost or quality. Keep the three roles; frontend/backend are scoped assignments
to coder rather than duplicate actors. For frontend design use
[frontend-development](../../.agents/skills/frontend-development/SKILL.md).
Use Terra for visual inspection or dashboard design when the assigned work needs it.
The coordinator owns ambiguous contracts and security/lifecycle decisions; request
a Sol review only when a concrete finding needs deeper analysis. Raise reasoning
only for a specific unresolved problem. Role files configure future agents but
the running agent system may impose its own model; report the actual runtime model
when exposed. All agents inherit parent tools and permissions.

## Context reuse and cost

- Keep stable role instructions and repository guidance stable. Put changing task
  details, owned paths and acceptance criteria in the assignment. Avoid copying
  the entire conversation or unrelated files into each agent.
- Reuse the same agent thread for related follow-ups. Give new agents a compact,
  self-contained brief and relevant evidence instead of full history when feasible.
- Reuse investigation results and passing checks while their code and assumptions
  remain valid. Review changed files and affected callers before expanding scope.
- Parallelize independent work only. Avoid agents repeating the same investigation,
  repeated polling, full logs in handoffs, and mandatory delegation for small edits.
- Exact reusable prompt prefixes can support caching; caches do not transfer
  between different models. Sharing a model alone does not guarantee cache hits.
  Codex controls request construction and cache retention: do not invent cache
  settings in these role files or claim savings without usage evidence. If usage
  data exposes cached input tokens and total usage, compare cost per completed task,
  including retries. API pricing is not a promise about subscription allowance.

Source: [model selection](https://developers.openai.com/api/docs/guides/model-selection)
and [prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching).

## Task records

When the user requests a record, create `.codex/workflow/tasks/<descriptive-name>.md` from [the template](templates/task.md). Keep requirements, decisions, verification and handoff together. See [task record guidance](tasks/README.md). Planning stops after the plan; implementation requires authorized scope. Record actual agent activity and checks. Never put credentials in task records.

Keep shared schemas, resource states and provider contracts with the coordinator before assigning bounded implementation work to coder.

## Handoff and evidence

Give a spawned agent the objective, named task file, owned paths, baseline, acceptance criteria, safeguards, and expected output. The agent must check the current files rather than assuming the task record is current. The coordinator checks the agent's actual changes and verification. Record the runtime agent identity and reviewed diff when available. If no separate reviewer ran, call it a self-review. The read-only roles have behavioral constraints; parent session permissions still apply.

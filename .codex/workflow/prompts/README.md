# Codex prompts

These are copy-and-edit entry points. Each prompt tells Codex to select the
smallest matching skill set from the table below; you provide the outcome,
component and optional task name. Cross-component work also uses `$system-design`.
Name a task record when you want one created or continued; otherwise keep progress
in the conversation.

| Component | Relevant skill |
| --- | --- |
| Domain, application, persistence, workers and resource providers | `$backend-development` |
| FastAPI routes and HTTP contracts | `$api-development` |
| Next.js dashboard | `$frontend-development` |
| Docker, CI/CD, Ansible, Terraform and release operations | `$delivery-engineering` |

| Need | Prompt |
| --- | --- |
| Investigate and agree a substantial feature | [Plan](plan.md) |
| Implement an agreed task or a small fix | [Implement](implement.md) |
| Continue a recorded task | [Resume](resume.md) |

Create task records only when requested. Planning records may be edited during planning; application and infrastructure changes require implementation scope. Coder owns bounded implementation; investigator and reviewer remain read-only. The coordinator owns shared contracts and final verification.

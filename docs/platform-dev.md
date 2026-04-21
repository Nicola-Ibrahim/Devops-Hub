# Platform-Dev Technical Reference

The **`platform-dev`** package is a specialized Python orchestration engine designed to manage local developer environments with high reliability and structured output.

---

## ⚙️ Core Engine Architecture

### `TaskGroup` (Context Manager)
The `TaskGroup` manages a collection of atomic tasks. It provides:
- **Ambient Context**: Tasks defined within a `with TaskGroup(...)` block automatically register themselves.
- **Transactional Logic**: Can be configured to `abort_on_failure` (stop immediately) or run all tasks and report an aggregate result.
- **Structured Logging**: Automatically handles headers, indentation, and success/error styling.

### `Task` (Atomic Unit of Work)
The `Task` class encapsulates a single shell command.
- **Execution Guards**: Use `required_tools=["toolname"]` to prevent execution if a dependency (like `docker` or `uv`) is missing.
- **Interaction Modes**: Supports `interactive=True` (for TTY login flows) and `stream=True` (for live-streaming container logs).
- **Confirmation**: Can force a user prompt before execution (`confirm=True`).

---

## 📂 Modular Task Library

Tasks are organized by domain in `scripts/dev/platform_dev/tasks/`:

| Module | Responsibility |
| :--- | :--- |
| `setup.py` | Auditing and installing system-level tools (`uv`, `doppler`). |
| `env_secrets.py` | Syncing with Doppler and managing `.env` files. |
| `infrastructure.py` | Docker Compose orchestration and service health checks. |
| `workspace.py` | Cleanup of caches, git status summaries, and disk audits. |

---

## 🛠 Extending the Toolbox

To add a new automation step to the TOB ecosystem:

### 1. Define the Task
Add your function to `workspace.py` (or a relevant module):
```python
def seed_database():
    with TaskGroup("Database Seeding") as group:
        Task(
            cmd="uv run scripts/seed.py",
            description="Seeding the local dev database",
            required_tools=["uv"]
        )
```

### 2. Register the Task
Hook it into either `bootstrap.py` (one-time setup) or `dev.py` (daily use):
```python
# In dev.py (handle_up)
def handle_up(skip_confirm: bool = False):
    # ... other sync steps ...
    seed_database()  # Run your new task
```

---

## 🔍 Debugging & Troubleshooting

### Interpreting Logs
- **➤ Cyan**: A step is currently executing.
- **✔ Green**: Step completed successfully.
- **✖ Red**: Step failed. Raw error output will often be printed directly below.
- **ℹ Cyan (Dim)**: Instructional info or skipped steps.

### Common Issues
- **Missing Binary**: If a task fails with "Missing required tools", run `tob-bootstrap` to ensure your system path is correct.
- **Docker Connection**: If infrastructure tasks fail, ensure Docker Desktop is running and your current user has permission to access the socket.

from platform_dev.engine.core import Task, TaskGroup


def sync_platform_workspace() -> bool:
    """Synchronize dependencies directly."""
    with TaskGroup("Workspace Synchronization"):
        # Python dependencies
        uv_task = Task(
            cmd="uv sync",
            description="Syncing Python dependencies (uv)",
            stream=True,
        )
        return uv_task.success


def cleanup_platform_workspace(skip_confirm: bool = False) -> bool:
    """Clean caches and temporary files."""
    with TaskGroup("Workspace Cleanup"):
        task = Task(
            cmd="rm -rf .pytest_cache .ruff_cache __pycache__",
            description="Cleaning Python caches",
            confirm=True,
            skip_confirm=skip_confirm,
        )
        return task.success

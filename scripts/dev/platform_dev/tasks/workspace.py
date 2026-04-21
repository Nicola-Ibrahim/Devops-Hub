from platform_dev.engine.system import get_root_dir
from platform_dev.engine.task_group import Task, TaskGroup


def sync_dependencies(skip_confirm: bool = False) -> bool:
    """Ensure that local packages are up to date with the latest changes."""
    with TaskGroup(
        "Dependency Synchronization",
        info="Ensuring that local packages are up to date with the latest changes.",
    ):
        Task(
            cmd="uv sync",
            description="Updating backend dependencies (uv)",
            confirm=True,
            skip_confirm=skip_confirm,
            required_tools=["uv"],
        )
        return True


def cleanup_caches(skip_confirm: bool = False) -> None:
    """Remove temporary runtime artifacts and Python caches."""
    with TaskGroup(
        "Cache Cleanup",
        info="Removing temporary runtime artifacts and Python caches.",
    ):
        cleanup_cmd = (
            r'find . -type d \( -name "__pycache__" '
            r'-o -name ".pytest_cache" -o -name ".ruff_cache" \) '
            r"-exec rm -rf {} + 2>/dev/null || true"
        )
        Task(
            cmd=cleanup_cmd,
            description="Clearing Python & Linter caches",
            confirm=True,
            skip_confirm=skip_confirm,
            required_tools=["find"],
        )


def audit_storage(skip_confirm: bool = False) -> None:
    """Report on the disk space used by AI datasets and artifacts."""
    storage_paths = []
    root = get_root_dir()
    if (root / "storage").exists():
        storage_paths.append("storage")
    if (root / "data").exists():
        storage_paths.append("data")

    if not storage_paths:
        return

    with TaskGroup(
        "Storage Audit",
    ) as group:
        group.logger.info("Calculating disk space used by AI datasets and artifacts.")
        audit_cmd = f"du -sh {' '.join(storage_paths)}"
        Task(
            cmd=audit_cmd,
            description="Auditing local storage size",
            confirm=True,
            skip_confirm=skip_confirm,
            required_tools=["du"],
        )


def cleanup_storage(skip_confirm: bool = False) -> None:
    """Wipe temporary data folders to free up space (requires confirmation)."""
    with TaskGroup(
        "Storage Purge",
        info="Wiping temporary data folders to free up space.",
    ):
        Task(
            cmd="rm -rf storage/* data/tmp/*",
            description="Purging temporary storage files",
            confirm=True,
            skip_confirm=skip_confirm,
        )


def summarize_work(skip_confirm: bool = False) -> None:
    """Display a high-level summary of workspace changes (via git)."""
    with TaskGroup(
        "Workspace Summary",
        info="Displaying a high-level summary of workspace changes.",
    ) as group:
        # Standard summary using git status
        task = Task(
            cmd="git status -s",
            description="Retrieving git status summary",
            skip_confirm=skip_confirm,
            required_tools=["git"],
        )

        if task.success:
            group.logger.info("The above files are currently modified or untracked.")
        else:
            group.logger.warning(
                "Could not retrieve git status. Is it a git repository?"
            )

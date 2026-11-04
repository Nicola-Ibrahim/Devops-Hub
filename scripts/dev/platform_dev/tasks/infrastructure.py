from platform_dev.engine.core import Task, TaskGroup


def boot_platform_infrastructure() -> bool:
    """Launch the local platform with its private synthetic development secrets."""
    with TaskGroup("Infrastructure Boot"):
        task = Task(
            cmd="scripts/ops/compose-up.sh",
            description="Creating local-only configuration and starting Compose services",
            stream=True,
        )
        return task.success


def shutdown_platform_services(skip_confirm: bool = False) -> bool:
    """Gracefully stop all Docker services."""
    with TaskGroup("Infrastructure Shutdown"):
        task = Task(
            cmd="docker compose --profile app down",
            description="Stopping Compose services while preserving named data volumes",
            stream=True,
            confirm=True,
            skip_confirm=skip_confirm,
        )
        return task.success

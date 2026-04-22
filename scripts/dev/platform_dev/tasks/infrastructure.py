from platform_dev.engine.core import Task, TaskGroup


def boot_platform_infrastructure() -> bool:
    """Launch all containers via direct Docker Compose call."""
    with TaskGroup("Infrastructure Boot"):
        task = Task(
            cmd="doppler run -- docker compose up -d --build",
            description="Executing Docker Compose (UP)",
            stream=True,
        )
        return task.success


def shutdown_platform_services(skip_confirm: bool = False) -> bool:
    """Gracefully stop all Docker services."""
    with TaskGroup("Infrastructure Shutdown"):
        task = Task(
            cmd="docker compose down",
            description="Executing Docker Compose (DOWN)",
            stream=True,
            confirm=True,
            skip_confirm=skip_confirm,
        )
        return task.success

from platform_dev.engine.system import is_tool_installed
from platform_dev.engine.task_group import Task, TaskGroup


def _is_docker_daemon_running() -> bool:
    """Verify if the Docker daemon is reachable."""
    try:
        # 'docker info' returns 0 if daemon is running
        import subprocess

        result = subprocess.run(
            ["docker", "info"], capture_output=True, text=True, check=False
        )
        return result.returncode == 0
    except Exception:
        return False


def boot_infrastructure(skip_confirm: bool = False) -> bool:
    """Launch all background services and application containers."""
    with TaskGroup(
        "Infrastructure & App Services",
        info="Launching all background services and application containers.",
    ) as group:
        if not _is_docker_daemon_running():
            group.logger.error(
                "Docker daemon is not running. Please start Docker Desktop."
            )
            return False

        # Launching everything defined in docker-compose.yml
        base_cmd = "docker compose up -d --build"
        if is_tool_installed("doppler"):
            cmd = f"doppler run -- {base_cmd}"
        else:
            cmd = base_cmd
            group.logger.warning("Doppler not found. Using local environment only.")

        Task(
            cmd=cmd,
            description="Booting all Docker containers",
            stream=True,
            skip_confirm=skip_confirm,
            required_tools=["docker"],
        )
        return True


def shutdown_services(skip_confirm: bool = False) -> bool:
    """Gracefully stop all Docker services."""
    with TaskGroup(
        "Docker Shutdown",
        info="Gracefully stopping all Docker services.",
    ):
        if not _is_docker_daemon_running():
            return True

        Task(
            cmd="docker compose down",
            description="Stopping all Docker containers",
            confirm=True,
            skip_confirm=skip_confirm,
            required_tools=["docker"],
        )
        return True


def reset_infrastructure(skip_confirm: bool = False) -> bool:
    """Ensure all background infrastructure is in a clean state (e.g., Redis)."""
    with TaskGroup(
        "Infrastructure Reset",
        info="Ensuring all background infrastructure is in a clean state.",
    ) as group:
        if not _is_docker_daemon_running():
            group.logger.warning(
                "Docker is not available. Skipping infrastructure reset."
            )
            return True

        try:
            # Try via docker-compose first
            Task(
                cmd="docker compose exec -T redis redis-cli flushall",
                description="Flushing Redis cache (Docker)",
                confirm=True,
                exit_on_error=False,
                skip_confirm=skip_confirm,
                required_tools=["docker"],
            )
            return True
        except Exception:
            group.logger.warning("Could not flush Redis. It might not be running.")
            return True

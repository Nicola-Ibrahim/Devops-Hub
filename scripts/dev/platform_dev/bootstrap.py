import sys

from platform_dev.engine.task_group import TaskGroup
from platform_dev.engine.ui import Logger
from platform_dev.tasks.env_secrets import sync_secrets
from platform_dev.tasks.infrastructure import boot_infrastructure
from platform_dev.tasks.setup import check_core_tools, install_missing_tools
from platform_dev.tasks.workspace import sync_dependencies


def run_bootstrap() -> None:
    """
    Main orchestration logic to prepare the local development environment.
    """
    with TaskGroup(
        "Environment Bootstrap",
        info="Ensuring all core developer tools are installed and configured.",
    ) as group:
        # 1. Tool Audit
        missing = check_core_tools()

        # 2. Tool Installation (if needed)
        if missing:
            if not install_missing_tools(missing):
                group.logger.error("Stop: Required tools could not be installed.")
                sys.exit(1)

        # 3. Identity & Secrets
        if not sync_secrets(skip_confirm=True):
            group.logger.error("Stop: Identity sync failed.")
            sys.exit(1)

        # 4. Background Infrastructure
        if not boot_infrastructure(skip_confirm=True):
            group.logger.error("Stop: Infrastructure failed to boot.")
            sys.exit(1)

        # 5. Dependency Management
        if not sync_dependencies(skip_confirm=True):
            group.logger.error("Stop: Dependency synchronization failed.")
            sys.exit(1)

        group.logger.success("Bootstrap complete! You are ready to develop.")


if __name__ == "__main__":
    try:
        run_bootstrap()
    except KeyboardInterrupt:
        Logger().info_step("\nBootstrap aborted by user.")
        sys.exit(0)
    except Exception as e:
        Logger().error(f"Bootstrap failed: {str(e)}")
        sys.exit(1)

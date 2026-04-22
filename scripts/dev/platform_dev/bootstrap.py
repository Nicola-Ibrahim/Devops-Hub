import sys

from platform_dev.engine.task_group import TaskGroup
from platform_dev.engine.ui import Logger
from platform_dev.tasks.env_secrets import setup_identity, sync_platform_secrets
from platform_dev.tasks.infrastructure import boot_platform_infrastructure
from platform_dev.tasks.setup import run_platform_setup
from platform_dev.tasks.workspace import sync_platform_workspace


def run_bootstrap() -> None:
    """
    Main orchestration logic to prepare the local development environment
    using Ansible for idempotent state management.
    """
    with TaskGroup(
        "Platform Bootstrap",
        info="Standardizing local development environment (Ansible-driven).",
    ) as group:
        # 1. Platform Setup (Idempotent tool installation)
        if not run_platform_setup():
            group.logger.error("Stop: Platform setup failed.")
            sys.exit(1)

        # 2. Identity (Interactive login if needed)
        if not setup_identity(skip_confirm=True):
            group.logger.error("Stop: Identity authentication failed.")
            sys.exit(1)

        # 3. Sync Secrets
        if not sync_platform_secrets():
            group.logger.error("Stop: Secret synchronization failed.")
            sys.exit(1)

        # 4. Boot Infrastructure
        if not boot_platform_infrastructure():
            group.logger.error("Stop: Infrastructure failed to boot.")
            sys.exit(1)

        # 5. Sync Workspace
        if not sync_platform_workspace():
            group.logger.error("Stop: Workspace synchronization failed.")
            sys.exit(1)

        group.logger.success("Bootstrap complete! Your environment is ready via Ansible.")


if __name__ == "__main__":
    try:
        run_bootstrap()
    except KeyboardInterrupt:
        Logger().info_step("\nBootstrap aborted by user.")
        sys.exit(0)
    except Exception as e:
        Logger().error(f"Bootstrap failed: {str(e)}")
        sys.exit(1)

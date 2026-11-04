import sys

from platform_dev.engine.core import TaskGroup
from platform_dev.engine.ui import Logger
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

        # 2. Sync Workspace before starting the local platform.
        if not sync_platform_workspace():
            group.logger.error("Stop: Workspace synchronization failed.")
            sys.exit(1)

        # 3. Boot Infrastructure. The demo uses generated local-only secrets.
        if not boot_platform_infrastructure():
            group.logger.error("Stop: Infrastructure failed to boot.")
            sys.exit(1)

        group.logger.success(
            "Bootstrap complete! Your environment is ready via Ansible."
        )


if __name__ == "__main__":
    try:
        run_bootstrap()
    except KeyboardInterrupt:
        Logger().info_step("\nBootstrap aborted by user.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - CLI boundary must report all failed setup steps.
        Logger().error(f"Bootstrap failed: {exc!s}")
        sys.exit(1)

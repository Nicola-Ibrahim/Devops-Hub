import argparse
import sys

from platform_dev.engine.ui import Logger
from platform_dev.tasks.infrastructure import (
    boot_platform_infrastructure,
    shutdown_platform_services,
)
from platform_dev.tasks.setup import run_platform_setup
from platform_dev.tasks.workspace import sync_platform_workspace


def handle_up(skip_confirm: bool = False) -> bool:
    """Full environment synchronization and startup via Ansible."""
    logger = Logger()
    logger.header("Development Workspace: UP (Ansible)")

    # 1. Install/configure local tools. Doppler is not required by the local demo.
    if not run_platform_setup():
        return False

    # 2. Sync pinned backend dependencies before startup.
    if not sync_platform_workspace():
        return False

    # 3. Boot Infrastructure
    if not boot_platform_infrastructure():
        return False

    logger.header("Workspace Ready")
    logger.success("All containers are running and environment is clean.")
    logger.info("\nEnjoy your coding session! ☕\n")
    return True


def handle_down(skip_confirm: bool = False) -> bool:
    """Gracefully stop services without deleting database or resource data."""
    logger = Logger()
    logger.header("Development Workspace: DOWN (Ansible)")

    if not shutdown_platform_services(skip_confirm=skip_confirm):
        logger.error("Service shutdown failed; workspace is left intact.")
        return False

    logger.header("Shutdown Complete")
    logger.success("All background services have been terminated via Ansible.")
    logger.info("\nSee you tomorrow! 🌙\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Unified Platform Manager (Ansible-Driven)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tob-dev up      # Start the environment
  tob-dev down    # Stop and clean up
        """,
    )

    parser.add_argument(
        "action",
        choices=["up", "down"],
        help="Action to perform: 'up' to start, 'down' to stop.",
    )

    parser.add_argument(
        "-y", "--yes", action="store_true", help="Skip all confirmation prompts."
    )

    args = parser.parse_args()

    try:
        if args.action == "up":
            succeeded = handle_up(skip_confirm=args.yes)
        elif args.action == "down":
            succeeded = handle_down(skip_confirm=args.yes)
        if not succeeded:
            sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001 - CLI boundary must return a failing process status.
        Logger().error(f"Execution failed: {exc!s}")
        sys.exit(1)


if __name__ == "__main__":
    main()

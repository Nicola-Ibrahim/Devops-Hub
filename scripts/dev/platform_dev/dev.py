import argparse
import sys

from platform_dev.engine.ui import Logger
from platform_dev.tasks.env_secrets import sync_platform_secrets
from platform_dev.tasks.infrastructure import (
    boot_platform_infrastructure,
    shutdown_platform_services,
)
from platform_dev.tasks.workspace import (
    cleanup_platform_workspace,
    sync_platform_workspace,
)


def handle_up(skip_confirm: bool = False) -> bool:
    """Full environment synchronization and startup via Ansible."""
    logger = Logger()
    logger.header("Development Workspace: UP (Ansible)")

    # 1. Sync Secrets
    if not sync_platform_secrets():
        return False

    # 2. Sync Workspace (Dependencies + Pre-flight)
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
    """Graceful shutdown and session cleanup via Ansible."""
    logger = Logger()
    logger.header("Development Workspace: DOWN (Ansible)")

    # 1. Shutdown Services
    shutdown_platform_services(skip_confirm=skip_confirm)

    # 2. Cleanup Workspace
    cleanup_platform_workspace(skip_confirm=skip_confirm)

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
            handle_up(skip_confirm=args.yes)
        elif args.action == "down":
            handle_down(skip_confirm=args.yes)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        Logger().error(f"Execution failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()

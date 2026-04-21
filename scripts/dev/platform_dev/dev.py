import argparse

from platform_dev.engine.ui import Logger
from platform_dev.tasks.env_secrets import sync_secrets
from platform_dev.tasks.infrastructure import (
    boot_infrastructure,
    reset_infrastructure,
    shutdown_services,
)
from platform_dev.tasks.workspace import (
    audit_storage,
    cleanup_caches,
    cleanup_storage,
    summarize_work,
    sync_dependencies,
)


def handle_up(skip_confirm: bool = False) -> bool:
    """Full environment synchronization and startup."""
    logger = Logger()
    logger.header("Development Workspace: UP")

    # 1. Sync Secrets
    if not sync_secrets(skip_confirm=skip_confirm):
        return False

    # 2. Sync Dependencies
    if not sync_dependencies(skip_confirm=skip_confirm):
        return False

    # 3. Boot Infrastructure
    if not boot_infrastructure(skip_confirm=skip_confirm):
        return False

    # 4. Infrastructure Reset (Flush Redis)
    reset_infrastructure(skip_confirm=skip_confirm)

    # 5. Storage Cleanup
    cleanup_storage(skip_confirm=skip_confirm)

    logger.header("Workspace Ready")
    logger.success("All containers are running and environment is clean.")
    logger.info("\nEnjoy your coding session! ☕\n")
    return True


def handle_down(skip_confirm: bool = False) -> bool:
    """Graceful shutdown and session cleanup."""
    logger = Logger()
    logger.header("Development Workspace: DOWN")

    # 1. Shutdown Services (Confirm if not -y)
    shutdown_services(skip_confirm=skip_confirm)

    # 2. Cleanup Caches
    cleanup_caches(skip_confirm=skip_confirm)

    # 3. Audit Storage
    audit_storage(skip_confirm=skip_confirm)

    # 4. Summarize Work
    summarize_work(skip_confirm=skip_confirm)

    logger.header("Shutdown Complete")
    logger.success("All background services have been terminated (where possible).")
    logger.info("\nSee you tomorrow! 🌙\n")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Unified Development Environment Manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  tob-dev up      # Start the environment
  tob-dev down    # Stop and clean up
  tob-dev up -y   # Start without confirmation prompts
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

    if args.action == "up":
        handle_up(skip_confirm=args.yes)
    elif args.action == "down":
        handle_down(skip_confirm=args.yes)


if __name__ == "__main__":
    main()

from platform_dev.engine.task_group import Task, TaskGroup


def setup_identity(skip_confirm: bool = False) -> bool:
    """Handle authentication with platform services (Doppler)."""
    with TaskGroup("Identity & Secrets") as group:
        auth_check = Task(
            cmd="doppler me", required_tools=["doppler"], exit_on_error=False
        )

        if auth_check.success:
            group.logger.success("Already authenticated with Doppler.")
            return True

        group.logger.info("Launching Doppler interactive login flow.")
        task = Task(
            cmd="doppler login",
            description="Logging into Doppler CLI",
            interactive=True,
            skip_confirm=skip_confirm,
            required_tools=["doppler"],
        )

        return task.success


def sync_secrets(skip_confirm: bool = False) -> bool:
    """Synchronize local secrets with the latest values from Doppler."""
    with TaskGroup(
        "Secret Management",
        info="Pulling latest environment variables (.env) from Doppler.",
    ) as group:
        # Diagnostic check using Task (silent mode - no description)
        login_check = Task(
            cmd="doppler me", required_tools=["doppler"], exit_on_error=False
        )

        if not login_check.success:
            # Check if failure was due to missing binary or just not logged in
            # If missing binary, Task guard already logged the error
            missing_binary = any(
                isinstance(r, Task) and "doppler" in r.required_tools and not r.success
                for r in group.results
            )

            if not missing_binary:
                # Not logged in, attempt setup
                if not setup_identity(skip_confirm=skip_confirm):
                    return False
            else:
                return False

        task = Task(
            cmd="doppler secrets download --format env --no-file > .env",
            description="Downloading .env file (Doppler)",
            skip_confirm=skip_confirm,
            required_tools=["doppler"],
        )
        return task.success

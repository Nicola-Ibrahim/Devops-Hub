from platform_dev.engine.core import Task, TaskGroup


def setup_identity(skip_confirm: bool = False) -> bool:
    """Handle authentication with platform services (Doppler)."""
    with TaskGroup("Identity Authentication"):
        # Check if already logged in
        auth_check = Task(cmd="doppler me")
        if auth_check.success:
            return True

        # Interactive login required
        task = Task(
            cmd="doppler login",
            description="Logging into Doppler CLI",
            interactive=True,
            skip_confirm=skip_confirm,
        )
        return task.success

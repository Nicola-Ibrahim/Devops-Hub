from platform_dev.engine.system import get_ansible_cmd
from platform_dev.engine.task_group import Task, TaskGroup


def setup_identity(skip_confirm: bool = False) -> bool:
    """Handle authentication with platform services (Doppler)."""
    with TaskGroup("Identity Authentication") as group:
        # Check if already logged in
        auth_check = Task(cmd="doppler me", exit_on_error=False)
        if auth_check.success:
            group.logger.success("Already authenticated with Doppler.")
            return True

        # Interactive login required
        task = Task(
            cmd="doppler login",
            description="Logging into Doppler CLI",
            interactive=True,
            skip_confirm=skip_confirm,
            required_tools=["doppler"],
        )
        return task.success


def sync_platform_secrets() -> bool:
    """Synchronize local secrets with Doppler via Ansible."""
    with TaskGroup("Secret Synchronization"):
        task = Task(
            cmd=get_ansible_cmd(tags=["secrets"]),
            description="Downloading .env file (Ansible/Doppler)",
            stream=True,
            required_tools=["ansible-playbook"],
        )
        return task.success

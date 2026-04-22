from platform_dev.engine.system import get_ansible_cmd
from platform_dev.engine.task_group import Task, TaskGroup


def sync_platform_workspace() -> bool:
    """Synchronize dependencies and clean workspace via Ansible."""
    with TaskGroup("Workspace Synchronization"):
        task = Task(
            cmd=get_ansible_cmd(tags=["up", "workspace"]),
            description="Syncing dependencies and prepping workspace",
            stream=True,
            required_tools=["ansible-playbook"],
        )
        return task.success


def cleanup_platform_workspace(skip_confirm: bool = False) -> bool:
    """Clean caches and temporary files via Ansible."""
    with TaskGroup("Workspace Cleanup"):
        task = Task(
            cmd=get_ansible_cmd(tags=["down", "workspace"]),
            description="Executing cache cleanup (Ansible)",
            stream=True,
            confirm=True,
            skip_confirm=skip_confirm,
            required_tools=["ansible-playbook"],
        )
        return task.success

from platform_dev.engine.system import get_ansible_cmd
from platform_dev.engine.task_group import Task, TaskGroup


def boot_platform_infrastructure() -> bool:
    """Launch all containers via Ansible orchestration."""
    with TaskGroup("Infrastructure Boot"):
        task = Task(
            cmd=get_ansible_cmd(tags=["up", "infrastructure"]),
            description="Executing Docker Compose (UP)",
            stream=True,
            required_tools=["ansible-playbook"],
        )
        return task.success


def shutdown_platform_services(skip_confirm: bool = False) -> bool:
    """Gracefully stop all Docker services via Ansible."""
    with TaskGroup("Infrastructure Shutdown"):
        task = Task(
            cmd=get_ansible_cmd(tags=["down", "infrastructure"]),
            description="Executing Docker Compose (DOWN)",
            stream=True,
            confirm=True,
            skip_confirm=skip_confirm,
            required_tools=["ansible-playbook"],
        )
        return task.success

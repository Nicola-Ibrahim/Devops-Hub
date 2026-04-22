from platform_dev.engine.system import get_ansible_cmd
from platform_dev.engine.task_group import Task, TaskGroup


def run_platform_setup() -> bool:
    """
    Idempotent installation and configuration of core tools via Ansible.
    """
    with TaskGroup(
        "Platform Setup",
        info="Auditing and installing core developer tools (Ansible-driven).",
    ):
        task = Task(
            cmd=get_ansible_cmd(tags=["setup"]),
            description="Executing idempotent tool installation",
            stream=True,
            required_tools=["ansible-playbook"],
        )
        return task.success

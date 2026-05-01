from platform_dev.engine.core import Task, TaskGroup
from pathlib import Path


def get_ansible_cmd(tags: list[str] = None) -> str:
    """
    Constructs the ansible-playbook command.
    Prioritizes local project playbooks, falling back to DevOps internal ones.
    """
    project_root = Task.get_project_root()
    devops_root = Task.get_devops_root()

    # Potential playbook locations
    playbook_options = [
        project_root / "setup-local.yml",
        project_root / "infra" / "ansible" / "playbooks" / "bootstrap-local.yml",
        devops_root / "infra" / "ansible" / "playbooks" / "bootstrap-local.yml",
    ]

    # Potential inventory locations
    inventory_options = [
        project_root / "inventory" / "local.yml",
        project_root / "infra" / "ansible" / "inventory" / "local.yml",
        devops_root / "infra" / "ansible" / "inventory" / "local.yml",
    ]

    # Find first existing playbook
    playbook = next((p for p in playbook_options if p.exists()), playbook_options[-1])
    
    # Find first existing inventory
    inventory = next((i for i in inventory_options if i.exists()), inventory_options[-1])

    cmd = f"ansible-playbook -i {inventory} {playbook}"
    if tags:
        cmd += f" --tags {','.join(tags)}"
    return cmd


def run_platform_setup() -> bool:
    """
    Idempotent installation and configuration of core tools via Ansible.
    This handles everything (Tools, Secrets, Workspace Setup).
    """
    with TaskGroup(
        "Platform Setup",
        info="Auditing and installing core developer tools (Ansible-driven).",
    ):
        task = Task(
            cmd=get_ansible_cmd(),
            description="Executing full environment bootstrap",
            stream=True,
        )
        return task.success

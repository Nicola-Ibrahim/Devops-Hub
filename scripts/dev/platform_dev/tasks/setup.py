from platform_dev.engine.core import Task, TaskGroup


def get_ansible_cmd(tags: list[str] = None) -> str:
    """Constructs the ansible-playbook command for local bootstrap."""
    root = Task.get_root_dir()
    playbook = root / "infra" / "ansible" / "playbooks" / "bootstrap-local.yml"
    inventory = root / "infra" / "ansible" / "inventory" / "local.yml"

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
            cmd=get_ansible_cmd(),  # No tags = Run everything
            description="Executing full environment bootstrap",
            stream=True,
        )
        return task.success

import shlex

from platform_dev.engine.core import Task, TaskGroup


def get_ansible_cmd(tags: list[str] | None = None) -> str:
    """Build the repository-local Ansible command with its checked-in config."""
    project_root = Task.get_project_root()
    ansible_root = project_root / "infra" / "ansible"
    playbook = ansible_root / "playbooks" / "bootstrap-local.yml"
    inventory = ansible_root / "inventory" / "local.yml"
    config = ansible_root / "ansible.cfg"
    parts = [
        f"ANSIBLE_CONFIG={shlex.quote(str(config))}",
        "ansible-playbook",
        "-i",
        shlex.quote(str(inventory)),
        shlex.quote(str(playbook)),
    ]
    if tags:
        parts.extend(["--tags", shlex.quote(",".join(tags))])
    return " ".join(parts)


def run_platform_setup() -> bool:
    """Install pinned Ansible modules, then run the local idempotent setup."""
    with TaskGroup(
        "Platform Setup",
        info="Installing declared Ansible collections and configuring local tools.",
    ):
        ansible_root = Task.get_project_root() / "infra" / "ansible"
        requirements = ansible_root / "requirements.yml"
        collections = Task(
            cmd=" ".join(
                [
                    "ansible-galaxy collection install -r",
                    shlex.quote(str(requirements)),
                ]
            ),
            description="Installing pinned Ansible collections",
            stream=True,
        )
        if not collections.success:
            return False

        task = Task(
            cmd=get_ansible_cmd(),
            description="Executing local environment bootstrap",
            stream=True,
        )
        return task.success

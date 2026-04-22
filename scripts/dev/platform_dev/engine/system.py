import os
import shutil
from pathlib import Path


def get_root_dir():
    """
    Returns the absolute project root directory by searching for .git
    starting from the current working directory.
    """
    current_path = Path(os.getcwd()).absolute()

    # Climb up to find .git
    for parent in [current_path] + list(current_path.parents):
        if (parent / ".git").exists():
            return parent

    # Fallback to CWD if no .git found
    return current_path


def is_tool_installed(name):
    """Checks if a tool is available in the system PATH."""
    return shutil.which(name) is not None


def get_ansible_cmd(tags: list[str]) -> str:
    """Constructs the ansible-playbook command with specific tags."""
    root = get_root_dir()
    playbook = root / "infra" / "ansible" / "playbooks" / "local_dev.yml"
    inventory = root / "infra" / "ansible" / "inventory" / "local.yml"
    tag_str = ",".join(tags)

    return f"ansible-playbook -i {inventory} {playbook} --tags {tag_str}"

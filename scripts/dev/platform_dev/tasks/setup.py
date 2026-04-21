import platform
from typing import List

from platform_dev.engine.system import is_tool_installed
from platform_dev.engine.task_group import Task, TaskGroup


def check_core_tools() -> List[str]:
    """
    Verify if core developer tools (uv, doppler) are already available.
    Returns a list of missing tool names.
    """
    missing_tools: List[str] = []
    with TaskGroup(
        "Tool Audit",
        info="Checking for required developer tools (uv, doppler).",
    ) as group:
        tools_to_check = {
            "uv": "uv --version",
            "doppler": "doppler --version",
        }

        for tool in tools_to_check:
            if not is_tool_installed(tool):
                group.logger.warning(f"{tool} is NOT installed.")
                missing_tools.append(tool)
            else:
                group.logger.success(f"{tool} is available.")

        if not missing_tools:
            group.logger.success("All core tools are ready to go.")

        return missing_tools


def install_missing_tools(missing_tools: List[str]) -> None:
    """Orchestrate the installation of missing tools based on OS."""
    if not missing_tools:
        return

    os_type = platform.system()

    with TaskGroup(
        "Tool Installation",
        info=f"Orchestrating installation of: {', '.join(missing_tools)} ({os_type})",
    ) as group:
        if os_type == "Darwin":
            _install_mac(group, missing_tools)
        elif os_type == "Linux":
            _install_linux(group, missing_tools)
        elif os_type == "Windows":
            _install_windows(group, missing_tools)
        else:
            group.logger.error(f"Unsupported OS: {os_type}")


def _install_mac(group: TaskGroup, tools: List[str]) -> None:
    """Installation logic for macOS."""
    has_brew = is_tool_installed("brew")

    if "uv" in tools:
        if has_brew:
            Task(
                cmd="brew install uv",
                description="Installing uv (Homebrew)",
                required_tools=["brew"],
            )
        else:
            Task(
                cmd="curl -fsSL https://astral.sh/uv/install.sh | <EMAIL>",
                description="Installing uv (curl)",
                required_tools=["curl"],
            )

    if "doppler" in tools:
        if has_brew:
            Task(
                cmd="brew install dopplerhq/cli/doppler",
                description="Installing Doppler CLI (Homebrew)",
                required_tools=["brew"],
            )
        else:
            group.logger.header("Manual Setup Required")
            group.logger.info("Visit: https://docs.doppler.com/docs/install-cli")


def _install_linux(group: TaskGroup, tools: List[str]) -> None:
    """Installation logic for Linux."""
    if "uv" in tools:
        Task(
            cmd="curl -fsSL https://astral.sh/uv/install.sh | <EMAIL>",
            description="Installing uv (curl)",
            required_tools=["curl"],
        )
    if "doppler" in tools:
        group.logger.header("Manual Setup Required (Linux)")
        group.logger.info("Visit: https://docs.doppler.com/docs/install-cli")


def _install_windows(group: TaskGroup, tools: List[str]) -> None:
    """Installation logic for Windows."""
    has_winget = is_tool_installed("winget")

    if "uv" in tools:
        if has_winget:
            Task(
                cmd="winget install uv",
                description="Installing uv (winget)",
                required_tools=["winget"],
            )
        else:
            Task(
                cmd='powershell -ExecutionPolicy ByPass -c "'
                'irm https://astral.sh/uv/install.ps1 | iex"',
                description="Installing uv (PowerShell)",
            )

    if "doppler" in tools:
        if has_winget:
            Task(
                cmd="winget install doppler",
                description="Installing Doppler CLI (winget)",
                required_tools=["winget"],
            )
        else:
            group.logger.warning("Manual setup suggested for Doppler on Windows.")
            group.logger.info("Visit: https://docs.doppler.com/docs/install-cli")

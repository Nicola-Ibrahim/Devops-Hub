import os
import subprocess
import time
from pathlib import Path

from platform_dev.engine.ui import Logger


class Task:
    """Simplified task runner for executing shell commands."""

    def __init__(
        self,
        cmd: str,
        description: str = None,
        cwd: Path = None,
        stream: bool = False,
        interactive: bool = False,
        confirm: bool = False,
        skip_confirm: bool = False,
    ):
        self.cmd = cmd
        self.description = description
        self.cwd = cwd or self.get_project_root()
        self.logger = Logger()
        self.success = False

        if description:
            self.logger.info_step(description)

        if confirm and not skip_confirm:
            if not self.logger.confirm(f"Proceed with: {description or cmd}?"):
                self.logger.warning("Task skipped by user.")
                return

        try:
            if interactive:
                # Use subprocess.run for interactive commands to connect to tty
                res = subprocess.run(cmd, shell=True, cwd=self.cwd)
                self.success = res.returncode == 0
            elif stream:
                process = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=self.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                )
                for line in process.stdout:
                    if line.strip():
                        self.logger.output(line)
                process.wait()
                self.success = process.returncode == 0
            else:
                res = subprocess.run(
                    cmd, shell=True, cwd=self.cwd, capture_output=True, text=True
                )
                if res.stdout:
                    self.logger.output(res.stdout)
                if res.returncode != 0 and res.stderr:
                    self.logger.error_output(res.stderr)
                self.success = res.returncode == 0

            if description:
                if self.success:
                    self.logger.success(f"Finished: {description}")
                else:
                    self.logger.error(f"Failed: {description}")
        except Exception as e:
            self.logger.error(f"Exception: {e}")

    @staticmethod
    def get_project_root() -> Path:
        """
        Finds the project root.
        If in a git repo, returns the root.
        Otherwise returns current working directory.
        """
        path = Path(os.getcwd()).absolute()
        for p in [path] + list(path.parents):
            if (p / ".git").exists() or (p / "pyproject.toml").exists():
                return p
        return path

    @staticmethod
    def get_devops_root() -> Path:
        """
        Returns the absolute path to the DevOps repository structure.
        This is used to find internal Ansible roles/playbooks if local ones aren't found.
        """
        # This file is in platform_dev/engine/core.py
        # Root is 4 levels up from platform_dev/engine/core.py
        return Path(__file__).absolute().parents[4]


class TaskGroup:
    """Minimal context for grouping tasks with a header."""

    def __init__(self, title: str, info: str = None):
        self.title = title
        self.info = info
        self.logger = Logger()
        self._start = 0

    def __enter__(self):
        self._start = time.time()
        self.logger.header(self.title)
        if self.info:
            self.logger.info(self.info)
        return self

    def __exit__(self, *args):
        elapsed = time.time() - self._start
        self.logger.info_step(f"Finished {self.title} in {elapsed:.1f}s")

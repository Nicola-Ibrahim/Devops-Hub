import subprocess
import sys
import time
from pathlib import Path
from typing import Self

from platform_dev.engine.system import get_root_dir, is_tool_installed
from platform_dev.engine.ui import Logger

_UNSET = object()


class TaskGroupAborted(Exception):
    """Raised internally when abort_on_failure=True and a task fails."""

    pass


class Task:
    """
    Encapsulates a shell command as an action object.
    Executes immediately on instantiation.
    Auto-registers with the active TaskGroup if one exists.
    """

    def __init__(
        self,
        cmd: str,  # required — no silent no-ops
        description: str | None = None,
        cwd: str | Path | None = None,
        interactive: bool = False,
        stream: bool = False,
        confirm: bool = False,
        skip_confirm: bool | object = _UNSET,  # sentinel — detect explicit False
        exit_on_error: bool = False,
        required_tools: list[str] | None = None,
    ):
        self.cmd = cmd
        self.description = description
        self.cwd = cwd or get_root_dir()
        self.interactive = interactive
        self.stream = stream
        self.confirm = confirm
        self.exit_on_error = exit_on_error
        self.required_tools = required_tools or []
        self.success = False

        # Resolve ambient group and inherit its logger + skip_confirm
        group = TaskGroup._get_active()
        if not group:
            raise RuntimeError(
                f"Task({self.description or self.cmd!r}) must be defined "
                "within a TaskGroup context."
            )

        self.logger = group.logger

        # Explicit value always wins — group is only the fallback
        if skip_confirm is _UNSET:
            self.skip_confirm = group.skip_confirm if group else False
        else:
            self.skip_confirm = bool(skip_confirm)

        # Pre-flight Tool Validation (Execution Guard)
        if self.required_tools:
            missing = [t for t in self.required_tools if not is_tool_installed(t)]
            if missing:
                self.logger.error(
                    f"Missing required tools: {', '.join(missing)}. "
                    "This task cannot be executed."
                )
                self.success = False
                if group:
                    group.register_result(self)
                return

        # Execute and register — always, because cmd is required
        self.success = self._execute()
        if group:
            group.register_result(self)

    def _execute(self) -> bool:
        if self.description:
            if self.confirm and not self.skip_confirm:
                if not self.logger.confirm(f"Run step: {self.description}?"):
                    self.logger.info_step("Skipped by user.")
                    return False
            self.logger.step(self.description)

        try:
            if self.interactive:
                result = subprocess.run(self.cmd, shell=True, cwd=self.cwd)
                returncode = result.returncode

            elif self.stream:
                process = subprocess.Popen(
                    self.cmd,
                    shell=True,
                    cwd=self.cwd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                )
                for line in process.stdout:
                    if line.strip():
                        self.logger.output(line)
                process.wait()
                returncode = process.returncode

            else:
                result = subprocess.run(
                    self.cmd,
                    shell=True,
                    cwd=self.cwd,
                    capture_output=True,
                    text=True,
                )
                if result.stdout and result.stdout.strip():
                    self.logger.output(result.stdout)
                if result.returncode != 0 and result.stderr:
                    self.logger.error("Raw error output:")
                    self.logger.error_output(result.stderr)
                returncode = result.returncode

            self.success = returncode == 0

            if self.description:
                if self.success:
                    self.logger.success(f"Successfully finished: {self.description}")
                else:
                    self.logger.error(f"Failed to complete: {self.description}")

            if not self.success and self.exit_on_error:
                sys.exit(returncode)

            return self.success

        except Exception as e:
            if self.description:
                self.logger.error(f"Critical exception during: {self.description}")
            self.logger.info_step(f"Exception: {e}")
            if self.exit_on_error:
                sys.exit(1)
            return False


class TaskGroup:
    """
    Ambient context for grouping tasks with aggregate result reporting.
    Tasks inside the with-block auto-register via the class-level stack.

    abort_on_failure=True  → stops on first failure, sets self.aborted=True
    abort_on_failure=False → runs all tasks, reports aggregate result
    """

    _stack: list[Self] = []

    @classmethod
    def _get_active(cls) -> Self | None:
        """Return the innermost active group, or None if outside any group."""
        return cls._stack[-1] if cls._stack else None

    def __init__(
        self,
        title: str,
        info: str | None = None,
        abort_on_failure: bool = False,
        skip_confirm: bool = False,
    ):
        self.title = title
        self.info = info
        self.abort_on_failure = abort_on_failure
        self.skip_confirm = skip_confirm
        self.logger = Logger()
        self.results: list[Task] = []
        self.aborted = False  # distinguishes abort vs partial failure
        self._start_time: float | None = None

    def register_result(self, task: Task) -> None:
        """Called automatically by Task after execution."""
        self.results.append(task)
        if self.abort_on_failure and not task.success:
            raise TaskGroupAborted(f"Aborting: {task.description!r} failed")

    def __enter__(self) -> "TaskGroup":
        self._start_time = time.time()
        TaskGroup._stack.append(self)
        self.logger.header(self.title)
        if self.info:
            self.logger.info(self.info)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        TaskGroup._stack.pop()
        duration = time.time() - self._start_time if self._start_time else 0

        if exc_type is TaskGroupAborted:
            self.aborted = True
            self.logger.error(f"{self.title} aborted early ({duration:.1f}s)")
            return True  # swallow — expected control flow

        if self.results:
            success_count = sum(1 for r in self.results if r.success)
            total = len(self.results)
            detail = f"({success_count}/{total} tasks, {duration:.1f}s)"
            if self.succeeded:
                self.logger.success(f"{self.title} completed {detail}")
            else:
                self.logger.error(f"{self.title} completed with failures {detail}")

        return False  # propagate any unexpected exceptions

    @property
    def succeeded(self) -> bool:
        """True only if every task passed and the group was not aborted."""
        return not self.aborted and all(r.success for r in self.results)

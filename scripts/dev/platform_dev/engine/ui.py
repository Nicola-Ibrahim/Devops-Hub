import logging
import sys
import textwrap

# --- ANSI Color/Style Constants ---
_BOLD = "\033[1m"
_DIM = "\033[2m"
_BLUE = "\033[94m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_MAGENTA = "\033[95m"
_RESET = "\033[0m"

# --- Formatting Constants ---
_INDENT_BASE = 2
_STEP_LEVEL = 2  # 4 spaces
_OUTPUT_LEVEL = 5  # 10 spaces (for command outputs/sub-steps)
_CONFIRM_LEVEL = 2  # 4 spaces


def _get_indent(level: int) -> str:
    """Returns an indentation string based on the given level."""
    return f"{'':>{level * _INDENT_BASE}}"


class ConsoleFormatter(logging.Formatter):
    """A simple formatter that just returns the message as-is."""

    def format(self, record):
        return record.getMessage()


class Logger:
    """A wrapper class for structured logging in the development environment."""

    def __init__(self, name: str = "dev", level: int = logging.INFO):
        self._logger = logging.getLogger(name)
        self._logger.setLevel(level)

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(ConsoleFormatter())
            self._logger.addHandler(handler)

    def header(self, text: str) -> None:
        """Logs a boxed, high-contrast, centered block header."""
        width = 62
        text = text.upper()

        # Calculate centering
        content_width = len(text)
        if content_width > width - 4:
            text = text[: width - 7] + "..."
            content_width = len(text)

        padding_total = width - content_width - 2
        pad_left = padding_total // 2
        pad_right = padding_total - pad_left

        top = f"┌{'─' * (width - 2)}┐"
        middle = f"│{' ' * pad_left}{text}{' ' * pad_right}│"
        bottom = f"└{'─' * (width - 2)}┘"

        self._logger.info(f"\n\n{_MAGENTA}{top}")
        self._logger.info(middle)
        self._logger.info(f"{bottom}{_RESET}")

    def step(self, text: str) -> None:
        """Logs a structured action step."""
        indent = _get_indent(_STEP_LEVEL)
        self._logger.info(f"{indent}{_CYAN}➤ {text}...{_RESET}")

    def success(self, text: str) -> None:
        """Logs a success message."""
        indent = _get_indent(_STEP_LEVEL)
        self._logger.info(f"{indent}{_GREEN}✔ {text}{_RESET}")

    def error(self, text: str) -> None:
        """Logs an error message."""
        indent = _get_indent(_STEP_LEVEL)
        self._logger.error(f"{indent}{_RED}✖ ERROR: {text}{_RESET}")

    def warning(self, text: str) -> None:
        """Logs a warning message."""
        indent = _get_indent(_STEP_LEVEL)
        self._logger.warning(f"{indent}{_YELLOW}⚠  {text}{_RESET}")

    def info(self, text: str) -> None:
        """Logs an informational message."""
        indent = _get_indent(_STEP_LEVEL)
        self._logger.info(f"{indent}{_DIM}{_CYAN}ℹ {text}{_RESET}")

    def output(self, text: str) -> None:
        """
        Logs dimmed, indented output for command results.
        Automatically handles multiline strings.
        """
        indent = _get_indent(_OUTPUT_LEVEL)
        formatted = textwrap.indent(text.strip(), indent)
        # Apply DIM and RESET to the entire block
        self._logger.info(f"{_DIM}{formatted}{_RESET}")

    def error_output(self, text: str) -> None:
        """
        Logs red, indented error output for failed commands.
        Automatically handles multiline strings.
        """
        indent = _get_indent(_OUTPUT_LEVEL)
        formatted = textwrap.indent(text.strip(), indent)
        # Apply RED and RESET to the entire block
        self._logger.error(f"{_RED}{formatted}{_RESET}")

    def info_step(self, text: str) -> None:
        """Logs a dimmed, indented info message (e.g., 'Skipped by user')."""
        indent = _get_indent(_OUTPUT_LEVEL)
        self._logger.info(f"{indent}{_DIM}{text}{_RESET}")

    def confirm(self, prompt: str, skip_confirm: bool = False) -> bool:
        """
        Asks the user for a Y/n confirmation.
        Returns True if confirmed or if skip_confirm is True.
        """
        if skip_confirm:
            return True

        try:
            indent = _get_indent(_CONFIRM_LEVEL)
            response = (
                input(f"\n{indent}{_YELLOW}❓ {prompt} (y/N): {_RESET}").strip().lower()
            )
            return response == "y"
        except KeyboardInterrupt:
            self._logger.info("\n")
            sys.exit(0)

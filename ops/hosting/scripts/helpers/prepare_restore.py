"""Write a private disposable restore password; emit only its non-secret container name."""

import argparse
import os
import secrets
from pathlib import Path


def prepare(directory: Path) -> str:
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("Expected an existing private temporary directory")
    directory.chmod(0o700)
    descriptor = os.open(
        directory / "postgres_password", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        output.write(secrets.token_hex(32) + "\n")
    return "devops-hub-restore-" + secrets.token_hex(6)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        name = prepare(args.directory)
    except (OSError, ValueError):
        parser.exit(
            1, "Cannot initialize private restore configuration; details suppressed.\n"
        )
    print(name)


if __name__ == "__main__":
    main()

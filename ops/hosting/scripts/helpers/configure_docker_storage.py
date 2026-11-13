"""Safely preserve Docker daemon configuration while setting its approved data root."""

import argparse
import json
import os
import tempfile
from pathlib import Path


def configure(config_path: Path, data_root: str) -> None:
    if not Path(data_root).is_absolute() or config_path.is_symlink():
        raise ValueError(
            "Expected an absolute data root and a regular configuration path"
        )
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        config = {}
    if not isinstance(config, dict):
        raise TypeError("Docker daemon config must be an object")
    if config.get("data-root") not in (None, data_root):
        raise ValueError(
            "Docker already uses another data-root; refusing to replace it"
        )
    config["data-root"] = data_root
    descriptor, temporary = tempfile.mkstemp(prefix=".daemon-", dir=config_path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(config, output, sort_keys=True, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, config_path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_root")
    parser.add_argument("--config", type=Path, default=Path("/etc/docker/daemon.json"))
    args = parser.parse_args()
    try:
        configure(args.config, args.data_root)
    except (OSError, ValueError, TypeError):
        parser.exit(
            1,
            "Docker configuration is invalid or conflicts with the requested data root; details suppressed.\n",
        )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Create local Compose environment files without overwriting existing values."""

import base64
import os
import secrets
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

LEGACY_NAMES = (
    "postgres_password",
    "platform_database_url",
    "platform_token_pepper",
    "platform_installation_id",
    "platform_resource_encryption_key",
    "platform_resource_key_id",
)
BACKEND_REQUIRED = (
    "POSTGRES_PASSWORD",
    "PLATFORM_DATABASE_URL",
    "PLATFORM_TOKEN_PEPPER",
    "PLATFORM_INSTALLATION_ID",
    "PLATFORM_RESOURCE_KEY",
)


def private_file(path: Path, values: dict[str, str], required: tuple[str, ...]) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing symlink at {path}")
    if path.exists():
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"Incomplete local env file at {path}")
        configured = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                key, value = line.split("=", 1)
                configured[key.strip()] = value.strip().strip("\"'")
        if any(not configured.get(key, "").strip() for key in required):
            raise RuntimeError(
                f"Required configuration is missing in {path}; refusing to overwrite it"
            )
        path.chmod(0o600)
        return
    if any("\n" in value or "\r" in value for value in values.values()):
        raise RuntimeError("Local configuration must contain single-line values")
    content = "".join(f"{key}={value}\n" for key, value in values.items())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(content)


def control_plane_volume_exists() -> bool:
    docker = shutil.which("docker")
    if docker is None:
        raise RuntimeError(
            "Cannot verify the existing control-plane volume because Docker is unavailable"
        )
    if (
        subprocess.run(
            [docker, "info"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        != 0
    ):
        raise RuntimeError(
            "Cannot verify the existing control-plane volume because the Docker daemon is unavailable"
        )
    result = subprocess.run(
        [docker, "volume", "ls", "--format", "{{.Name}}"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Docker could not determine whether the control-plane volume exists"
        )
    return "devops-hub_control_plane_data" in result.stdout.splitlines()


def initialize(root: Path) -> None:
    for directory in (root / "backend", root / "frontend", root / ".local"):
        if directory.is_symlink():
            raise RuntimeError("Refusing symlink in local configuration directories")
    backend = root / "backend/.env"
    frontend = root / "frontend/.env"
    legacy = root / ".local/secrets"
    if legacy.is_symlink():
        raise RuntimeError(f"Refusing symlink at {legacy}")
    present = [
        name
        for name in LEGACY_NAMES
        if (legacy / name).exists() or (legacy / name).is_symlink()
    ]
    if not backend.exists() and not present and control_plane_volume_exists():
        raise RuntimeError(
            "Existing local database volume found; restore backend/.env instead of generating new credentials"
        )
    if any((legacy / name).is_symlink() for name in present):
        raise RuntimeError("Refusing symlink in legacy local secrets")
    if present and len(present) != len(LEGACY_NAMES) and not backend.exists():
        raise RuntimeError(
            "Incomplete legacy local secret set; refusing to generate new credentials"
        )
    if len(present) == len(LEGACY_NAMES):
        private = {
            name: (legacy / name).read_text(encoding="utf-8").strip()
            for name in LEGACY_NAMES
        }
        if not all(private.values()):
            raise RuntimeError(
                "Empty legacy local secret; refusing to change credentials"
            )
    else:
        password = secrets.token_hex(24)
        private = {
            "postgres_password": password,
            "platform_database_url": f"postgresql+psycopg://platform:{password}@postgres:5432/platform",
            "platform_token_pepper": secrets.token_hex(48),
            "platform_installation_id": str(uuid.uuid4()),
            "platform_resource_encryption_key": base64.urlsafe_b64encode(
                os.urandom(32)
            ).decode(),
            "platform_resource_key_id": "local",
        }
    backend_values = {
        "POSTGRES_DB": "platform",
        "POSTGRES_USER": "platform",
        "POSTGRES_PASSWORD": private["postgres_password"],
        "PLATFORM_DATABASE_URL": private["platform_database_url"],
        "PLATFORM_TOKEN_PEPPER": private["platform_token_pepper"],
        "PLATFORM_INSTALLATION_ID": private["platform_installation_id"],
        "PLATFORM_RESOURCE_KEY": private["platform_resource_encryption_key"],
        "PLATFORM_RESOURCE_KEY_ID": private["platform_resource_key_id"],
        "PLATFORM_METRICS_TOKEN": secrets.token_hex(48),
        "PLATFORM_ENVIRONMENT": "local",
        "PLATFORM_OPA_URL": "http://opa:8181",
        "PLATFORM_LOCAL_PROVIDER_ENABLED": "false",
        "PLATFORM_COOKIE_SECURE": "true",
        "PLATFORM_ADVERTISED_HOST": "127.0.0.1",
        "PLATFORM_APPROVED_LOCAL_IMAGES": "",
    }
    private_file(backend, backend_values, BACKEND_REQUIRED)
    private_file(frontend, {"BACKEND_URL": "http://api:8000"}, ("BACKEND_URL",))


def main() -> int:
    root = (
        Path(sys.argv[1]).resolve()
        if len(sys.argv) > 1
        else Path(__file__).resolve().parents[2]
    )
    try:
        initialize(root)
    except (OSError, RuntimeError, UnicodeError) as error:
        print(f"Local environment initialization failed: {error}", file=sys.stderr)
        return 1
    print("Local backend and frontend env files are present; values were not printed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

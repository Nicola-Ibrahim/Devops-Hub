#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
if [[ ! -e "${repo_root}/backend/.env" && ! -e "${repo_root}/.local/secrets/platform_database_url" ]]; then
  if command -v docker >/dev/null && docker volume inspect devops-hub_control_plane_data >/dev/null 2>&1; then
    echo "Existing local database volume found; restore backend/.env instead of generating new credentials." >&2
    exit 1
  fi
fi
python3 - "${repo_root}" <<'PY'
import base64
import os
import secrets
import sys
import uuid
from pathlib import Path

root = Path(sys.argv[1])
backend = root / "backend/.env"
frontend = root / "frontend/.env"
legacy = root / ".local/secrets"

def private_file(path: Path, values: dict[str, str]) -> None:
    if path.is_symlink():
        raise SystemExit(f"Refusing symlink at {path}")
    if path.exists():
        if not path.is_file() or not path.stat().st_size:
            raise SystemExit(f"Incomplete local env file at {path}")
        configured = dict(
            line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        )
        required = ("POSTGRES_PASSWORD", "PLATFORM_DATABASE_URL", "PLATFORM_TOKEN_PEPPER",
                    "PLATFORM_INSTALLATION_ID", "PLATFORM_RESOURCE_KEY") if path == backend else ("BACKEND_URL",)
        if any(not configured.get(key, "").strip().strip("\"'") for key in required):
            raise SystemExit(f"Required configuration is missing in {path}; refusing to overwrite it")
        path.chmod(0o600)
        return
    if any("\n" in value or "\r" in value for value in values.values()):
        raise SystemExit("Local configuration must contain single-line values")
    lines = "".join(f"{key}={value}\n" for key, value in values.items())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        output.write(lines)

legacy_names = (
    "postgres_password",
    "platform_database_url",
    "platform_token_pepper",
    "platform_installation_id",
    "platform_resource_encryption_key",
    "platform_resource_key_id",
)
present = [name for name in legacy_names if (legacy / name).exists()]
if present and len(present) != len(legacy_names) and not backend.exists():
    raise SystemExit("Incomplete legacy local secret set; refusing to generate new credentials")
if len(present) == len(legacy_names):
    private = {name: (legacy / name).read_text(encoding="utf-8").strip() for name in legacy_names}
    if not all(private.values()):
        raise SystemExit("Empty legacy local secret; refusing to change credentials")
else:
    password = secrets.token_hex(24)
    private = {
        "postgres_password": password,
        "platform_database_url": f"postgresql+psycopg://platform:{password}@postgres:5432/platform",
        "platform_token_pepper": secrets.token_hex(48),
        "platform_installation_id": str(uuid.uuid4()),
        "platform_resource_encryption_key": base64.urlsafe_b64encode(os.urandom(32)).decode(),
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
private_file(backend, backend_values)
private_file(frontend, {"BACKEND_URL": "http://api:8000"})
print("Local backend and frontend env files are present; values were not printed.")
PY

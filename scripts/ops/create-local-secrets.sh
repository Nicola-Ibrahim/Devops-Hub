#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
secret_dir="${repo_root}/.local/secrets"
mkdir -p "${secret_dir}"
chmod 700 "${repo_root}/.local" "${secret_dir}"

legacy_names=(postgres_password platform_database_url platform_token_pepper platform_installation_id platform_resource_encryption_key platform_resource_key_id)
names=("${legacy_names[@]}" platform_metrics_token)
present_legacy=0
for name in "${legacy_names[@]}"; do
  if [[ -s "${secret_dir}/${name}" ]]; then
    present_legacy=$((present_legacy + 1))
  fi
done
if (( present_legacy == ${#legacy_names[@]} )) && [[ -s "${secret_dir}/platform_metrics_token" ]]; then
  if [[ -L "${secret_dir}/platform_metrics_token" || ! -f "${secret_dir}/platform_metrics_token" ]]; then
    echo "Metrics token path must be a regular local file; refusing to follow links." >&2
    exit 1
  fi
  chmod 0444 "${secret_dir}/platform_metrics_token"
  echo "Local demo secret files already exist; leaving them unchanged."
  exit 0
elif (( present_legacy == ${#legacy_names[@]} )) && [[ ! -e "${secret_dir}/platform_metrics_token" ]]; then
  umask 077
  tmp_file="$(mktemp "${secret_dir}/.metrics-token.XXXXXX")"
  python3 - "${tmp_file}" <<'PY'
import secrets
import sys
from pathlib import Path

path = Path(sys.argv[1])
path.write_text(secrets.token_hex(48) + "\n", encoding="utf-8")
path.chmod(0o444)
PY
  mv "${tmp_file}" "${secret_dir}/platform_metrics_token"
  echo "Added the private Prometheus scrape token without changing existing local keys."
  exit 0
elif (( present_legacy != 0 )) || [[ -e "${secret_dir}/platform_metrics_token" ]]; then
  echo "Incomplete local secret set at ${secret_dir}; refusing to rotate or overwrite it." >&2
  exit 1
fi

umask 077
tmp_dir="$(mktemp -d "${secret_dir}/.generate.XXXXXX")"
cleanup() { rm -rf "${tmp_dir}"; }
trap cleanup EXIT

python3 - "${tmp_dir}" <<'PY'
import base64
import os
import secrets
import sys
import uuid
from pathlib import Path

target = Path(sys.argv[1])
password = secrets.token_hex(24)
values = {
    "postgres_password": password,
    "platform_database_url": f"postgresql+psycopg://platform:{password}@postgres:5432/platform",
    "platform_token_pepper": secrets.token_hex(48),
    "platform_installation_id": str(uuid.uuid4()),
    "platform_resource_encryption_key": base64.urlsafe_b64encode(os.urandom(32)).decode(),
    "platform_resource_key_id": "local",
    "platform_metrics_token": secrets.token_hex(48),
}
for name, value in values.items():
    (target / name).write_text(value + "\n", encoding="utf-8")
    (target / name).chmod(0o444 if name == "platform_metrics_token" else 0o600)
PY

for name in "${names[@]}"; do
  mv "${tmp_dir}/${name}" "${secret_dir}/${name}"
done
rmdir "${tmp_dir}"
trap - EXIT
echo "Created local-only demo secrets. Values were not printed; the metrics token is readable only through the mode-0700 secret directory."

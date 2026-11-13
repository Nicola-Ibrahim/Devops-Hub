#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: restore-control-plane.sh <encrypted-backup.dump.age>" >&2
  exit 2
fi
archive="$1"
identity_file="${AGE_IDENTITY_FILE:-}"
if [[ ! -s "${archive}" || ! -s "${identity_file}" ]]; then
  echo "Encrypted archive and operator-controlled AGE_IDENTITY_FILE are required." >&2
  exit 2
fi
command -v age >/dev/null || { echo "Install age before restoring a backup." >&2; exit 1; }

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null && [[ -r "${script_dir}/helpers/prepare_restore.py" ]] || {
  echo "Standalone restore helper and Python 3 are required." >&2; exit 1;
}

# Validate decryptability/archive structure before allocating the isolated DB.
if ! age --decrypt --identity "${identity_file}" "${archive}" | docker run --rm -i --pull=never --network none postgres:16.6 pg_restore --list >/dev/null; then
  echo "Backup integrity/decryption validation failed; no restore container was started." >&2
  exit 1
fi

secret_dir="$(mktemp -d "${TMPDIR:-/tmp}/devops-hub-restore.XXXXXX")"
umask 077
container_name=""

cleanup() {
  if [[ -n "${container_name}" ]]; then docker stop "${container_name}" >/dev/null 2>&1 || true; fi
  rm -rf "${secret_dir}"
}
trap cleanup EXIT
container_name="$(python3 "${script_dir}/helpers/prepare_restore.py" "${secret_dir}")"

docker run -d --rm --pull=never --network none --name "${container_name}" \
  --env POSTGRES_DB=platform_restore \
  --env POSTGRES_USER=platform \
  --env POSTGRES_PASSWORD_FILE=/run/secrets/postgres_password \
  --mount "type=bind,source=${secret_dir}/postgres_password,target=/run/secrets/postgres_password,readonly" \
  postgres:16.6 >/dev/null

ready=false
for attempt in $(seq 1 30); do
  if docker exec "${container_name}" pg_isready --username=platform --dbname=platform_restore >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "${ready}" != "true" ]]; then
  echo "Isolated PostgreSQL did not become ready; no active database was changed." >&2
  exit 1
fi

if ! age --decrypt --identity "${identity_file}" "${archive}" \
  | docker exec -i "${container_name}" pg_restore --exit-on-error --username=platform --dbname=platform_restore; then
  echo "Restore failed. The isolated validation container will be removed; no active database was changed." >&2
  exit 1
fi

version="$(docker exec "${container_name}" psql --username=platform --dbname=platform_restore --tuples-only --no-align --command \
  "SELECT version_num FROM alembic_version LIMIT 1")"
if [[ -z "${version}" ]]; then
  echo "Restore completed but migration revision could not be read; isolated validation failed." >&2
  exit 1
fi
echo "Isolated restore verified at schema revision ${version}; active services and data volumes were untouched."
echo "The disposable PostgreSQL container is removed when this command exits."

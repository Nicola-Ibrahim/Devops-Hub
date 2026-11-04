#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: backup-control-plane.sh <destination-directory>" >&2
  exit 2
fi
destination="$1"
recipient="${AGE_RECIPIENT:-}"
s3_destination="${PLATFORM_BACKUP_UPLOAD_S3_URI:-}"
if [[ ! "${recipient}" =~ ^age1[0-9a-z]{20,}$ ]]; then
  echo "Set AGE_RECIPIENT to the operator-controlled age public recipient; no backup was created." >&2
  exit 2
fi
command -v age >/dev/null || { echo "Install age before creating an encrypted backup." >&2; exit 1; }
command -v sha256sum >/dev/null || { echo "sha256sum is required." >&2; exit 1; }

mkdir -p "${destination}"
chmod 700 "${destination}"
umask 077
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
plain_file="$(mktemp "${destination}/.control-plane-${timestamp}.XXXXXX.dump")"
encrypted_file="${destination}/control-plane-${timestamp}.dump.age"
cleanup() { rm -f "${plain_file}"; }
trap cleanup EXIT

# pg_dump uses the container-local Unix socket. The control-plane password is
# neither read by this script nor placed in arguments, environment or output.
docker compose exec -T postgres pg_dump --username=platform --dbname=platform --format=custom >"${plain_file}"
chmod 600 "${plain_file}"
age --recipient "${recipient}" --output "${encrypted_file}" "${plain_file}"
chmod 600 "${encrypted_file}"
rm -f "${plain_file}"
trap - EXIT
(
  cd "${destination}"
  sha256sum "control-plane-${timestamp}.dump.age" >"control-plane-${timestamp}.dump.age.sha256"
  chmod 600 "control-plane-${timestamp}.dump.age.sha256"
)
if [[ -n "${s3_destination}" ]]; then
  if [[ ! "${s3_destination}" =~ ^s3://[a-z0-9.-]+/control-plane$ ]]; then
    echo "PLATFORM_BACKUP_UPLOAD_S3_URI must name the approved control-plane/ prefix." >&2
    exit 2
  fi
  command -v aws >/dev/null || { echo "AWS CLI is required for the configured remote backup target." >&2; exit 1; }
  aws s3 cp --only-show-errors --sse AES256 \
    "${encrypted_file}" "${s3_destination}/control-plane-${timestamp}.dump.age"
  aws s3 cp --only-show-errors --sse AES256 \
    "${destination}/control-plane-${timestamp}.dump.age.sha256" \
    "${s3_destination}/control-plane-${timestamp}.dump.age.sha256"
  rm -f "${encrypted_file}" "${destination}/control-plane-${timestamp}.dump.age.sha256"
  echo "Encrypted control-plane backup uploaded to the configured private S3 prefix."
  exit 0
fi
echo "Encrypted control-plane backup created: ${encrypted_file}"
echo "The unencrypted intermediate was removed. Store the age identity separately from this artifact."

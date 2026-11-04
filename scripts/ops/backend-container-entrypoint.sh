#!/bin/sh
set -eu

runtime_secrets=/run/platform-secrets
mkdir -p "${runtime_secrets}"
chmod 0700 "${runtime_secrets}"

copy_secret_file() {
  variable="$1"
  file_variable="${variable}_FILE"
  source_path="$(printenv "${file_variable}" 2>/dev/null || true)"
  if [ -z "${source_path}" ]; then
    return 0
  fi
  case "${source_path}" in
    /run/secrets/*) ;;
    *) echo "Container secret path must be mounted under /run/secrets." >&2; exit 1 ;;
  esac
  if [ ! -f "${source_path}" ] || [ ! -r "${source_path}" ]; then
    echo "Required container secret file is unavailable." >&2
    exit 1
  fi
  runtime_path="${runtime_secrets}/${variable#PLATFORM_}"
  install -o 10001 -g 10001 -m 0400 -- "${source_path}" "${runtime_path}"
  export "${file_variable}=${runtime_path}"
}

copy_secret_file PLATFORM_DATABASE_URL
copy_secret_file PLATFORM_TOKEN_PEPPER
copy_secret_file PLATFORM_INSTALLATION_ID
copy_secret_file PLATFORM_RESOURCE_KEY
copy_secret_file PLATFORM_RESOURCE_KEY_ID
copy_secret_file PLATFORM_METRICS_TOKEN
chown 10001:10001 "${runtime_secrets}"

if [ "$#" -eq 0 ]; then
  echo "Container command is required." >&2
  exit 2
fi
exec setpriv --reuid=10001 --regid=10001 --keep-groups -- "$@"

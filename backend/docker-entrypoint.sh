#!/bin/sh
set -eu

runtime_secrets=/run/platform-secrets
secret_files_root="${PLATFORM_SECRET_FILES_ROOT:-/run/secrets}"
mkdir -p "${runtime_secrets}"
chmod 0700 "${runtime_secrets}"

copy_secret_file() {
  variable="$1"
  file_variable="${variable}_FILE"
  source_path="$(printenv "${file_variable}" 2>/dev/null || true)"
  if [ -z "${source_path}" ]; then
    return 0
  fi
  case "${secret_files_root}" in
    /*) ;;
    *) echo "Secret file root must be an absolute path." >&2; exit 1 ;;
  esac
  secret_files_root="$(realpath -e -- "${secret_files_root}")"
  if [ "${secret_files_root}" = "/" ]; then
    echo "Secret file root cannot be the filesystem root." >&2
    exit 1
  fi
  if [ ! -f "${source_path}" ] || [ ! -r "${source_path}" ]; then
    echo "Required container secret file is unavailable." >&2
    exit 1
  fi
  source_path="$(realpath -e -- "${source_path}")"
  case "${source_path}" in
    "${secret_files_root}"/*) ;;
    *) echo "Container secret file must be inside PLATFORM_SECRET_FILES_ROOT." >&2; exit 1 ;;
  esac
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
copy_secret_file PLATFORM_GITHUB_TOKEN
copy_secret_file PLATFORM_GITHUB_WEBHOOK_SECRET
chown 10001:10001 "${runtime_secrets}"

if [ "$#" -eq 0 ]; then
  echo "Container command is required." >&2
  exit 2
fi
exec setpriv --reuid=10001 --regid=10001 --keep-groups -- "$@"

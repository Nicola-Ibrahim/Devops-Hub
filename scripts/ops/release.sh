#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ne 3 ]]; then
  echo "Usage: release.sh <api-image@sha256:digest> <frontend-image@sha256:digest> <migration-compatible-previous:true|false>" >&2
  exit 2
fi

api_image="$1"
frontend_image="$2"
migration_compatible_previous="$3"
digest_re='^.+@sha256:[0-9a-f]{64}$'
if [[ ! "${api_image}" =~ ${digest_re} || ! "${frontend_image}" =~ ${digest_re} ]]; then
  echo "Release requires immutable sha256 image digests." >&2
  exit 2
fi
if [[ "${migration_compatible_previous}" != "true" ]]; then
  echo "Release blocked: operator must confirm migrations remain compatible with the previous application image." >&2
  exit 2
fi

app_root="${PLATFORM_APP_ROOT:-/opt/devops-hub}"
secrets_dir="${PLATFORM_SECRETS_DIR:-/etc/devops-hub/secrets}"
release_history="${app_root}/releases"
current_env="${app_root}/.release.env"
candidate_env="${app_root}/.release.env.next.$$"
docker_config="$(mktemp -d "${TMPDIR:-/tmp}/devops-hub-docker-config.XXXXXX")"
umask 077
mkdir -p "${release_history}"
cd "${app_root}"
cleanup() {
  rm -f "${candidate_env}"
  rm -rf "${docker_config}"
}
trap cleanup EXIT

for secret in postgres_password platform_database_url platform_token_pepper platform_installation_id platform_resource_encryption_key platform_resource_key_id platform_metrics_token; do
  if [[ ! -s "${secrets_dir}/${secret}" ]]; then
    echo "Release blocked: required operator-managed secret file is missing." >&2
    exit 1
  fi
done

cat >"${candidate_env}" <<EOF
PLATFORM_API_IMAGE=${api_image}
PLATFORM_FRONTEND_IMAGE=${frontend_image}
PLATFORM_SECRETS_DIR=${secrets_dir}
PLATFORM_DOCKER_GID=$(stat -c '%g' /var/run/docker.sock 2>/dev/null || stat -f '%g' /var/run/docker.sock)
EOF
chmod 600 "${candidate_env}"

export DOCKER_CONFIG="${docker_config}"
api_registry="${api_image%%/*}"
frontend_registry="${frontend_image%%/*}"
if [[ "${api_registry}" != "${frontend_registry}" ]]; then
  echo "Release blocked: API and frontend images must use the same registry." >&2
  exit 2
fi
if [[ "${api_registry}" == *".dkr.ecr."* ]]; then
  if [[ -z "${AWS_REGION:-}" ]]; then
    echo "Release blocked: AWS_REGION is required for ECR authentication." >&2
    exit 2
  fi
  if ! aws ecr get-login-password --region "${AWS_REGION}" | docker login --username AWS --password-stdin "${api_registry}" >/dev/null; then
    echo "Release blocked: unable to obtain short-lived ECR pull credentials." >&2
    exit 1
  fi
fi

compose=(docker compose --env-file "${candidate_env}" --profile app)
record_attempt() {
  local outcome="$1"
  local attempted_at
  attempted_at="$(date -u +%Y%m%dT%H%M%SZ)"
  printf 'PLATFORM_API_IMAGE=%s\nPLATFORM_FRONTEND_IMAGE=%s\nPLATFORM_SECRETS_DIR=%s\nOUTCOME=%s\n' \
    "${api_image}" "${frontend_image}" "${secrets_dir}" "${outcome}" \
    >"${release_history}/${attempted_at}.${outcome}.env"
  chmod 600 "${release_history}/${attempted_at}.${outcome}.env"
}

wait_ready() {
  local attempt
  for attempt in $(seq 1 60); do
    if curl --silent --show-error --fail --max-time 3 --output /dev/null http://127.0.0.1:8000/health/ready \
      && curl --silent --show-error --fail --max-time 3 --output /dev/null http://127.0.0.1:3000/; then
      return 0
    fi
    sleep 3
  done
  return 1
}

if ! "${compose[@]}" config --quiet; then
  echo "Release blocked: Compose configuration is invalid." >&2
  exit 1
fi
if ! "${compose[@]}" pull api worker migrate frontend; then
  echo "Release blocked: an immutable release image could not be pulled." >&2
  exit 1
fi

# Schema changes are forward-only. Never run an automatic database downgrade.
if ! "${compose[@]}" run --rm migrate; then
  record_attempt failed-migration
  echo "Release blocked: schema migration failed; the running application was left in place." >&2
  exit 1
fi

rollback() {
  if [[ ! -s "${current_env}" ]]; then
    echo "Readiness failed and no previous release is recorded; operator recovery is required." >&2
    return 1
  fi
  echo "Readiness failed; restoring the previous compatible application image digests." >&2
  local previous=(docker compose --env-file "${current_env}" --profile app)
  if ! "${previous[@]}" pull api worker migrate frontend; then
    echo "Rollback blocked: previous image pull failed; current state is preserved for operator recovery." >&2
    return 1
  fi
  if ! "${previous[@]}" up -d --no-build; then
    echo "Rollback failed while restoring the previous services; operator recovery is required." >&2
    return 1
  fi
  if ! wait_ready; then
    echo "Rollback containers started but previous release readiness failed; operator recovery is required." >&2
    return 1
  fi
  return 0
}

if ! "${compose[@]}" up -d --no-build; then
  record_attempt failed-start
  rollback || true
  exit 1
fi

if ! wait_ready; then
  record_attempt failed-readiness
  rollback || true
  exit 1
fi

released_at="$(date -u +%Y%m%dT%H%M%SZ)"
mv -f "${candidate_env}" "${current_env}"
cp "${current_env}" "${release_history}/${released_at}.env"
chmod 600 "${current_env}" "${release_history}/${released_at}.env"
echo "Release ${released_at} is ready. API and dashboard readiness checks passed."

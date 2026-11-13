#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/dev.sh help
  scripts/dev.sh up [--resources] [--application-delivery]
  scripts/dev.sh down
  scripts/dev.sh status
  scripts/dev.sh logs SERVICE
  scripts/dev.sh clean [--apply]

SERVICE must be one of: api, application-worker, frontend, migrate, opa,
postgres, worker.

Requirements for up: local Docker Engine/Desktop with Compose v2, and Python 3
for the standalone private-env helper. No Python package installation is needed.
Clean previews cache paths unless --apply is supplied; down preserves volumes.
USAGE
}

fail() { printf 'Error: %s\n' "$1" >&2; exit "${2:-1}"; }

require_local_docker() {
  command -v docker >/dev/null 2>&1 || fail "Docker CLI is unavailable; install/start Docker Desktop or Engine first."
  if [[ -n "${DOCKER_HOST:-}" && -z "${DOCKER_CONTEXT:-}" ]]; then
    endpoint="$DOCKER_HOST"
  else
    endpoint="$(docker context inspect --format '{{.Endpoints.docker.Host}}')" || fail "Could not resolve the current Docker context."
  fi
  case "$endpoint" in
    unix://*) ;;
    *) fail "This command is local-only; select a local Unix-socket Docker context." ;;
  esac
  docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable or unreachable; start Docker Desktop or Engine first."
}

if [[ $# -eq 0 || "$1" == help || "$1" == --help || "$1" == -h ]]; then
  usage
  exit 0
fi
command_name="$1"
shift
cd "$REPO_ROOT"

case "$command_name" in
  up)
    profiles="--profile app"
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --resources) profiles="$profiles --profile resources" ;;
        --application-delivery) profiles="$profiles --profile application-delivery" ;;
        *) fail "unknown up option: $1" 2 ;;
      esac
      shift
    done
    require_local_docker
    python3 "${REPO_ROOT}/scripts/helpers/init_env.py" || fail "Local environment initialization failed."
    socket=/var/run/docker.sock
    docker_gid=0
    if [[ -S "$socket" || -e "$socket" ]]; then
      if docker_gid="$(stat -c '%g' "$socket" 2>/dev/null)"; then
        :
      elif docker_gid="$(stat -f '%g' "$socket" 2>/dev/null)"; then
        :
      else
        fail "Could not determine Docker socket group ID at $socket."
      fi
    fi
    # profiles contains only fixed options from the allowlist above.
    # shellcheck disable=SC2086
    PLATFORM_DOCKER_GID="$docker_gid" docker compose $profiles up --build -d --wait || fail "Compose startup/readiness failed (including migration completion)."
    printf 'Core services passed Compose readiness. Dashboard: http://127.0.0.1:3000; API: http://127.0.0.1:8000/health/ready\n'
    printf 'Worker startup alone does not establish provider readiness.\n'
    ;;
  down)
    [[ $# -eq 0 ]] || fail "down takes no options" 2
    require_local_docker
    docker compose --profile app --profile resources --profile application-delivery down || fail "Compose shutdown failed."
    ;;
  status)
    [[ $# -eq 0 ]] || fail "status takes no options" 2
    require_local_docker
    docker compose --profile app --profile resources --profile application-delivery ps || fail "Could not read Compose status."
    ;;
  logs)
    [[ $# -eq 1 ]] || fail "logs requires exactly one allowlisted service" 2
    case "$1" in
      api|application-worker|frontend|migrate|opa|postgres|worker) ;;
      *) fail "service is not allowlisted: $1" 2 ;;
    esac
    require_local_docker
    docker compose --profile app --profile resources --profile application-delivery logs --follow "$1" || fail "Could not read service logs."
    ;;
  clean)
    apply=0
    if [[ $# -gt 1 ]]; then fail "clean accepts only optional --apply" 2; fi
    if [[ $# -eq 1 ]]; then
      [[ "$1" == --apply ]] || fail "clean accepts only optional --apply" 2
      apply=1
    fi
    for cache in .pytest_cache .mypy_cache .ruff_cache backend/.pytest_cache frontend/.next/cache scripts/.pytest_cache; do
      target="${REPO_ROOT}"
      path_parts="${cache//\// }"
      for part in $path_parts; do
        target="${target}/${part}"
        if [[ -L "$target" ]]; then fail "refusing symlink cache path: $cache"; fi
      done
      if [[ -e "$target" ]]; then
        [[ -d "$target" ]] || fail "refusing non-directory cache path: $cache"
        printf '%s %s\n' "$([[ $apply -eq 1 ]] && printf 'Remove' || printf 'Would remove')" "$cache"
        if [[ $apply -eq 1 ]]; then rm -rf -- "$target" || fail "could not remove cache: $cache"; fi
      fi
    done
    ;;
  *)
    usage >&2
    fail "unknown command: $command_name" 2
    ;;
esac

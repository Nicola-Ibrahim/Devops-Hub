#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bash "${repo_root}/scripts/ops/create-local-env.sh"
if [[ ! -S /var/run/docker.sock ]]; then
  echo "Docker daemon socket /var/run/docker.sock is unavailable; start Docker Desktop/Engine first." >&2
  exit 1
fi
if docker_gid="$(stat -c '%g' /var/run/docker.sock 2>/dev/null)"; then
  :
else
  docker_gid="$(stat -f '%g' /var/run/docker.sock)"
fi
cd "${repo_root}"
profiles=(--profile app)
for feature in "$@"; do
  case "${feature}" in
    --resources) profiles+=(--profile resources) ;;
    --application-delivery) profiles+=(--profile application-delivery) ;;
    *) echo "Unknown option: ${feature}" >&2; exit 2 ;;
  esac
done
PLATFORM_DOCKER_GID="${docker_gid}" docker compose "${profiles[@]}" up --build -d
echo "Compose started selected profiles. Dashboard: http://127.0.0.1:3000; API readiness: http://127.0.0.1:8000/health/ready."

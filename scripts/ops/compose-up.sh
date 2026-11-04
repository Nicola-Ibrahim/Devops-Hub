#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
"${repo_root}/scripts/ops/create-local-secrets.sh"
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
PLATFORM_DOCKER_GID="${docker_gid}" docker compose --profile app up --build -d
echo "Platform services started. Dashboard: http://127.0.0.1:3000; API: http://127.0.0.1:8000/health/ready"

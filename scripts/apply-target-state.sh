#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
ensure_command docker

wait_for_container_healthy() {
  local container_name="$1"
  local timeout_seconds="${2:-120}"
  local elapsed=0
  local status=""

  while (( elapsed < timeout_seconds )); do
    status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_name}" 2>/dev/null || true)"
    case "${status}" in
      healthy|running)
        return 0
        ;;
    esac
    sleep 2
    elapsed=$((elapsed + 2))
  done

  printf 'Timed out waiting for %s to become healthy.\n' "${container_name}" >&2
  return 1
}

wait_for_proxy_console() {
  local timeout_seconds="${1:-120}"
  local elapsed=0

  while (( elapsed < timeout_seconds )); do
    if docker exec --user 1000 "${TARGET_PROXY_CONTAINER}" mc-send-to-console lpv sync >/dev/null 2>&1; then
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done

  printf 'Timed out waiting for proxy console access on %s.\n' "${TARGET_PROXY_CONTAINER}" >&2
  return 1
}

restart_target_containers() {
  docker restart \
    "${TARGET_PROXY_CONTAINER}" \
    "${TARGET_LOBBY_CONTAINER}" \
    "${TARGET_SURVIVAL_CONTAINER}" \
    "${TARGET_CREATIVE_CONTAINER}" >/dev/null
}

main() {
  "${SCRIPT_DIR}/validate-target.sh"
  "${SCRIPT_DIR}/sync-plugins.sh"
  "${SCRIPT_DIR}/render-luckperms-config.sh"

  admin_compose up -d --build mariadb
  wait_for_container_healthy mc-admin-mariadb 120

  restart_target_containers
  admin_compose up -d --build

  wait_for_proxy_console 120
  "${SCRIPT_DIR}/bootstrap-permissions.sh"
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env

restart_container() {
  local container_name="$1"
  docker restart "${container_name}" >/dev/null
  printf 'Restarted %s\n' "${container_name}"
}

case "${1:-}" in
  backup_now)
    "${SCRIPT_DIR}/run-backup-now.sh"
    ;;
  sync_whitelist)
    require_envs TARGET_SYNC_WHITELIST_SCRIPT
    "$(target_path_local "${TARGET_SYNC_WHITELIST_SCRIPT}")"
    ;;
  restart_proxy)
    require_envs TARGET_PROXY_CONTAINER
    restart_container "${TARGET_PROXY_CONTAINER}"
    ;;
  restart_lobby)
    require_envs TARGET_LOBBY_CONTAINER
    restart_container "${TARGET_LOBBY_CONTAINER}"
    ;;
  restart_survival)
    require_envs TARGET_SURVIVAL_CONTAINER
    restart_container "${TARGET_SURVIVAL_CONTAINER}"
    ;;
  restart_creative)
    require_envs TARGET_CREATIVE_CONTAINER
    restart_container "${TARGET_CREATIVE_CONTAINER}"
    ;;
  restart_all_core)
    require_envs TARGET_PROXY_CONTAINER TARGET_LOBBY_CONTAINER TARGET_SURVIVAL_CONTAINER TARGET_CREATIVE_CONTAINER
    restart_container "${TARGET_PROXY_CONTAINER}"
    restart_container "${TARGET_LOBBY_CONTAINER}"
    restart_container "${TARGET_SURVIVAL_CONTAINER}"
    restart_container "${TARGET_CREATIVE_CONTAINER}"
    ;;
  stage_admin_state)
    "${SCRIPT_DIR}/stage-admin-state.sh"
    ;;
  reapply_plugins_and_configs)
    "${SCRIPT_DIR}/sync-plugins.sh"
    "${SCRIPT_DIR}/render-luckperms-config.sh"
    "${SCRIPT_DIR}/bootstrap-permissions.sh"
    "${SCRIPT_DIR}/olive-action.sh" restart_all_core
    ;;
  *)
    printf 'Usage: %s <backup_now|sync_whitelist|restart_proxy|restart_lobby|restart_survival|restart_creative|restart_all_core|stage_admin_state|reapply_plugins_and_configs>\n' "$0" >&2
    exit 1
    ;;
esac

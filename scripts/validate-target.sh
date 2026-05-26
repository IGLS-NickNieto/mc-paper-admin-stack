#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
ensure_command docker

if [[ -z "${BACKUP_COMPANION_ROOT:-}" ]]; then
  BACKUP_COMPANION_ROOT="$(cd "${SCRIPT_DIR}/../../mc-backup-google-drive" 2>/dev/null && pwd || true)"
  export BACKUP_COMPANION_ROOT
fi

require_envs \
  BACKUP_COMPANION_ROOT \
  TARGET_STACK_ROOT \
  TARGET_COMPOSE_PROJECT_DIR \
  TARGET_COMPOSE_FILE \
  TARGET_DATA_DIR \
  TARGET_BACKUPS_DIR \
  TARGET_ACCESS_DIR \
  TARGET_INVITE_PLAYERS_FILE \
  TARGET_BACKUP_SCRIPT \
  TARGET_SYNC_WHITELIST_SCRIPT \
  TARGET_PROXY_CONTAINER \
  TARGET_LOBBY_CONTAINER \
  TARGET_SURVIVAL_CONTAINER \
  TARGET_CREATIVE_CONTAINER

for path_name in \
  BACKUP_COMPANION_ROOT \
  TARGET_STACK_ROOT \
  TARGET_COMPOSE_PROJECT_DIR \
  TARGET_DATA_DIR \
  TARGET_BACKUPS_DIR \
  TARGET_ACCESS_DIR; do
  if [[ ! -d "${!path_name}" ]]; then
    printf 'Expected directory not found: %s=%s\n' "${path_name}" "${!path_name}" >&2
    exit 1
  fi
done

for file_name in \
  TARGET_COMPOSE_FILE \
  TARGET_BACKUP_SCRIPT \
  TARGET_SYNC_WHITELIST_SCRIPT; do
  if [[ ! -f "${!file_name}" ]]; then
    printf 'Expected file not found: %s=%s\n' "${file_name}" "${!file_name}" >&2
    exit 1
  fi
done

for script_name in TARGET_BACKUP_SCRIPT TARGET_SYNC_WHITELIST_SCRIPT; do
  if [[ ! -x "${!script_name}" ]]; then
    printf 'Expected executable script: %s=%s\n' "${script_name}" "${!script_name}" >&2
    exit 1
  fi
done

for container_name in \
  TARGET_PROXY_CONTAINER \
  TARGET_LOBBY_CONTAINER \
  TARGET_SURVIVAL_CONTAINER \
  TARGET_CREATIVE_CONTAINER; do
  if ! docker container inspect "${!container_name}" >/dev/null 2>&1; then
    printf 'Target container not found: %s=%s\n' "${container_name}" "${!container_name}" >&2
    exit 1
  fi
done

for backup_file in \
  "${BACKUP_COMPANION_ROOT}/scripts/offsite-backup.sh" \
  "${BACKUP_COMPANION_ROOT}/scripts/backup-verify.sh" \
  "${BACKUP_COMPANION_ROOT}/scripts/restore-to-staging.sh" \
  "${BACKUP_COMPANION_ROOT}/scripts/promote-rollback.sh"; do
  if [[ ! -f "${backup_file}" ]]; then
    printf 'Expected backup companion file not found: %s\n' "${backup_file}" >&2
    exit 1
  fi
done

printf 'Target validation passed for %s\n' "${TARGET_STACK_ROOT}"

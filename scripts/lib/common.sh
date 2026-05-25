#!/usr/bin/env bash
set -euo pipefail

admin_repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

load_admin_env() {
  local root
  local line
  local key
  local value
  root="$(admin_repo_root)"

  if [[ -f "${root}/.env" ]]; then
    while IFS= read -r line || [[ -n "${line}" ]]; do
      line="${line%$'\r'}"
      [[ -z "${line}" ]] && continue
      [[ "${line}" =~ ^[[:space:]]*# ]] && continue
      [[ "${line}" != *=* ]] && continue

      key="${line%%=*}"
      value="${line#*=}"
      export "${key}=${value}"
    done < "${root}/.env"
  fi
}

require_envs() {
  local name
  local missing=()

  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      missing+=("${name}")
    fi
  done

  if (( ${#missing[@]} > 0 )); then
    printf 'Missing required environment variables: %s\n' "${missing[*]}" >&2
    exit 1
  fi
}

ensure_command() {
  local command_name="$1"
  if ! command -v "${command_name}" >/dev/null 2>&1; then
    printf 'Required command not found: %s\n' "${command_name}" >&2
    exit 1
  fi
}

admin_compose() {
  local root
  root="$(admin_repo_root)"
  docker compose --project-directory "${root}" "$@"
}

csv_list_to_array() {
  local raw="${1:-}"
  local trimmed

  IFS=',' read -r -a CSV_LIST_RESULT <<<"${raw}"
  for i in "${!CSV_LIST_RESULT[@]}"; do
    trimmed="${CSV_LIST_RESULT[$i]}"
    trimmed="${trimmed#"${trimmed%%[![:space:]]*}"}"
    trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
    CSV_LIST_RESULT[$i]="${trimmed}"
  done
}

target_path_local() {
  local host_path="$1"

  if [[ -n "${MC_ADMIN_TARGET_ROOT_MOUNT:-}" ]] && [[ -n "${TARGET_STACK_ROOT:-}" ]]; then
    case "${host_path}" in
      "${TARGET_STACK_ROOT}")
        printf '%s\n' "${MC_ADMIN_TARGET_ROOT_MOUNT}"
        return
        ;;
      "${TARGET_STACK_ROOT}"/*)
        printf '%s/%s\n' "${MC_ADMIN_TARGET_ROOT_MOUNT}" "${host_path#"${TARGET_STACK_ROOT}/"}"
        return
        ;;
    esac
  fi

  printf '%s\n' "${host_path}"
}

ensure_directory() {
  local path="$1"
  mkdir -p "${path}"
}

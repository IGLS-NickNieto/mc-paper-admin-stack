#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
require_envs TARGET_DATA_DIR

MANIFEST_PATH="${ROOT_DIR}/plugins/manifest.csv"
MANUAL_DIR="${ROOT_DIR}/plugins/manual"
TMP_DIR="$(mktemp -d)"
FAILURES=0

cleanup() {
  rm -rf "${TMP_DIR}"
}

trap cleanup EXIT

fetch_adjacent_sha256() {
  local url="$1"
  local checksum

  checksum="$(curl -fsSL "${url}.sha256" 2>/dev/null || true)"
  if [[ -n "${checksum}" ]]; then
    printf '%s\n' "${checksum%% *}"
    return
  fi

  printf '\n'
}

plugin_targets() {
  local install_target="$1"
  case "${install_target}" in
    proxy)
      printf '%s\n' "${TARGET_DATA_DIR}/proxy/plugins"
      ;;
    lobby)
      printf '%s\n' "${TARGET_DATA_DIR}/lobby/plugins"
      ;;
    survival)
      printf '%s\n' "${TARGET_DATA_DIR}/survival/plugins"
      ;;
    creative)
      printf '%s\n' "${TARGET_DATA_DIR}/creative/plugins"
      ;;
    all-paper)
      printf '%s\n' \
        "${TARGET_DATA_DIR}/lobby/plugins" \
        "${TARGET_DATA_DIR}/survival/plugins" \
        "${TARGET_DATA_DIR}/creative/plugins"
      ;;
    *)
      printf 'Unknown install target: %s\n' "${install_target}" >&2
      exit 1
      ;;
  esac
}

install_plugin_file() {
  local source_path="$1"
  local target_dir

  while IFS= read -r target_dir; do
    ensure_directory "${target_dir}"
    cp "${source_path}" "${target_dir}/"
  done
}

{
  read -r _
  while IFS=',' read -r plugin_id version install_target file_name source_url sha256 manual_source notes; do
    [[ -z "${plugin_id}" ]] && continue

    printf 'Syncing plugin %s (%s)\n' "${plugin_id}" "${version}"

    if [[ "${manual_source}" == "true" ]]; then
      if [[ ! -f "${MANUAL_DIR}/${file_name}" ]]; then
        printf 'Missing manual plugin jar: %s\n  Source: %s\n' "${MANUAL_DIR}/${file_name}" "${source_url}" >&2
        FAILURES=1
        continue
      fi

      install_plugin_file "${MANUAL_DIR}/${file_name}" < <(plugin_targets "${install_target}")
      continue
    fi

    DOWNLOAD_PATH="${TMP_DIR}/${file_name}"
    curl -fsSL "${source_url}" -o "${DOWNLOAD_PATH}"

    if [[ -z "${sha256}" ]]; then
      sha256="$(fetch_adjacent_sha256 "${source_url}")"
    fi

    if [[ -n "${sha256}" ]]; then
      printf '%s  %s\n' "${sha256}" "${DOWNLOAD_PATH}" | sha256sum -c -
    fi

    install_plugin_file "${DOWNLOAD_PATH}" < <(plugin_targets "${install_target}")
  done
} < "${MANIFEST_PATH}"

if [[ "${FAILURES}" != "0" ]]; then
  printf 'Plugin sync completed with missing manual sources.\n' >&2
  exit 1
fi

printf 'Plugin sync complete.\n'

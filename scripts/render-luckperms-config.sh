#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
require_envs TARGET_DATA_DIR LP_DB_HOST LP_DB_PORT MARIADB_DATABASE MARIADB_USER MARIADB_PASSWORD

render_template() {
  local template_path="$1"
  local output_path="$2"
  shift 2

  ensure_directory "$(dirname "${output_path}")"
  (
    export "$@"
    envsubst < "${template_path}" > "${output_path}"
  )
}

render_template \
  "${ROOT_DIR}/config/luckperms/proxy-config.yml.template" \
  "${TARGET_DATA_DIR}/proxy/plugins/luckperms/config.yml" \
  LP_DB_HOST LP_DB_PORT MARIADB_DATABASE MARIADB_USER MARIADB_PASSWORD

for server_name in lobby survival creative; do
  render_template \
    "${ROOT_DIR}/config/luckperms/paper-config.yml.template" \
    "${TARGET_DATA_DIR}/${server_name}/plugins/LuckPerms/config.yml" \
    LP_DB_HOST LP_DB_PORT MARIADB_DATABASE MARIADB_USER MARIADB_PASSWORD "LP_SERVER_CONTEXT=${server_name}"
done

printf 'LuckPerms configs rendered into %s\n' "${TARGET_DATA_DIR}"

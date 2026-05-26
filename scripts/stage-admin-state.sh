#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
ensure_command docker
require_envs TARGET_DATA_DIR MARIADB_DATABASE MARIADB_USER MARIADB_PASSWORD

OUT_DIR="${TARGET_DATA_DIR}/proxy/admin-state"
TIMESTAMP="$(date +%F_%H%M%S)"

ensure_directory "${OUT_DIR}"

admin_compose exec -T mariadb mariadb-dump \
  --single-transaction \
  --skip-lock-tables \
  -u"${MARIADB_USER}" \
  -p"${MARIADB_PASSWORD}" \
  "${MARIADB_DATABASE}" > "${OUT_DIR}/luckperms-${TIMESTAMP}.sql"

cp "${ROOT_DIR}/plugins/manifest.csv" "${OUT_DIR}/plugins-manifest.csv"
cp "${ROOT_DIR}/docs/permissions-bootstrap.md" "${OUT_DIR}/permissions-bootstrap.md"
cp "${ROOT_DIR}/docs/plugin-management.md" "${OUT_DIR}/plugin-management.md"
cp -R "${ROOT_DIR}/config/console" "${OUT_DIR}/console-state"

if [[ -f "${ROOT_DIR}/data/console/console.db" ]]; then
  cp "${ROOT_DIR}/data/console/console.db" "${OUT_DIR}/console.db"
fi

if [[ -d "${TARGET_DATA_DIR}/proxy/plugins/luckperms" ]]; then
  ensure_directory "${OUT_DIR}/proxy-luckperms"
  cp -R "${TARGET_DATA_DIR}/proxy/plugins/luckperms/." "${OUT_DIR}/proxy-luckperms/"
fi

for server_name in lobby survival creative; do
  if [[ -d "${TARGET_DATA_DIR}/${server_name}/plugins/LuckPerms" ]]; then
    ensure_directory "${OUT_DIR}/${server_name}-LuckPerms"
    cp -R "${TARGET_DATA_DIR}/${server_name}/plugins/LuckPerms/." "${OUT_DIR}/${server_name}-LuckPerms/"
  fi
done

printf 'Admin state staged at %s\n' "${OUT_DIR}"

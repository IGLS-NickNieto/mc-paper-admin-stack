#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_PATH="${ROOT_DIR}/config/olivetin/config.yaml.template"
OUTPUT_DIR="${ROOT_DIR}/data/olivetin/config"
OUTPUT_PATH="${OUTPUT_DIR}/config.yaml"

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    printf 'Missing required environment variable: %s\n' "${name}" >&2
    exit 1
  fi
}

hash_password() {
  local password="$1"
  local salt
  salt="$(openssl rand -base64 16)"
  printf '%s' "${password}" | argon2 "${salt}" -id -t 4 -m 16 -p 6 -l 32 -e
}

require_env OLIVETIN_MOD_USERNAME
require_env OLIVETIN_MOD_PASSWORD
require_env OLIVETIN_ADMIN_USERNAME
require_env OLIVETIN_ADMIN_PASSWORD
require_env OLIVETIN_PAGE_TITLE

MOD_PASSWORD_HASH="$(hash_password "${OLIVETIN_MOD_PASSWORD}")"
ADMIN_PASSWORD_HASH="$(hash_password "${OLIVETIN_ADMIN_PASSWORD}")"
export MOD_PASSWORD_HASH ADMIN_PASSWORD_HASH

mkdir -p "${OUTPUT_DIR}"
envsubst < "${TEMPLATE_PATH}" > "${OUTPUT_PATH}"

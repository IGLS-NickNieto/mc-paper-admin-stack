#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/minecraft-admin}"
TARGET_STACK_ROOT_DEFAULT="${TARGET_STACK_ROOT:-/opt/minecraft}"
BACKUP_COMPANION_ROOT_DEFAULT="${BACKUP_COMPANION_ROOT:-/opt/minecraft-backup-google-drive}"
APP_USER="${SUDO_USER:-$USER}"
ENABLE_GIT_SYNC_ON_BOOT_DEFAULT="${ENABLE_GIT_SYNC_ON_BOOT:-1}"
ENABLE_IMAGE_PULL_ON_BOOT_DEFAULT="${ENABLE_IMAGE_PULL_ON_BOOT:-1}"

if ! command -v sudo >/dev/null 2>&1; then
  echo "This script expects sudo to be available." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_GROUP="$(id -gn "${APP_USER}")"

run_as_app_user() {
  sudo -u "${APP_USER}" "$@"
}

is_interactive() {
  [[ -r /dev/tty && -w /dev/tty ]]
}

read_env_value() {
  local file="$1"
  local key="$2"
  local raw_value

  if [[ ! -f "${file}" ]]; then
    return 0
  fi

  raw_value="$(sed -n "s#^${key}=##p" "${file}" | tail -n1)"
  if [[ -z "${raw_value}" ]]; then
    return 0
  fi

  python3 -c 'import shlex, sys; value = sys.argv[1]; parsed = shlex.split(value, posix=True); print(parsed[0] if parsed else "")' "${raw_value}"
}

escape_sed_replacement() {
  printf '%s' "$1" | sed -e 's/[\/&]/\\&/g'
}

value_is_placeholder() {
  local value="$1"
  case "${value}" in
    ""|change-me-*|CHANGE_ME_* )
      return 0
      ;;
  esac
  return 1
}

detect_git_repo_url() {
  if [[ -d "${ROOT_DIR}/.git" ]]; then
    git -C "${ROOT_DIR}" config --get remote.origin.url 2>/dev/null || true
  fi
}

detect_git_ref() {
  local branch=""

  if [[ -d "${ROOT_DIR}/.git" ]]; then
    branch="$(git -C "${ROOT_DIR}" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    if [[ "${branch}" == "HEAD" ]]; then
      branch="$(git -C "${ROOT_DIR}" describe --tags --exact-match 2>/dev/null || true)"
    fi
  fi

  if [[ "${branch}" == "HEAD" ]]; then
    branch=""
  fi

  printf '%s\n' "${branch}"
}

detect_remote_default_ref() {
  local repo_url="$1"
  local remote_head=""

  remote_head="$(git ls-remote --symref "${repo_url}" HEAD 2>/dev/null | sed -n 's#^ref: refs/heads/##p' | awk 'NR==1 {print $1}')"
  printf '%s\n' "${remote_head}"
}

sync_repo_snapshot_from_git() {
  local repo_url="$1"
  local ref="$2"
  local temp_dir
  local default_ref

  temp_dir="$(run_as_app_user mktemp -d)"

  if run_as_app_user git clone --depth 1 --branch "${ref}" "${repo_url}" "${temp_dir}/repo"; then
    :
  else
    default_ref="$(detect_remote_default_ref "${repo_url}")"
    if [[ -n "${default_ref}" && "${default_ref}" != "${ref}" ]]; then
      echo "Git ref ${ref} was not found; falling back to remote default branch ${default_ref}..."
      run_as_app_user git clone --depth 1 --branch "${default_ref}" "${repo_url}" "${temp_dir}/repo"
      ref="${default_ref}"
    else
      echo "Unable to clone ${repo_url} using ref ${ref}." >&2
      exit 1
    fi
  fi

  run_as_app_user rsync -a --delete \
    --exclude '.git/' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude 'data/' \
    --exclude 'plugins/manual/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '.mypy_cache/' \
    --exclude '.ruff_cache/' \
    "${temp_dir}/repo/" "${APP_DIR}/"

  run_as_app_user rm -rf "${temp_dir}"
}

upsert_env_var() {
  local file="$1"
  local key="$2"
  local value="$3"
  local quoted_value

  printf -v quoted_value '%q' "${value}"
  quoted_value="$(escape_sed_replacement "${quoted_value}")"

  if grep -q "^${key}=" "${file}"; then
    run_as_app_user sed -i "s#^${key}=.*#${key}=${quoted_value}#" "${file}"
  else
    run_as_app_user sh -c 'printf "%s=%s\n" "$1" "$2" >> "$3"' _ "${key}" "${quoted_value}" "${file}"
  fi
}

resolve_setting_or_default() {
  local key="$1"
  local default_value="$2"
  local env_value file_value

  env_value="${!key:-}"
  if [[ -n "${env_value}" ]] && ! value_is_placeholder "${env_value}"; then
    printf '%s\n' "${env_value}"
    return 0
  fi

  file_value="$(read_env_value "${APP_DIR}/.env" "${key}")"
  if [[ -n "${file_value}" ]] && ! value_is_placeholder "${file_value}"; then
    printf '%s\n' "${file_value}"
    return 0
  fi

  printf '%s\n' "${default_value}"
}

prompt_for_setting() {
  local key="$1"
  local prompt_text="$2"
  local default_value="$3"
  local hidden="${4:-0}"
  local env_value file_value prompt_suffix value

  env_value="${!key:-}"
  if [[ -n "${env_value}" ]] && ! value_is_placeholder "${env_value}"; then
    printf '%s\n' "${env_value}"
    return 0
  fi

  file_value="$(read_env_value "${APP_DIR}/.env" "${key}")"
  if [[ -n "${file_value}" ]] && ! value_is_placeholder "${file_value}"; then
    printf '%s\n' "${file_value}"
    return 0
  fi

  if ! is_interactive; then
    if [[ -n "${default_value}" ]]; then
      printf '%s\n' "${default_value}"
      return 0
    fi

    echo "Missing required ${key}. Re-run scripts/bootstrap-sidecar.sh interactively or set ${key} in the environment or .env." >&2
    exit 1
  fi

  prompt_suffix=""
  if [[ -n "${default_value}" ]]; then
    prompt_suffix=" [${default_value}]"
  fi

  while true; do
    if [[ "${hidden}" == "1" ]]; then
      read -r -s -p "${prompt_text}${prompt_suffix}: " value </dev/tty >/dev/tty
      printf '\n' >/dev/tty
    else
      read -r -p "${prompt_text}${prompt_suffix}: " value </dev/tty >/dev/tty
    fi

    if [[ -z "${value}" && -n "${default_value}" ]]; then
      value="${default_value}"
    fi

    if [[ -n "${value}" ]]; then
      printf '%s\n' "${value}"
      return 0
    fi

    echo "${key} cannot be empty." >&2
  done
}

generate_secret() {
  python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(24))
PY
}

detect_vm_host() {
  hostname -f 2>/dev/null || hostname 2>/dev/null || true
}

detect_vm_lan_ip() {
  hostname -I 2>/dev/null | awk 'NR==1 {print $1}'
}

install_startup_refresh_service() {
  if [[ "${ENABLE_GIT_SYNC_ON_BOOT_VALUE}" == "1" ]]; then
    if [[ -z "${GIT_REPO_URL}" ]]; then
      echo "ENABLE_GIT_SYNC_ON_BOOT=1 requires GIT_REPO_URL in .env or a Git clone with an origin remote." >&2
      exit 1
    fi

    echo "Installing boot-time admin refresh service..."
    sudo sed "s#/opt/minecraft-admin#${APP_DIR}#g" ops/systemd/minecraft-admin-startup-refresh.service | sudo tee /etc/systemd/system/minecraft-admin-startup-refresh.service >/dev/null
    sudo systemctl daemon-reload
    sudo systemctl enable minecraft-admin-startup-refresh.service
  else
    if [[ -f /etc/systemd/system/minecraft-admin-startup-refresh.service ]]; then
      echo "Disabling boot-time admin refresh service..."
      sudo systemctl disable minecraft-admin-startup-refresh.service >/dev/null 2>&1 || true
      sudo rm -f /etc/systemd/system/minecraft-admin-startup-refresh.service
      sudo systemctl daemon-reload
    fi
  fi
}

import_core_contract() {
  local export_script="${TARGET_STACK_ROOT_VALUE}/scripts/export-admin-target-env.sh"
  [[ -x "${export_script}" ]] || {
    echo "Missing core contract exporter: ${export_script}" >&2
    exit 1
  }

  while IFS= read -r line || [[ -n "${line}" ]]; do
    [[ "${line}" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] || continue
    upsert_env_var "${APP_DIR}/.env" "${line%%=*}" "${line#*=}"
  done < <("${export_script}")
}

echo "Installing admin-side base packages..."
sudo apt update
sudo apt install -y docker-compose-plugin gettext-base python3 python3-pip rsync git

echo "Preparing admin app directory..."
sudo install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 0775 "${APP_DIR}"

GIT_REPO_URL="${GIT_REPO_URL:-}"
GIT_REF="${GIT_REF:-}"

if [[ -z "${GIT_REPO_URL}" ]]; then
  GIT_REPO_URL="$(read_env_value "${APP_DIR}/.env" "GIT_REPO_URL")"
fi
if [[ -z "${GIT_REPO_URL}" ]]; then
  GIT_REPO_URL="$(detect_git_repo_url)"
fi

if [[ -z "${GIT_REF}" ]]; then
  GIT_REF="$(read_env_value "${APP_DIR}/.env" "GIT_REF")"
fi
if [[ -z "${GIT_REF}" ]]; then
  GIT_REF="$(detect_git_ref)"
fi
if [[ -z "${GIT_REF}" && -n "${GIT_REPO_URL}" ]]; then
  GIT_REF="$(detect_remote_default_ref "${GIT_REPO_URL}")"
fi
GIT_REF="${GIT_REF:-main}"

if [[ -n "${GIT_REPO_URL}" ]]; then
  echo "Syncing admin repo into ${APP_DIR} from ${GIT_REPO_URL} (${GIT_REF})..."
  sync_repo_snapshot_from_git "${GIT_REPO_URL}" "${GIT_REF}"
elif [[ "${ROOT_DIR}" != "${APP_DIR}" ]]; then
  echo "Syncing admin repo into ${APP_DIR}..."
  rsync -a --delete \
    --exclude '.git/' \
    --exclude '.env' \
    --exclude '.env.*' \
    --exclude 'data/' \
    --exclude 'plugins/manual/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '.mypy_cache/' \
    --exclude '.ruff_cache/' \
    "${ROOT_DIR}/" "${APP_DIR}/"
fi

echo "Normalizing admin directory ownership and permissions..."
sudo chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
sudo find "${APP_DIR}" -type d -exec chmod u+rwx {} +
sudo find "${APP_DIR}" -type f -exec chmod u+rw {} +

cd "${APP_DIR}"

if [[ ! -f .env ]]; then
  run_as_app_user cp .env.example .env
fi

TARGET_STACK_ROOT_VALUE="$(prompt_for_setting "TARGET_STACK_ROOT" "Core stack root" "${TARGET_STACK_ROOT_DEFAULT}")"
BACKUP_COMPANION_ROOT_VALUE="$(resolve_setting_or_default "BACKUP_COMPANION_ROOT" "${BACKUP_COMPANION_ROOT_DEFAULT}")"
upsert_env_var .env "TARGET_STACK_ROOT" "${TARGET_STACK_ROOT_VALUE}"
upsert_env_var .env "BACKUP_COMPANION_ROOT" "${BACKUP_COMPANION_ROOT_VALUE}"

import_core_contract

LP_DB_HOST_DEFAULT="$(detect_vm_lan_ip)"
if [[ -z "${LP_DB_HOST_DEFAULT}" ]]; then
  LP_DB_HOST_DEFAULT="$(detect_vm_host)"
fi
LP_DB_HOST_VALUE="$(prompt_for_setting "LP_DB_HOST" "LuckPerms MariaDB host visible to the core containers" "${LP_DB_HOST_DEFAULT}")"
ENABLE_GIT_SYNC_ON_BOOT_VALUE="$(resolve_setting_or_default "ENABLE_GIT_SYNC_ON_BOOT" "${ENABLE_GIT_SYNC_ON_BOOT_DEFAULT}")"
ENABLE_IMAGE_PULL_ON_BOOT_VALUE="$(resolve_setting_or_default "ENABLE_IMAGE_PULL_ON_BOOT" "${ENABLE_IMAGE_PULL_ON_BOOT_DEFAULT}")"

upsert_env_var .env "TZ" "$(resolve_setting_or_default "TZ" "America/New_York")"
upsert_env_var .env "ADMIN_BIND_IP" "$(resolve_setting_or_default "ADMIN_BIND_IP" "127.0.0.1")"
upsert_env_var .env "GIT_REPO_URL" "${GIT_REPO_URL}"
upsert_env_var .env "GIT_REF" "${GIT_REF}"
upsert_env_var .env "ENABLE_GIT_SYNC_ON_BOOT" "${ENABLE_GIT_SYNC_ON_BOOT_VALUE}"
upsert_env_var .env "ENABLE_IMAGE_PULL_ON_BOOT" "${ENABLE_IMAGE_PULL_ON_BOOT_VALUE}"
upsert_env_var .env "BACKUP_COMPANION_ROOT" "${BACKUP_COMPANION_ROOT_VALUE}"
upsert_env_var .env "LP_DB_HOST" "${LP_DB_HOST_VALUE}"

for key in \
  FILEBROWSER_ADMIN_USER \
  OLIVETIN_MOD_USERNAME \
  OLIVETIN_ADMIN_USERNAME \
  CONSOLE_ADMIN_USER \
  CONSOLE_MOD_USER \
  FILEBROWSER_PORTAL_NAME \
  OLIVETIN_PAGE_TITLE \
  CONSOLE_PAGE_TITLE \
  MARIADB_DATABASE \
  MARIADB_USER \
  MARIADB_BIND_IP \
  MARIADB_PORT \
  LP_DB_PORT; do
  upsert_env_var .env "${key}" "$(resolve_setting_or_default "${key}" "$(read_env_value .env.example "${key}")")"
done

for key in \
  FILEBROWSER_ADMIN_PASSWORD \
  OLIVETIN_MOD_PASSWORD \
  OLIVETIN_ADMIN_PASSWORD \
  CONSOLE_ADMIN_PASSWORD \
  CONSOLE_MOD_PASSWORD \
  CONSOLE_SESSION_SECRET \
  MARIADB_PASSWORD \
  MARIADB_ROOT_PASSWORD; do
  current_value="$(resolve_setting_or_default "${key}" "")"
  if value_is_placeholder "${current_value}"; then
    current_value="$(generate_secret)"
  fi
  if [[ -z "${current_value}" ]]; then
    current_value="$(generate_secret)"
  fi
  upsert_env_var .env "${key}" "${current_value}"
done

set -a
# shellcheck disable=SC1091
source .env
set +a

chmod +x scripts/*.sh

install_startup_refresh_service

echo "Applying admin desired state..."
run_as_app_user ./scripts/apply-target-state.sh

cat <<EOF

Admin bootstrap complete.

Project dir:  ${APP_DIR}
Core stack:   ${TARGET_STACK_ROOT_VALUE}
Backup repo:  ${BACKUP_COMPANION_ROOT_VALUE}
LP DB host:   ${LP_DB_HOST_VALUE}

Useful checks:
  docker compose ps
  docker compose logs -f console
  ./scripts/validate-target.sh
  ./scripts/reconcile-permissions.sh
EOF

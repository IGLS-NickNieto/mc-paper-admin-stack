#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
require_envs TARGET_PROXY_CONTAINER
python "${SCRIPT_DIR}/reconcile_permissions.py" "$@"

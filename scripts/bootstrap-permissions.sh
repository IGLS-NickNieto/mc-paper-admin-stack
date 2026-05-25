#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/lib/common.sh"

load_admin_env
ensure_command docker
require_envs TARGET_PROXY_CONTAINER

send_proxy_console() {
  docker exec --user 1000 "${TARGET_PROXY_CONTAINER}" mc-send-to-console "$@"
}

lpv() {
  send_proxy_console lpv "$@"
}

assign_group_csv() {
  local raw_csv="$1"
  local group_name="$2"
  local player

  csv_list_to_array "${raw_csv}"
  for player in "${CSV_LIST_RESULT[@]}"; do
    [[ -z "${player}" ]] && continue
    lpv user "${player}" parent add "${group_name}" >/dev/null
  done
}

printf 'Bootstrapping LuckPerms groups through %s\n' "${TARGET_PROXY_CONTAINER}"

lpv creategroup guest >/dev/null || true
lpv creategroup member >/dev/null || true
lpv creategroup mod >/dev/null || true
lpv creategroup admin >/dev/null || true

lpv group guest setweight 10 >/dev/null || true
lpv group member setweight 20 >/dev/null || true
lpv group mod setweight 30 >/dev/null || true
lpv group admin setweight 40 >/dev/null || true

lpv group default parent add guest >/dev/null || true
lpv group member parent add guest >/dev/null || true
lpv group mod parent add member >/dev/null || true
lpv group admin parent add mod >/dev/null || true

lpv group guest meta setprefix 10 "[Guest] " >/dev/null || true
lpv group member meta setprefix 20 "[Member] " >/dev/null || true
lpv group mod meta setprefix 30 "[Mod] " >/dev/null || true
lpv group admin meta setprefix 40 "[Admin] " >/dev/null || true

for node in \
  essentials.msg \
  essentials.reply \
  essentials.rules \
  essentials.motd \
  essentials.list \
  essentials.spawn \
  essentials.home \
  essentials.sethome \
  essentials.delhome \
  quickconnect.server.lobby \
  quickconnect.server.survival \
  quickconnect.server.creative; do
  lpv group guest permission set "${node}" true >/dev/null || true
done

for node in \
  essentials.back \
  essentials.tpa \
  essentials.tpaccept \
  essentials.tpdeny \
  essentials.sethome.multiple.member; do
  lpv group member permission set "${node}" true >/dev/null || true
done

for node in \
  essentials.invsee \
  essentials.kick \
  essentials.mute \
  essentials.tempban \
  essentials.unban \
  essentials.socialspy \
  openinv.openinv; do
  lpv group mod permission set "${node}" true >/dev/null || true
done

for node in \
  luckperms.* \
  essentials.* \
  worldedit.* \
  worldguard.* \
  openinv.*; do
  lpv group admin permission set "${node}" true >/dev/null || true
done

assign_group_csv "${LP_BOOTSTRAP_MEMBER_PLAYERS:-}" member
assign_group_csv "${LP_BOOTSTRAP_MOD_PLAYERS:-}" mod
assign_group_csv "${LP_BOOTSTRAP_ADMIN_PLAYERS:-}" admin

lpv sync >/dev/null || true

printf 'LuckPerms bootstrap applied.\n'

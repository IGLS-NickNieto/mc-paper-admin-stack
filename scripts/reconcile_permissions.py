#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def send_proxy_console(target_proxy_container: str, *args: str) -> None:
    subprocess.run(
        ["docker", "exec", "--user", "1000", target_proxy_container, "mc-send-to-console", "lpv", *args],
        check=True,
        capture_output=True,
        text=True,
    )


def csv_env_players(name: str) -> list[str]:
    return [value.strip() for value in os.environ.get(name, "").split(",") if value.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    state_file = Path(args.state_file) if args.state_file else Path(__file__).resolve().parents[1] / "config" / "console" / "perks.json"
    target_proxy_container = os.environ["TARGET_PROXY_CONTAINER"]
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    groups = payload["perks"]["groups"] if "perks" in payload else payload["groups"]
    players_state = payload.get("players", {}).get("players", [])

    managed_permissions = sorted({permission for group in groups.values() for permission in group.get("permissions", [])})
    managed_groups = list(groups.keys())
    managed_perk_nodes = sorted(
        {
            permission
            for perk in payload.get("perks", {}).get("perk_bundles", {}).values()
            for permission in perk.get("permissions", [])
        }
    )

    for group_name in managed_groups:
        send_proxy_console(target_proxy_container, "creategroup", group_name)
        send_proxy_console(target_proxy_container, "group", group_name, "setweight", str(groups[group_name]["weight"]))
        send_proxy_console(target_proxy_container, "group", group_name, "meta", "setprefix", str(groups[group_name]["weight"]), groups[group_name]["prefix"])
        for inherited in groups[group_name].get("inherits", []):
            send_proxy_console(target_proxy_container, "group", group_name, "parent", "add", inherited)

        for permission in managed_permissions:
            if permission not in groups[group_name].get("permissions", []):
                send_proxy_console(target_proxy_container, "group", group_name, "permission", "unset", permission)
        for permission in groups[group_name].get("permissions", []):
            send_proxy_console(target_proxy_container, "group", group_name, "permission", "set", permission, "true")

    send_proxy_console(target_proxy_container, "group", "default", "parent", "add", "guest")

    bootstrap_map = {
        "member": csv_env_players("LP_BOOTSTRAP_MEMBER_PLAYERS"),
        "mod": csv_env_players("LP_BOOTSTRAP_MOD_PLAYERS"),
        "admin": csv_env_players("LP_BOOTSTRAP_ADMIN_PLAYERS"),
    }
    for role_name, player_names in bootstrap_map.items():
        for player_name in player_names:
            players_state.append({"player_name": player_name, "roles": [role_name], "perks": [], "notes": "", "whitelisted": True})

    unique_players = {}
    for player in players_state:
        unique_players[player["player_name"]] = player

    perk_catalog = payload.get("perks", {}).get("perk_bundles", {})
    for player_name, player in unique_players.items():
        desired_roles = set(player.get("roles", []))
        for group_name in managed_groups:
            if group_name in desired_roles:
                send_proxy_console(target_proxy_container, "user", player_name, "parent", "add", group_name)
            else:
                send_proxy_console(target_proxy_container, "user", player_name, "parent", "remove", group_name)

        desired_perks = {
            permission
            for perk_name in player.get("perks", [])
            for permission in perk_catalog.get(perk_name, {}).get("permissions", [])
        }
        for permission in managed_perk_nodes:
            if permission in desired_perks:
                send_proxy_console(target_proxy_container, "user", player_name, "permission", "set", permission, "true")
            else:
                send_proxy_console(target_proxy_container, "user", player_name, "permission", "unset", permission)

    send_proxy_console(target_proxy_container, "sync")
    result = {"status": "success", "groups": managed_groups, "players": sorted(unique_players.keys())}
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print("LuckPerms reconcile applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

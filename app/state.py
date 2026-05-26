from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any


DEFAULT_STATE: dict[str, dict[str, Any]] = {
    "servers": {
        "profiles": {
            "lobby": {
                "display_name": "Lobby",
                "assigned_world_id": "lobby-hub",
                "whitelist_mode": "invite-only",
                "plugin_bundles": ["lobby-default"],
                "world_border": {
                    "enabled": True,
                    "radius_blocks": 2000,
                },
                "pregeneration_status": {
                    "state": "planned",
                    "last_run_at": "",
                    "notes": "Create a small protected lobby footprint only after backups pass.",
                },
                "maintenance_window": "Tuesday 03:00-04:00 America/New_York",
                "cleanup_notes": "Keep lobby entity counts low and avoid decorative lag sources.",
                "settings": {
                    "gamemode": "adventure",
                    "difficulty": "peaceful",
                    "force-gamemode": True,
                    "pvp": False,
                    "allow-nether": False,
                    "allow-flight": True,
                    "max-players": 20,
                    "view-distance": 6,
                    "simulation-distance": 4,
                },
            },
            "survival": {
                "display_name": "Survival",
                "assigned_world_id": "survival-main",
                "whitelist_mode": "invite-only",
                "plugin_bundles": ["survival-default"],
                "world_border": {
                    "enabled": True,
                    "radius_blocks": 12000,
                },
                "pregeneration_status": {
                    "state": "planned",
                    "last_run_at": "",
                    "notes": "Run Chunky after the baseline Bedrock path is stable.",
                },
                "maintenance_window": "Tuesday 03:00-04:00 America/New_York",
                "cleanup_notes": "Prune unused chunks only from restored copies first.",
                "settings": {
                    "gamemode": "survival",
                    "difficulty": "hard",
                    "force-gamemode": False,
                    "pvp": True,
                    "allow-nether": True,
                    "allow-flight": False,
                    "max-players": 20,
                    "view-distance": 8,
                    "simulation-distance": 6,
                },
            },
            "creative": {
                "display_name": "Creative",
                "assigned_world_id": "creative-plots",
                "whitelist_mode": "invite-only",
                "plugin_bundles": ["creative-default"],
                "world_border": {
                    "enabled": True,
                    "radius_blocks": 8000,
                },
                "pregeneration_status": {
                    "state": "planned",
                    "last_run_at": "",
                    "notes": "Pregenerate the plots world after world border approval.",
                },
                "maintenance_window": "Tuesday 03:00-04:00 America/New_York",
                "cleanup_notes": "Watch armor stands, item frames, and plot junk accumulation.",
                "settings": {
                    "gamemode": "creative",
                    "difficulty": "peaceful",
                    "force-gamemode": True,
                    "pvp": False,
                    "allow-nether": False,
                    "allow-flight": True,
                    "max-players": 20,
                    "view-distance": 8,
                    "simulation-distance": 6,
                },
            },
        }
    },
    "worlds": {
        "worlds": [
            {
                "world_id": "lobby-hub",
                "display_name": "Main Lobby Hub",
                "artifact_path": "world-library/lobby-hub.zip",
                "source_kind": "archive",
                "checksum": "",
                "notes": "Protected spawn hub world.",
                "compatibility_tags": ["lobby"],
            },
            {
                "world_id": "survival-main",
                "display_name": "Main Survival World",
                "artifact_path": "world-library/survival-main.zip",
                "source_kind": "archive",
                "checksum": "",
                "notes": "Primary survival world.",
                "compatibility_tags": ["survival"],
            },
            {
                "world_id": "creative-plots",
                "display_name": "Creative Plots",
                "artifact_path": "world-library/creative-plots.zip",
                "source_kind": "archive",
                "checksum": "",
                "notes": "Creative plots world.",
                "compatibility_tags": ["creative"],
            },
        ]
    },
    "plugins": {
        "catalog": [
            {
                "plugin_id": "luckperms_velocity",
                "version": "5.5.50",
                "file_name": "LuckPerms-Velocity-5.5.50.jar",
                "source_url": "https://luckperms.net/download",
                "sha256": "",
                "manual_source": True,
                "install_target": "proxy",
                "description": "LuckPerms on Velocity.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "exohub",
                "version": "1.0.0",
                "file_name": "ExoHub-1.0.0.jar",
                "source_url": "https://modrinth.com/plugin/exohub",
                "sha256": "",
                "manual_source": True,
                "install_target": "proxy",
                "description": "Velocity /hub support.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "luckperms_paper",
                "version": "5.5.50",
                "file_name": "LuckPerms-Bukkit-5.5.50.jar",
                "source_url": "https://luckperms.net/download",
                "sha256": "",
                "manual_source": True,
                "install_target": "all-paper",
                "description": "LuckPerms on Paper backends.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "essentialsx",
                "version": "2.21.2",
                "file_name": "EssentialsX-2.21.2.jar",
                "source_url": "https://repo.essentialsx.net/releases/net/essentialsx/EssentialsX/2.21.2/EssentialsX-2.21.2.jar",
                "sha256": "",
                "manual_source": False,
                "install_target": "all-paper",
                "description": "Core utility commands.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "essentialsx_spawn",
                "version": "2.21.2",
                "file_name": "EssentialsXSpawn-2.21.2.jar",
                "source_url": "https://repo.essentialsx.net/releases/net/essentialsx/EssentialsXSpawn/2.21.2/EssentialsXSpawn-2.21.2.jar",
                "sha256": "",
                "manual_source": False,
                "install_target": "lobby",
                "description": "Lobby spawn management.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "worldedit",
                "version": "7.4.3",
                "file_name": "worldedit-bukkit-7.4.3.jar",
                "source_url": "https://worldedit.enginehub.org/en/latest/install/",
                "sha256": "",
                "manual_source": True,
                "install_target": "lobby",
                "description": "World editing for lobby staff.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "worldguard",
                "version": "7.0.16",
                "file_name": "worldguard-bukkit-7.0.16.jar",
                "source_url": "https://worldguard.enginehub.org/en/latest/install/",
                "sha256": "",
                "manual_source": True,
                "install_target": "lobby",
                "description": "Lobby protection regions.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "quickconnect",
                "version": "1.0.2",
                "file_name": "QuickConnect-1.0.2.jar",
                "source_url": "https://modrinth.com/plugin/quickconnect-utility/version/wMX1NaWC",
                "sha256": "",
                "manual_source": True,
                "install_target": "lobby",
                "description": "Server selector UI.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "openinv",
                "version": "0.4.0",
                "file_name": "OpenInv.jar",
                "source_url": "https://www.spigotmc.org/threads/open-inventory.715860/",
                "sha256": "",
                "manual_source": True,
                "install_target": "all-paper",
                "description": "Staff inventory access.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "spark",
                "version": "1.10.172",
                "file_name": "spark-1.10.172-paper.jar",
                "source_url": "https://spark.lucko.me/download",
                "sha256": "",
                "manual_source": True,
                "install_target": "all-paper",
                "description": "Performance profiling and MSPT/TPS diagnostics.",
                "bedrock_risk_level": "safe",
                "rollout_phase": "approved-now",
                "owner": "admin-stack",
            },
            {
                "plugin_id": "bluemap",
                "version": "5.20",
                "file_name": "bluemap-5.20-paper.jar",
                "source_url": "https://bluemap.bluecolored.de/",
                "sha256": "",
                "manual_source": True,
                "install_target": "all-paper",
                "description": "Map rendering. Delay until cleanup and storage policy are proven.",
                "bedrock_risk_level": "medium",
                "rollout_phase": "optional-later",
                "owner": "admin-stack",
            },
        ],
        "bundles": {
            "proxy-default": ["luckperms_velocity", "exohub"],
            "lobby-default": ["luckperms_paper", "essentialsx", "essentialsx_spawn", "worldedit", "worldguard", "quickconnect", "openinv"],
            "survival-default": ["luckperms_paper", "essentialsx", "openinv"],
            "creative-default": ["luckperms_paper", "essentialsx", "openinv"],
        },
    },
    "perks": {
        "groups": {
            "guest": {
                "inherits": [],
                "weight": 10,
                "prefix": "[Guest] ",
                "permissions": [
                    "essentials.msg",
                    "essentials.reply",
                    "essentials.rules",
                    "essentials.motd",
                    "essentials.list",
                    "essentials.spawn",
                    "essentials.home",
                    "essentials.sethome",
                    "essentials.delhome",
                    "quickconnect.server.lobby",
                    "quickconnect.server.survival",
                    "quickconnect.server.creative",
                ],
            },
            "member": {
                "inherits": ["guest"],
                "weight": 20,
                "prefix": "[Member] ",
                "permissions": [
                    "essentials.back",
                    "essentials.tpa",
                    "essentials.tpaccept",
                    "essentials.tpdeny",
                    "essentials.sethome.multiple.member",
                ],
            },
            "mod": {
                "inherits": ["member"],
                "weight": 30,
                "prefix": "[Mod] ",
                "permissions": [
                    "essentials.invsee",
                    "essentials.kick",
                    "essentials.mute",
                    "essentials.tempban",
                    "essentials.unban",
                    "essentials.socialspy",
                    "openinv.openinv",
                ],
            },
            "admin": {
                "inherits": ["mod"],
                "weight": 40,
                "prefix": "[Admin] ",
                "permissions": ["luckperms.*", "essentials.*", "worldedit.*", "worldguard.*", "openinv.*"],
            },
        },
        "perk_bundles": {
            "builder": {
                "description": "Lightweight build utility perks.",
                "permissions": ["worldedit.selection.pos", "worldedit.selection.hpos"],
            }
        },
    },
    "players": {
        "players": [
            {
                "player_name": "ExamplePlayer",
                "roles": ["member"],
                "perks": ["builder"],
                "notes": "Seed record for the console.",
                "whitelisted": True,
            }
        ]
    },
    "whitelist": {
        "mode": "invite-only",
        "entries": [
            {
                "player_name": "ExamplePlayer",
                "note": "Initial beta player.",
            }
        ],
    },
    "policy": {
        "approved_features_now": [
            "Velocity proxy",
            "Geyser and Floodgate on the proxy",
            "LuckPerms",
            "Spark profiling",
            "safe Vanilla Tweaks datapacks only",
            "world border and pregeneration planning",
            "boring verified backups and restore drills",
        ],
        "delayed_features": [
            "custom resource packs",
            "custom item models",
            "custom sounds",
            "voice chat",
            "map rendering",
            "large public-server plugin stacks",
        ],
        "cleanup_policy": {
            "maintenance_window": "Tuesday 03:00-04:00 America/New_York",
            "manual_chunk_pruning_requires_restore_test": True,
            "log_retention_days": 14,
            "spark_report_retention_days": 14,
            "crash_report_retention_days": 30,
            "entity_farm_limits": [
                "avoid giant villager halls without caps",
                "avoid oversized item-frame walls",
                "avoid always-on redstone clocks",
            ],
            "disk_growth_signals": {
                "data_dir_warn_percent": 80,
                "backups_dir_warn_percent": 85,
                "suspicious_growth_gb": 5,
            },
        },
        "observability": {
            "backup_freshness_target_hours": 24,
            "alerts": [
                "proxy process down",
                "backend process down",
                "TPS below 18 sustained",
                "MSPT above 50 sustained",
                "disk above 80%",
                "backup failure",
                "Java TCP 25565 unreachable",
                "Bedrock UDP 19132 unreachable",
            ],
        },
    },
    "datapacks": {
        "safe_now": [
            {
                "name": "AFK Display",
                "bedrock_risk_level": "safe",
                "notes": "Vanilla-friendly scoreboard-style utility.",
            },
            {
                "name": "Anti Enderman Grief",
                "bedrock_risk_level": "safe",
                "notes": "Gameplay cleanup with no custom assets.",
            },
            {
                "name": "Multiplayer Sleep",
                "bedrock_risk_level": "safe",
                "notes": "Low-risk vanilla quality-of-life change.",
            },
            {
                "name": "Double Shulker Shells",
                "bedrock_risk_level": "safe",
                "notes": "Loot-table tweak only.",
            },
            {
                "name": "More Mob Heads",
                "bedrock_risk_level": "safe",
                "notes": "Vanilla item outcomes only.",
            },
            {
                "name": "Player Head Drops",
                "bedrock_risk_level": "safe",
                "notes": "Vanilla-compatible loot-table behavior.",
            },
            {
                "name": "Silence Mobs",
                "bedrock_risk_level": "safe",
                "notes": "Utility-only behavior change.",
            },
            {
                "name": "Track Statistics",
                "bedrock_risk_level": "safe",
                "notes": "Operational scoreboard/stat tracking.",
            },
            {
                "name": "Wandering Trades",
                "bedrock_risk_level": "safe",
                "notes": "Vanilla trade-table tweak.",
            },
            {
                "name": "Durability Ping",
                "bedrock_risk_level": "safe",
                "notes": "Safe if kept vanilla and text-only.",
            },
        ],
        "delayed": [
            {
                "name": "Coordinates HUD",
                "bedrock_risk_level": "medium",
                "notes": "Only if it behaves cleanly for Bedrock clients.",
            },
            {
                "name": "Nether Portal Coords",
                "bedrock_risk_level": "medium",
                "notes": "Add only after staged testing.",
            },
            {
                "name": "Universal Dyeing",
                "bedrock_risk_level": "medium",
                "notes": "Delay until baseline stability is proven.",
            },
        ],
    },
}


STATE_FILES = {
    "servers": "servers.json",
    "worlds": "worlds.json",
    "plugins": "plugins.json",
    "perks": "perks.json",
    "players": "players.json",
    "whitelist": "whitelist.json",
    "policy": "policy.json",
    "datapacks": "datapacks.json",
}


def ensure_state_files(state_dir: Path) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    for name, filename in STATE_FILES.items():
        path = state_dir / filename
        if not path.exists():
            write_state_file(path, copy.deepcopy(DEFAULT_STATE[name]))


def read_state_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_state_file(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_all_state(state_dir: Path) -> dict[str, Any]:
    ensure_state_files(state_dir)
    return {name: read_state_file(state_dir / filename) for name, filename in STATE_FILES.items()}


def save_named_state(state_dir: Path, name: str, data: dict[str, Any]) -> None:
    filename = STATE_FILES[name]
    write_state_file(state_dir / filename, data)


def state_digest(state_payload: dict[str, Any]) -> str:
    encoded = json.dumps(state_payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

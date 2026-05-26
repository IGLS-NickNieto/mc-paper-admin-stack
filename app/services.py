from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import shutil
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import auth, db, state
from .config import Settings


ENV_KEY_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
SENSITIVE_ENV_FRAGMENTS = ("PASSWORD", "SECRET", "TOKEN", "PRIVATE", "CREDENTIAL", "RCLONE_CONFIG")


def ensure_runtime(settings: Settings) -> None:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    db.ensure_database(settings.database_path)
    state.ensure_state_files(settings.state_dir)


def env_value_is_sensitive(key: str) -> bool:
    upper_key = key.upper()
    return any(fragment in upper_key for fragment in SENSITIVE_ENV_FRAGMENTS)


def decode_env_value(raw_value: str) -> str:
    if raw_value == "":
        return ""
    try:
        parsed = shlex.split(raw_value, posix=True)
    except ValueError:
        return raw_value.strip("'\"")
    return parsed[0] if parsed else ""


def encode_env_value(value: str) -> str:
    return shlex.quote(value) if value else ""


def read_env_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def env_entries_from_lines(lines: list[str]) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in lines:
        match = ENV_KEY_PATTERN.match(line.rstrip("\r"))
        if match:
            values[match.group(1)] = decode_env_value(match.group(2))
    return values


def env_key_order(*line_sets: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for lines in line_sets:
        for line in lines:
            match = ENV_KEY_PATTERN.match(line.rstrip("\r"))
            if not match:
                continue
            key = match.group(1)
            if key not in seen:
                ordered.append(key)
                seen.add(key)
    return ordered


def env_target_roots(settings: Settings) -> dict[str, dict[str, Any]]:
    target_mount = Path(os.environ.get("MC_ADMIN_TARGET_ROOT_MOUNT", "/target/stack")).resolve()
    core_root = target_mount if target_mount.exists() else settings.target_stack_root
    return {
        "admin": {"label": "Admin Stack", "root": settings.repo_root},
        "core": {"label": "Core Stack", "root": core_root},
        "backup": {"label": "Backup Companion", "root": settings.backup_repo_root},
    }


def load_env_targets(settings: Settings) -> list[dict[str, Any]]:
    targets = []
    for target_id, target in env_target_roots(settings).items():
        root = Path(target["root"])
        env_path = root / ".env"
        example_path = root / ".env.example"
        env_lines = read_env_lines(env_path)
        example_lines = read_env_lines(example_path)
        values = env_entries_from_lines(env_lines)
        example_values = env_entries_from_lines(example_lines)
        keys = env_key_order(example_lines, env_lines)
        entries = []
        for key in keys:
            sensitive = env_value_is_sensitive(key)
            present = key in values
            value = values.get(key, example_values.get(key, ""))
            entries.append(
                {
                    "key": key,
                    "value": "" if sensitive else value,
                    "masked": sensitive and present and bool(values.get(key)),
                    "sensitive": sensitive,
                    "present": present,
                    "from_example": key not in values and key in example_values,
                }
            )
        targets.append(
            {
                "id": target_id,
                "label": target["label"],
                "root": str(root),
                "path": str(env_path),
                "example_path": str(example_path),
                "exists": env_path.exists(),
                "example_exists": example_path.exists(),
                "entries": entries,
            }
        )
    return targets


def env_target_by_id(settings: Settings, target_id: str) -> dict[str, Any]:
    targets = env_target_roots(settings)
    if target_id not in targets:
        raise KeyError(f"Unknown env target: {target_id}")
    return targets[target_id]


def save_env_target(settings: Settings, target_id: str, form_data: dict[str, str]) -> list[str]:
    target = env_target_by_id(settings, target_id)
    root = Path(target["root"])
    env_path = root / ".env"
    example_path = root / ".env.example"
    existing_lines = read_env_lines(env_path)
    example_lines = read_env_lines(example_path)
    base_lines = existing_lines if existing_lines else example_lines
    current_values = env_entries_from_lines(existing_lines)
    known_keys = env_key_order(example_lines, existing_lines)
    updates: dict[str, str] = {}

    for key in known_keys:
        field_name = f"env_{key}"
        if field_name not in form_data:
            continue
        submitted = form_data[field_name]
        if env_value_is_sensitive(key) and submitted == "" and key in current_values:
            continue
        updates[key] = submitted

    rendered_lines: list[str] = []
    updated_existing: set[str] = set()
    for line in base_lines:
        match = ENV_KEY_PATTERN.match(line.rstrip("\r"))
        if match and match.group(1) in updates:
            key = match.group(1)
            rendered_lines.append(f"{key}={encode_env_value(updates[key])}")
            updated_existing.add(key)
        else:
            rendered_lines.append(line.rstrip("\r"))

    for key, value in updates.items():
        if key not in updated_existing:
            rendered_lines.append(f"{key}={encode_env_value(value)}")

    env_path.parent.mkdir(parents=True, exist_ok=True)
    if env_path.exists():
        backup_path = env_path.with_name(f".env.backup-{datetime.now(tz=timezone.utc).strftime('%Y%m%d%H%M%S')}")
        shutil.copy2(env_path, backup_path)
    env_path.write_text("\n".join(rendered_lines).rstrip("\n") + "\n", encoding="utf-8")
    return sorted(updates.keys())


def save_first_run_credentials(
    settings: Settings,
    admin_username: str,
    admin_password: str,
    mod_username: str,
    mod_password: str,
) -> list[str]:
    env_lines = read_env_lines(settings.repo_root / ".env")
    env_values = env_entries_from_lines(env_lines)
    session_secret = env_values.get("CONSOLE_SESSION_SECRET", os.environ.get("CONSOLE_SESSION_SECRET", ""))
    if auth.value_needs_setup(session_secret):
        session_secret = secrets.token_urlsafe(32)

    updates = {
        "env_ENABLE_CONSOLE_FIRST_RUN_SETUP": "1",
        "env_CONSOLE_ADMIN_USER": admin_username,
        "env_CONSOLE_ADMIN_PASSWORD": admin_password,
        "env_CONSOLE_MOD_USER": mod_username,
        "env_CONSOLE_MOD_PASSWORD": mod_password,
        "env_CONSOLE_SESSION_SECRET": session_secret,
    }
    changed_keys = save_env_target(settings, "admin", updates)
    for key, value in updates.items():
        os.environ[key.removeprefix("env_")] = value
    return changed_keys


def list_local_archives(settings: Settings) -> list[dict[str, Any]]:
    daily_dir = settings.target_backups_dir / "daily"
    if not daily_dir.exists():
        return []
    archives = []
    for path in sorted(daily_dir.glob("minecraft-*.tar.gz"), reverse=True):
        stat = path.stat()
        archives.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        )
    return archives


def directory_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    total = 0
    for file_path in path.rglob("*"):
        if file_path.is_file():
            total += file_path.stat().st_size
    return total


def disk_growth_overview(settings: Settings) -> dict[str, Any]:
    data_usage = disk_usage_or_empty(settings.target_data_dir)
    backups_usage = disk_usage_or_empty(settings.target_backups_dir)
    return {
        "target_data_dir": str(settings.target_data_dir),
        "target_backups_dir": str(settings.target_backups_dir),
        "target_data_dir_size_bytes": directory_size_bytes(settings.target_data_dir),
        "target_backups_dir_size_bytes": directory_size_bytes(settings.target_backups_dir),
        "target_data_dir_total_bytes": data_usage.total,
        "target_data_dir_free_bytes": data_usage.free,
        "target_backups_dir_total_bytes": backups_usage.total,
        "target_backups_dir_free_bytes": backups_usage.free,
        "target_data_dir_exists": settings.target_data_dir.exists(),
        "target_backups_dir_exists": settings.target_backups_dir.exists(),
    }


def disk_usage_or_empty(path: Path) -> shutil._ntuple_diskusage:
    if path.exists():
        return shutil.disk_usage(path)
    for parent in path.parents:
        if parent.exists():
            return shutil.disk_usage(parent)
    return shutil._ntuple_diskusage(total=0, used=0, free=0)


def run_json_command(command: list[str], cwd: Path | None = None) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        return {"status": "error", "returncode": 127, "message": str(exc)}
    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"status": "success" if completed.returncode == 0 else "error", "stdout": stdout}
    else:
        payload = {"status": "success" if completed.returncode == 0 else "error"}
    payload["returncode"] = completed.returncode
    if stderr:
        payload["stderr"] = stderr
    if completed.returncode != 0 and payload.get("status") == "success":
        payload["status"] = "error"
    return payload


def enqueue_job(connection: sqlite3.Connection, job_type: str, created_by: str, payload: dict[str, Any]) -> int:
    cursor = connection.execute(
        "INSERT INTO jobs (job_type, payload_json, created_by) VALUES (?, ?, ?)",
        (job_type, json.dumps(payload, sort_keys=True), created_by),
    )
    db.add_audit_log(connection, created_by, "queue_job", {"job_type": job_type, "payload": payload})
    connection.commit()
    return int(cursor.lastrowid)


def list_jobs(connection: sqlite3.Connection, limit: int = 25) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT id, job_type, status, created_by, created_at, started_at, finished_at, log_text, result_json "
        "FROM jobs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def list_audit_logs(connection: sqlite3.Connection, limit: int = 25) -> list[sqlite3.Row]:
    return connection.execute(
        "SELECT actor, action, details_json, created_at FROM audit_logs ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def get_next_queued_job(connection: sqlite3.Connection) -> sqlite3.Row | None:
    row = connection.execute(
        "SELECT id, job_type, payload_json, created_by FROM jobs WHERE status = 'queued' ORDER BY id ASC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    connection.execute(
        "UPDATE jobs SET status = 'running', started_at = CURRENT_TIMESTAMP WHERE id = ?",
        (row["id"],),
    )
    connection.commit()
    return connection.execute("SELECT * FROM jobs WHERE id = ?", (row["id"],)).fetchone()


def append_job_log(connection: sqlite3.Connection, job_id: int, message: str) -> None:
    connection.execute(
        "UPDATE jobs SET log_text = log_text || ? || char(10) WHERE id = ?",
        (message, job_id),
    )
    connection.commit()


def finish_job(connection: sqlite3.Connection, job_id: int, status: str, result: dict[str, Any]) -> None:
    connection.execute(
        "UPDATE jobs SET status = ?, result_json = ?, finished_at = CURRENT_TIMESTAMP WHERE id = ?",
        (status, json.dumps(result, sort_keys=True), job_id),
    )
    connection.commit()


def build_plugin_install_plan(current_state: dict[str, Any]) -> dict[str, Any]:
    catalog = {entry["plugin_id"]: entry for entry in current_state["plugins"]["catalog"]}
    plans: dict[str, list[dict[str, Any]]] = {"proxy": [], "lobby": [], "survival": [], "creative": []}
    for profile_name, profile in current_state["servers"]["profiles"].items():
        plugin_ids: list[str] = []
        for bundle_name in profile.get("plugin_bundles", []):
            plugin_ids.extend(current_state["plugins"]["bundles"].get(bundle_name, []))
        unique_ids = list(dict.fromkeys(plugin_ids))
        plans[profile_name] = [catalog[plugin_id] for plugin_id in unique_ids if plugin_id in catalog]

    proxy_ids: list[str] = []
    for bundle_name in current_state["plugins"]["bundles"]:
        if bundle_name.startswith("proxy"):
            proxy_ids.extend(current_state["plugins"]["bundles"][bundle_name])
    plans["proxy"] = [catalog[plugin_id] for plugin_id in dict.fromkeys(proxy_ids) if plugin_id in catalog]
    return {"generated_at": datetime.now(tz=timezone.utc).isoformat(), "plans": plans}


def write_whitelist_file(settings: Settings, current_state: dict[str, Any]) -> list[str]:
    names = {entry["player_name"] for entry in current_state["whitelist"]["entries"]}
    for player in current_state["players"]["players"]:
        if player.get("whitelisted"):
            names.add(player["player_name"])
    ordered = sorted(names)
    settings.target_invite_players_file.parent.mkdir(parents=True, exist_ok=True)
    settings.target_invite_players_file.write_text("\n".join(ordered) + ("\n" if ordered else ""), encoding="utf-8")
    return ordered


def write_generated_files(settings: Settings, current_state: dict[str, Any]) -> dict[str, Any]:
    settings.generated_dir.mkdir(parents=True, exist_ok=True)
    plugin_plan = build_plugin_install_plan(current_state)
    plugin_plan_path = settings.generated_dir / "plugin-sync-plan.json"
    plugin_plan_path.write_text(json.dumps(plugin_plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    settings_payload_path = settings.generated_dir / "profile-settings.json"
    settings_payload_path.write_text(
        json.dumps(current_state["servers"]["profiles"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    permissions_payload_path = settings.generated_dir / "permissions-state.json"
    permissions_payload_path.write_text(
        json.dumps(
            {
                "perks": current_state["perks"],
                "players": current_state["players"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "plugin_plan_path": str(plugin_plan_path),
        "settings_payload_path": str(settings_payload_path),
        "permissions_payload_path": str(permissions_payload_path),
    }


def load_last_applied(settings: Settings) -> dict[str, Any] | None:
    path = settings.data_dir / "last-applied-state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_last_applied(settings: Settings, current_state: dict[str, Any]) -> None:
    path = settings.data_dir / "last-applied-state.json"
    path.write_text(json.dumps(current_state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def resolve_world_artifact(settings: Settings, world_id: str, current_state: dict[str, Any]) -> str:
    for world in current_state["worlds"]["worlds"]:
        if world["world_id"] == world_id:
            relative = world["artifact_path"].lstrip("/\\")
            return str(settings.target_data_dir / relative)
    raise KeyError(f"Unknown world_id: {world_id}")


def apply_desired_state(settings: Settings, connection: sqlite3.Connection, job_id: int) -> dict[str, Any]:
    current_state = state.load_all_state(settings.state_dir)
    generated = write_generated_files(settings, current_state)
    last_applied = load_last_applied(settings) or {}
    whitelist_names = write_whitelist_file(settings, current_state)

    append_job_log(connection, job_id, f"Prepared {len(whitelist_names)} whitelist entries.")

    sync_plugins = run_json_command(
        ["bash", str(settings.repo_root / "scripts" / "sync-plugins.sh"), "--plan", generated["plugin_plan_path"], "--json"]
    )
    append_job_log(connection, job_id, "Plugin sync completed.")

    render_permissions = run_json_command(["bash", str(settings.repo_root / "scripts" / "render-luckperms-config.sh")])
    append_job_log(connection, job_id, "LuckPerms config rendered.")

    reconcile_permissions = run_json_command(
        [
            "bash",
            str(settings.repo_root / "scripts" / "reconcile-permissions.sh"),
            "--state-file",
            generated["permissions_payload_path"],
            "--json",
        ]
    )
    append_job_log(connection, job_id, "LuckPerms permissions reconciled.")

    profile_results: dict[str, Any] = {}
    for profile_name, profile in current_state["servers"]["profiles"].items():
        previous_profile = last_applied.get("servers", {}).get("profiles", {}).get(profile_name, {})
        settings_changed = previous_profile.get("settings") != profile.get("settings")
        world_changed = previous_profile.get("assigned_world_id") != profile.get("assigned_world_id")
        if not (settings_changed or world_changed or not last_applied):
            profile_results[profile_name] = {"status": "skipped", "reason": "no changes"}
            continue

        command = [
            "bash",
            str(settings.target_stack_root / "scripts" / "admin-apply-profile.sh"),
            "--profile",
            profile_name,
            "--settings-file",
            generated["settings_payload_path"],
            "--json",
            "--restart",
        ]
        if world_changed or not last_applied:
            command.extend(["--world-archive", resolve_world_artifact(settings, profile["assigned_world_id"], current_state)])
        profile_results[profile_name] = run_json_command(command, cwd=settings.target_stack_root)
        append_job_log(connection, job_id, f"Applied profile {profile_name}.")

    whitelist_result = run_json_command(
        ["bash", str(settings.target_sync_whitelist_script), "--json"],
        cwd=settings.target_stack_root,
    )
    append_job_log(connection, job_id, "Whitelist sync completed.")

    save_last_applied(settings, current_state)
    return {
        "status": "success",
        "plugin_sync": sync_plugins,
        "render_luckperms": render_permissions,
        "reconcile_permissions": reconcile_permissions,
        "profiles": profile_results,
        "whitelist_sync": whitelist_result,
        "state_digest": state.state_digest(current_state),
    }


def execute_job(settings: Settings, connection: sqlite3.Connection, job_row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(job_row["payload_json"])
    job_type = job_row["job_type"]

    if job_type == "apply_state":
        return apply_desired_state(settings, connection, int(job_row["id"]))
    if job_type == "run_local_backup":
        return run_json_command(["bash", str(settings.repo_root / "scripts" / "run-backup-now.sh")])
    if job_type == "run_offsite_backup":
        return run_json_command(["bash", str(settings.backup_repo_root / "scripts" / "offsite-backup.sh"), "--json"])
    if job_type == "verify_backups":
        return run_json_command(["bash", str(settings.backup_repo_root / "scripts" / "backup-verify.sh"), "--json"])
    if job_type == "stage_restore":
        return run_json_command(
            [
                "bash",
                str(settings.backup_repo_root / "scripts" / "restore-to-staging.sh"),
                "--json",
                payload["source_ref"],
                payload.get("scope", "full"),
            ]
        )
    if job_type == "promote_rollback":
        command = [
            "bash",
            str(settings.backup_repo_root / "scripts" / "promote-rollback.sh"),
            "--json",
            payload["stage_path"],
            payload.get("scope", "full"),
        ]
        if payload.get("allow_playerdata_rollback"):
            command.append("--allow-playerdata-rollback")
        return run_json_command(command)
    if job_type == "operation":
        return run_json_command(["bash", str(settings.repo_root / "scripts" / "olive-action.sh"), payload["action"]])

    raise ValueError(f"Unsupported job type: {job_type}")


def import_world_archive(settings: Settings, uploaded_name: str, data: bytes, world_id: str, display_name: str, notes: str) -> None:
    target_name = f"{world_id}{Path(uploaded_name).suffix or '.zip'}"
    destination = settings.uploads_dir / target_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)

    checksum = ""
    if destination.suffix.lower() == ".zip":
        checksum = hashlib_for_file(destination)

    worlds_state = state.read_state_file(settings.state_dir / state.STATE_FILES["worlds"])
    worlds_state["worlds"] = [
        world for world in worlds_state["worlds"] if world["world_id"] != world_id
    ] + [
        {
            "world_id": world_id,
            "display_name": display_name,
            "artifact_path": f"world-library/{target_name}",
            "source_kind": "archive",
            "checksum": checksum,
            "notes": notes,
            "compatibility_tags": [],
        }
    ]
    worlds_state["worlds"] = sorted(worlds_state["worlds"], key=lambda item: item["world_id"])
    state.save_named_state(settings.state_dir, "worlds", worlds_state)


def hashlib_for_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_overview(settings: Settings) -> dict[str, Any]:
    payload = run_json_command(["bash", str(settings.backup_repo_root / "scripts" / "list-snapshots.sh"), "--json"])
    local_archives = list_local_archives(settings)
    payload["local_archives"] = local_archives
    payload["latest_local_archive_age_hours"] = None
    if local_archives:
        latest = datetime.fromisoformat(local_archives[0]["modified_at"])
        payload["latest_local_archive_age_hours"] = round(
            (datetime.now(tz=timezone.utc) - latest).total_seconds() / 3600,
            2,
        )
    return payload


def status_overview(settings: Settings) -> dict[str, Any]:
    return run_json_command(["bash", str(settings.target_stack_root / "scripts" / "admin-status.sh"), "--json"])


def stability_overview(settings: Settings) -> dict[str, Any]:
    current_state = state.load_all_state(settings.state_dir)
    status = status_overview(settings)
    snapshots = snapshot_overview(settings)
    disk = disk_growth_overview(settings)
    return {
        "state": current_state,
        "status": status,
        "snapshots": snapshots,
        "disk": disk,
    }


def update_server_profile(settings: Settings, profile_name: str, update: dict[str, Any]) -> None:
    servers_state = state.read_state_file(settings.state_dir / state.STATE_FILES["servers"])
    servers_state["profiles"][profile_name].update(update)
    state.save_named_state(settings.state_dir, "servers", servers_state)


def update_player_state(settings: Settings, player_name: str, role: str, whitelisted: bool, notes: str, perks: list[str]) -> None:
    players_state = state.read_state_file(settings.state_dir / state.STATE_FILES["players"])
    whitelist_state = state.read_state_file(settings.state_dir / state.STATE_FILES["whitelist"])
    players = [player for player in players_state["players"] if player["player_name"] != player_name]
    players.append(
        {
            "player_name": player_name,
            "roles": [role],
            "perks": perks,
            "notes": notes,
            "whitelisted": whitelisted,
        }
    )
    players_state["players"] = sorted(players, key=lambda item: item["player_name"].lower())
    state.save_named_state(settings.state_dir, "players", players_state)

    whitelist_entries = [entry for entry in whitelist_state["entries"] if entry["player_name"] != player_name]
    if whitelisted:
        whitelist_entries.append({"player_name": player_name, "note": notes})
    whitelist_state["entries"] = sorted(whitelist_entries, key=lambda item: item["player_name"].lower())
    state.save_named_state(settings.state_dir, "whitelist", whitelist_state)


def update_plugin_bundles(settings: Settings, profile_name: str, bundle_names: list[str]) -> None:
    servers_state = state.read_state_file(settings.state_dir / state.STATE_FILES["servers"])
    servers_state["profiles"][profile_name]["plugin_bundles"] = bundle_names
    state.save_named_state(settings.state_dir, "servers", servers_state)


def update_perk_bundle(settings: Settings, bundle_name: str, description: str, permissions_text: str) -> None:
    perks_state = state.read_state_file(settings.state_dir / state.STATE_FILES["perks"])
    permissions = [line.strip() for line in permissions_text.splitlines() if line.strip()]
    perks_state["perk_bundles"][bundle_name] = {"description": description, "permissions": permissions}
    state.save_named_state(settings.state_dir, "perks", perks_state)


def update_group_permissions(settings: Settings, group_name: str, permissions_text: str) -> None:
    perks_state = state.read_state_file(settings.state_dir / state.STATE_FILES["perks"])
    permissions = [line.strip() for line in permissions_text.splitlines() if line.strip()]
    perks_state["groups"][group_name]["permissions"] = permissions
    state.save_named_state(settings.state_dir, "perks", perks_state)


def newline_entries(raw_text: str) -> list[str]:
    return [line.strip() for line in raw_text.splitlines() if line.strip()]


def parse_datapack_lines(raw_text: str, default_risk: str) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for line in newline_entries(raw_text):
        parts = [part.strip() for part in line.split("|")]
        name = parts[0]
        risk = parts[1] if len(parts) > 1 and parts[1] else default_risk
        notes = parts[2] if len(parts) > 2 else ""
        entries.append({"name": name, "bedrock_risk_level": risk, "notes": notes})
    return entries


def update_policy_state(
    settings: Settings,
    approved_features_now: str,
    delayed_features: str,
    maintenance_window: str,
    entity_limits: str,
    log_retention_days: int,
    spark_report_retention_days: int,
    crash_report_retention_days: int,
    data_warn_percent: int,
    backups_warn_percent: int,
    suspicious_growth_gb: int,
    backup_freshness_target_hours: int,
    alerts: str,
) -> None:
    policy_state = state.read_state_file(settings.state_dir / state.STATE_FILES["policy"])
    policy_state["approved_features_now"] = newline_entries(approved_features_now)
    policy_state["delayed_features"] = newline_entries(delayed_features)
    policy_state["cleanup_policy"]["maintenance_window"] = maintenance_window
    policy_state["cleanup_policy"]["entity_farm_limits"] = newline_entries(entity_limits)
    policy_state["cleanup_policy"]["log_retention_days"] = log_retention_days
    policy_state["cleanup_policy"]["spark_report_retention_days"] = spark_report_retention_days
    policy_state["cleanup_policy"]["crash_report_retention_days"] = crash_report_retention_days
    policy_state["cleanup_policy"]["disk_growth_signals"] = {
        "data_dir_warn_percent": data_warn_percent,
        "backups_dir_warn_percent": backups_warn_percent,
        "suspicious_growth_gb": suspicious_growth_gb,
    }
    policy_state["observability"]["backup_freshness_target_hours"] = backup_freshness_target_hours
    policy_state["observability"]["alerts"] = newline_entries(alerts)
    state.save_named_state(settings.state_dir, "policy", policy_state)


def update_datapack_state(settings: Settings, safe_now: str, delayed: str) -> None:
    datapack_state = state.read_state_file(settings.state_dir / state.STATE_FILES["datapacks"])
    datapack_state["safe_now"] = parse_datapack_lines(safe_now, "safe")
    datapack_state["delayed"] = parse_datapack_lines(delayed, "medium")
    state.save_named_state(settings.state_dir, "datapacks", datapack_state)

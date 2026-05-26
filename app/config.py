from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    state_dir: Path
    data_dir: Path
    generated_dir: Path
    database_path: Path
    uploads_dir: Path
    target_stack_root: Path
    target_data_dir: Path
    target_backups_dir: Path
    target_access_dir: Path
    target_invite_players_file: Path
    target_sync_whitelist_script: Path
    backup_repo_root: Path
    session_secret: str
    console_title: str


def mounted_stack_path(path_value: str, host_stack_root: Path, mount_stack_root: Path | None) -> Path:
    host_path = Path(path_value).resolve()
    if mount_stack_root is None:
        return host_path

    try:
        relative_path = host_path.relative_to(host_stack_root)
    except ValueError:
        return host_path

    return (mount_stack_root / relative_path).resolve()


def load_settings() -> Settings:
    repo_root = Path(os.environ.get("MC_ADMIN_REPO_ROOT", "/workspace")).resolve()
    data_dir = Path(os.environ.get("MC_ADMIN_CONSOLE_DATA_DIR", str(repo_root / "data" / "console"))).resolve()
    host_stack_root = Path(os.environ.get("TARGET_STACK_ROOT", "/target/stack")).resolve()
    mount_stack_root_raw = os.environ.get("MC_ADMIN_TARGET_ROOT_MOUNT", "")
    mount_stack_root = Path(mount_stack_root_raw).resolve() if mount_stack_root_raw else None
    target_stack_root = mount_stack_root if mount_stack_root and mount_stack_root.exists() else host_stack_root
    target_data_dir = mounted_stack_path(
        os.environ.get("TARGET_DATA_DIR", str(host_stack_root / "data")),
        host_stack_root,
        target_stack_root if target_stack_root != host_stack_root else None,
    )
    target_backups_dir = mounted_stack_path(
        os.environ.get("TARGET_BACKUPS_DIR", str(host_stack_root / "backups")),
        host_stack_root,
        target_stack_root if target_stack_root != host_stack_root else None,
    )
    target_access_dir = mounted_stack_path(
        os.environ.get("TARGET_ACCESS_DIR", str(host_stack_root / "ops" / "access")),
        host_stack_root,
        target_stack_root if target_stack_root != host_stack_root else None,
    )
    target_invite_players_file = Path(
        os.environ.get("TARGET_INVITE_PLAYERS_FILE", str(target_access_dir / "invite-players.txt"))
    )
    target_sync_whitelist_script = Path(
        os.environ.get("TARGET_SYNC_WHITELIST_SCRIPT", str(host_stack_root / "scripts" / "sync-whitelist.sh"))
    )
    if target_stack_root != host_stack_root:
        target_invite_players_file = mounted_stack_path(str(target_invite_players_file), host_stack_root, target_stack_root)
        target_sync_whitelist_script = mounted_stack_path(str(target_sync_whitelist_script), host_stack_root, target_stack_root)
    else:
        target_invite_players_file = target_invite_players_file.resolve()
        target_sync_whitelist_script = target_sync_whitelist_script.resolve()

    return Settings(
        repo_root=repo_root,
        state_dir=(repo_root / "config" / "console").resolve(),
        data_dir=data_dir,
        generated_dir=(data_dir / "generated").resolve(),
        database_path=(data_dir / "console.db").resolve(),
        uploads_dir=target_data_dir / "world-library",
        target_stack_root=target_stack_root,
        target_data_dir=target_data_dir,
        target_backups_dir=target_backups_dir,
        target_access_dir=target_access_dir,
        target_invite_players_file=target_invite_players_file,
        target_sync_whitelist_script=target_sync_whitelist_script,
        backup_repo_root=Path(os.environ.get("BACKUP_COMPANION_ROOT", "/backup-companion")).resolve(),
        session_secret=os.environ.get("CONSOLE_SESSION_SECRET", "change-me-console-session-secret"),
        console_title=os.environ.get("CONSOLE_PAGE_TITLE", "Minecraft Control Plane"),
    )

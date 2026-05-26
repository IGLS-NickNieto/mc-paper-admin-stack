from __future__ import annotations

import tempfile
import unittest
import importlib.util
import os
import sqlite3
from pathlib import Path

from app import auth, db, services, state
from app.config import Settings


def make_settings(root: Path) -> Settings:
    return Settings(
        repo_root=root,
        state_dir=root / "config",
        data_dir=root / "data",
        generated_dir=root / "data" / "generated",
        database_path=root / "data" / "console.db",
        uploads_dir=root / "uploads",
        target_stack_root=root / "target",
        target_data_dir=root / "target" / "data",
        target_backups_dir=root / "target" / "backups",
        target_access_dir=root / "target" / "ops" / "access",
        target_invite_players_file=root / "target" / "ops" / "access" / "invite-players.txt",
        target_sync_whitelist_script=root / "target" / "scripts" / "sync-whitelist.sh",
        backup_repo_root=root / "backup",
        session_secret="test",
        console_title="Test",
    )


def load_sync_plugins_module():
    module_path = Path(__file__).resolve().parents[2] / "scripts" / "sync_plugins.py"
    spec = importlib.util.spec_from_file_location("sync_plugins", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load sync_plugins.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def memory_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.executescript(db.SCHEMA)
    return connection


class StateTests(unittest.TestCase):
    def test_ensure_state_files_creates_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            state_dir = Path(temp_dir)
            state.ensure_state_files(state_dir)
            payload = state.load_all_state(state_dir)
            self.assertIn("lobby", payload["servers"]["profiles"])
            self.assertIn("worlds", payload["worlds"])

    def test_build_plugin_install_plan_uses_profile_bundles(self) -> None:
        current_state = state.DEFAULT_STATE.copy()
        plan = services.build_plugin_install_plan(current_state)
        self.assertIn("lobby", plan["plans"])
        self.assertTrue(any(plugin["plugin_id"] == "quickconnect" for plugin in plan["plans"]["lobby"]))

    def test_env_save_preserves_existing_secret_when_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env.example").write_text("PLAIN=example value\nSECRET_TOKEN=\n", encoding="utf-8")
            (root / ".env").write_text("PLAIN=old\nSECRET_TOKEN=keep-me\n", encoding="utf-8")
            settings = make_settings(root)

            changed = services.save_env_target(settings, "admin", {"env_PLAIN": "new value", "env_SECRET_TOKEN": ""})
            env_text = (root / ".env").read_text(encoding="utf-8")

            self.assertEqual(changed, ["PLAIN"])
            self.assertIn("PLAIN='new value'", env_text)
            self.assertIn("SECRET_TOKEN=keep-me", env_text)

    def test_import_manual_plugin_from_private_source(self) -> None:
        sync_plugins = load_sync_plugins_module()
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            manual_dir = root / "plugins" / "manual"
            source_dir = root / "private" / "approved-now" / "luckperms"
            source_dir.mkdir(parents=True)
            source_file = source_dir / "LuckPerms-Bukkit-5.5.50.jar"
            source_file.write_bytes(b"jar")

            imported, imported_from = sync_plugins.import_manual_plugin(
                manual_dir,
                "LuckPerms-Bukkit-5.5.50.jar",
                [root / "private"],
            )

            self.assertEqual(imported, manual_dir / "LuckPerms-Bukkit-5.5.50.jar")
            self.assertEqual(imported_from, source_file)
            self.assertEqual((manual_dir / "LuckPerms-Bukkit-5.5.50.jar").read_bytes(), b"jar")

    def test_console_setup_required_for_placeholder_credentials(self) -> None:
        env = {
            "ENABLE_CONSOLE_FIRST_RUN_SETUP": "1",
            "CONSOLE_ADMIN_USER": "admin",
            "CONSOLE_ADMIN_PASSWORD": "change-me-console-admin",
            "CONSOLE_MOD_USER": "mod",
            "CONSOLE_MOD_PASSWORD": "change-me-console-mod",
            "CONSOLE_SESSION_SECRET": "change-me-console-session-secret",
        }
        connection = memory_database()
        try:
            auth.ensure_seed_users(connection, env)
            self.assertTrue(auth.console_setup_required(connection, env))
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0], 0)
        finally:
            connection.close()

    def test_first_run_credentials_update_env_and_database(self) -> None:
        managed_keys = [
            "ENABLE_CONSOLE_FIRST_RUN_SETUP",
            "CONSOLE_ADMIN_USER",
            "CONSOLE_ADMIN_PASSWORD",
            "CONSOLE_MOD_USER",
            "CONSOLE_MOD_PASSWORD",
            "CONSOLE_SESSION_SECRET",
        ]
        previous_env = {key: os.environ.get(key) for key in managed_keys}
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                (root / ".env.example").write_text(
                    "\n".join(f"{key}=" for key in managed_keys) + "\n",
                    encoding="utf-8",
                )
                (root / ".env").write_text(
                    "ENABLE_CONSOLE_FIRST_RUN_SETUP=1\n"
                    "CONSOLE_ADMIN_USER=admin\n"
                    "CONSOLE_ADMIN_PASSWORD=change-me-console-admin\n"
                    "CONSOLE_MOD_USER=mod\n"
                    "CONSOLE_MOD_PASSWORD=change-me-console-mod\n"
                    "CONSOLE_SESSION_SECRET=change-me-console-session-secret\n",
                    encoding="utf-8",
                )
                settings = make_settings(root)

                changed = services.save_first_run_credentials(settings, "owner", "admin-pass", "helper", "mod-pass")
                connection = memory_database()
                try:
                    auth.set_console_credentials(connection, "owner", "admin-pass", "helper", "mod-pass")
                    self.assertFalse(auth.console_setup_required(connection, dict(os.environ)))
                    self.assertIsNotNone(auth.authenticate(connection, "owner", "admin-pass"))
                    self.assertIsNotNone(auth.authenticate(connection, "helper", "mod-pass"))
                finally:
                    connection.close()

                env_text = (root / ".env").read_text(encoding="utf-8")
                self.assertIn("CONSOLE_ADMIN_USER=owner", env_text)
                self.assertIn("CONSOLE_MOD_USER=helper", env_text)
                self.assertIn("CONSOLE_SESSION_SECRET=", env_text)
                self.assertIn("CONSOLE_ADMIN_PASSWORD", changed)
        finally:
            for key, value in previous_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value


if __name__ == "__main__":
    unittest.main()

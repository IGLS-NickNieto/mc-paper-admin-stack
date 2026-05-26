from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import services, state
from app.config import Settings


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
            settings = Settings(
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

            changed = services.save_env_target(settings, "admin", {"env_PLAIN": "new value", "env_SECRET_TOKEN": ""})
            env_text = (root / ".env").read_text(encoding="utf-8")

            self.assertEqual(changed, ["PLAIN"])
            self.assertIn("PLAIN='new value'", env_text)
            self.assertIn("SECRET_TOKEN=keep-me", env_text)


if __name__ == "__main__":
    unittest.main()

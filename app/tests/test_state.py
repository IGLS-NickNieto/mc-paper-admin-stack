from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app import services, state


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


if __name__ == "__main__":
    unittest.main()

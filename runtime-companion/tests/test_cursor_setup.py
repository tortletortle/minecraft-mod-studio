import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

import install_cursor_mcp


class CursorInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.workspace = Path(self.temporary.name) / "workspace"
        self.workspace.mkdir()
        self.connection_file = Path(self.temporary.name) / "connection.json"
        self.connection_file.write_text('{"protocol":1}', encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_installs_stdio_server_and_only_readonly_auto_approval(self):
        cursor_dir = self.workspace / ".cursor"
        cursor_dir.mkdir()
        (cursor_dir / "mcp.json").write_text(json.dumps({
            "mcpServers": {
                "existing-tool": {"command": "node", "args": ["existing.js"]}
            }
        }), encoding="utf-8")
        (cursor_dir / "permissions.json").write_text(json.dumps({
            "terminalAllowlist": ["python -m unittest"],
            "mcpAllowlist": ["existing-tool:lookup"],
        }), encoding="utf-8")

        mcp_path, permissions_path = install_cursor_mcp.install(
            self.connection_file,
            scope="workspace",
            workspace=self.workspace,
            auto_approve_safe_tools=True,
        )
        mcp = json.loads(mcp_path.read_text(encoding="utf-8"))
        permissions = json.loads(permissions_path.read_text(encoding="utf-8"))
        server = mcp["mcpServers"]["minecraft-live-debugger"]

        self.assertEqual(server["type"], "stdio")
        self.assertEqual(server["command"], str(Path(sys.executable).resolve()))
        self.assertIn(str((TOOLS_DIR / "live_debugger_mcp.py").resolve()), server["args"])
        self.assertIn(str(self.connection_file.resolve()), server["args"])
        self.assertIn("existing-tool", mcp["mcpServers"])
        self.assertIn("existing-tool:lookup", permissions["mcpAllowlist"])
        self.assertIn("python -m unittest", permissions["terminalAllowlist"])
        self.assertIn("minecraft-live-debugger:mms_get_scene_snapshot", permissions["mcpAllowlist"])
        self.assertNotIn("minecraft-live-debugger:mms_move_player", permissions["mcpAllowlist"])
        self.assertNotIn("minecraft-live-debugger:mms_authorize_transient_controls", permissions["mcpAllowlist"])
        self.assertNotIn("protocol", mcp_path.read_text(encoding="utf-8"))

    def test_can_install_without_automatic_approval_entries(self):
        mcp_path, permissions_path = install_cursor_mcp.install(
            self.connection_file,
            scope="workspace",
            workspace=self.workspace,
        )
        self.assertTrue(mcp_path.is_file())
        self.assertIsNone(permissions_path)
        self.assertFalse((self.workspace / ".cursor" / "permissions.json").exists())

    def test_transient_auto_approval_keeps_authorization_and_persistent_writes_gated(self):
        mcp_path, permissions_path = install_cursor_mcp.install(
            self.connection_file,
            scope="workspace",
            workspace=self.workspace,
            auto_approve_transient_tools=True,
        )
        permissions = json.loads(permissions_path.read_text(encoding="utf-8"))
        allowed = permissions["mcpAllowlist"]
        self.assertIn("minecraft-live-debugger:mms_move_player", allowed)
        self.assertIn("minecraft-live-debugger:mms_move_player_and_verify", allowed)
        self.assertIn("minecraft-live-debugger:mms_trigger_animation", allowed)
        self.assertNotIn("minecraft-live-debugger:mms_authorize_transient_controls", allowed)
        self.assertNotIn("minecraft-live-debugger:mms_set_entity_attribute", allowed)
        self.assertNotIn("minecraft-live-debugger:mms_reset_entity_attributes", allowed)

    def test_dry_run_does_not_write_configuration(self):
        mcp_path, permissions_path = install_cursor_mcp.install(
            self.connection_file,
            scope="workspace",
            workspace=self.workspace,
            auto_approve_safe_tools=True,
            dry_run=True,
        )
        self.assertFalse(mcp_path.exists())
        self.assertFalse(permissions_path.exists())

    def test_malformed_existing_configuration_is_not_overwritten(self):
        cursor_dir = self.workspace / ".cursor"
        cursor_dir.mkdir()
        mcp_path = cursor_dir / "mcp.json"
        original = "{ not valid JSON"
        mcp_path.write_text(original, encoding="utf-8")
        with self.assertRaises(ValueError):
            install_cursor_mcp.install(
                self.connection_file,
                scope="workspace",
                workspace=self.workspace,
            )
        self.assertEqual(mcp_path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()

import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from install_cursor_mcp import (  # noqa: E402
    SAFE_AUTO_APPROVE_TOOLS,
    SERVER_NAME,
    TRANSIENT_TOOLS,
    install,
)
from diagnose_cursor_mcp import diagnose  # noqa: E402


class CursorTemplateAllowlistTests(unittest.TestCase):
    def test_opt_in_safe_allowlist_includes_template_tools_but_not_mutation_gates(self):
        template_tools = {
            "mms_list_ai_templates",
            "mms_get_ai_template",
            "mms_route_ai_task",
            "mms_check_ai_template_capabilities",
            "mms_prepare_ai_task",
        }
        self.assertTrue(template_tools.issubset(set(SAFE_AUTO_APPROVE_TOOLS)))
        self.assertNotIn("mms_authorize_transient_controls", SAFE_AUTO_APPROVE_TOOLS)
        self.assertNotIn("mms_set_entity_attribute", SAFE_AUTO_APPROVE_TOOLS)
        self.assertNotIn("mms_reset_entity_attributes", SAFE_AUTO_APPROVE_TOOLS)
        self.assertTrue(set(TRANSIENT_TOOLS).isdisjoint(set(SAFE_AUTO_APPROVE_TOOLS)))

    def test_installer_adds_template_tools_only_when_safe_auto_approval_is_opted_in(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection_file = root / "connection.json"
            connection_file.write_text("{}", encoding="utf-8")

            mcp_path, permissions_path = install(
                connection_file,
                scope="workspace",
                workspace=root,
                auto_approve_safe_tools=True,
            )
            self.assertTrue(mcp_path.is_file())
            self.assertTrue(permissions_path.is_file())
            permissions = json.loads(permissions_path.read_text(encoding="utf-8"))
            allowlist = permissions["mcpAllowlist"]
            self.assertIn(f"{SERVER_NAME}:mms_prepare_ai_task", allowlist)
            self.assertIn(f"{SERVER_NAME}:mms_list_ai_templates", allowlist)
            self.assertNotIn(f"{SERVER_NAME}:mms_authorize_transient_controls", allowlist)
            self.assertNotIn(f"{SERVER_NAME}:mms_set_entity_attribute", allowlist)
            self.assertNotIn(f"{SERVER_NAME}:mms_reset_entity_attributes", allowlist)

    def test_templates_only_install_and_diagnose_without_connection_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mcp_path, permissions_path = install(
                None,
                scope="workspace",
                workspace=root,
            )
            self.assertTrue(mcp_path.is_file())
            self.assertIsNone(permissions_path)
            config = json.loads(mcp_path.read_text(encoding="utf-8"))
            args = config["mcpServers"][SERVER_NAME]["args"]
            self.assertNotIn("--connection-file", args)

            result = diagnose(None, scope="workspace", workspace=root)
            self.assertTrue(result["template_only_mode"])
            self.assertTrue(result["cursor_server_registered"])
            self.assertFalse(result["minecraft_bridge_connected"])

    def test_default_install_does_not_write_cursor_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection_file = root / "connection.json"
            connection_file.write_text("{}", encoding="utf-8")
            mcp_path, permissions_path = install(
                connection_file,
                scope="workspace",
                workspace=root,
            )
            self.assertTrue(mcp_path.is_file())
            self.assertIsNone(permissions_path)
            self.assertFalse((root / ".cursor" / "permissions.json").exists())


if __name__ == "__main__":
    unittest.main()

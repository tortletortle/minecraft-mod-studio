#!/usr/bin/env python3
"""Check Cursor MCP registration and the live Minecraft bridge without printing secrets."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

from live_debugger_client import BridgeClient, BridgeError

SERVER_NAME = "minecraft-live-debugger"
REQUIRED_CAPABILITIES = {"status", "scene_snapshot", "capture_screenshot", "move", "stop"}


def _load(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def diagnose(connection_file: Path, *, scope: str = "workspace", workspace: Path | None = None) -> dict[str, Any]:
    if scope == "workspace":
        cursor_dir = (workspace or Path.cwd()).expanduser().resolve() / ".cursor"
    else:
        cursor_dir = Path.home() / ".cursor"
    mcp_path = cursor_dir / "mcp.json"
    permissions_path = cursor_dir / "permissions.json"
    config = _load(mcp_path)
    servers = config.get("mcpServers", {})
    if not isinstance(servers, dict):
        servers = {}
    server = servers.get(SERVER_NAME, {})
    expected_script = Path(__file__).resolve().with_name("live_debugger_mcp.py")
    expected_python = str(Path(sys.executable).resolve())
    expected_connection = str(connection_file.expanduser().resolve())

    registration_matches = (
        isinstance(server, dict)
        and server.get("command") == expected_python
        and isinstance(server.get("args"), list)
        and str(expected_script) in server["args"]
        and expected_connection in server["args"]
        and server.get("type") == "stdio"
    )

    connection_ok = False
    capabilities: list[str] = []
    bridge_error: str | None = None
    try:
        with BridgeClient(connection_file) as bridge:
            capabilities = sorted(bridge.capabilities)
            connection_ok = REQUIRED_CAPABILITIES.issubset(set(capabilities))
            if not connection_ok:
                bridge_error = "The companion is connected but does not advertise every V2.6.5 capability."
    except (OSError, ValueError, BridgeError) as exc:
        bridge_error = str(exc)

    permissions = _load(permissions_path)
    allowlist = permissions.get("mcpAllowlist", [])
    readonly_allowlist_present = (
        isinstance(allowlist, list)
        and all(f"{SERVER_NAME}:{tool}" in allowlist for tool in (
            "mms_game_status", "mms_get_scene_snapshot", "mms_capture_screenshot", "mms_stop_player",
            "mms_list_ai_templates", "mms_get_ai_template", "mms_route_ai_task",
            "mms_check_ai_template_capabilities", "mms_prepare_ai_task"
        ))
    )
    transient_allowlist_present = (
        isinstance(allowlist, list)
        and all(f"{SERVER_NAME}:{tool}" in allowlist for tool in (
            "mms_move_player", "mms_move_player_and_verify", "mms_look_player", "mms_trigger_animation"
        ))
    )
    sdk_available = importlib.util.find_spec("mcp") is not None

    return {
        "python_executable": expected_python,
        "python_version": sys.version.split()[0],
        "mcp_sdk_installed": sdk_available,
        "cursor_mcp_config": str(mcp_path),
        "cursor_server_registered": registration_matches,
        "cursor_safe_tool_allowlist_configured": readonly_allowlist_present,
        "cursor_transient_tool_allowlist_configured": transient_allowlist_present,
        "connection_file_exists": connection_file.is_file() and not connection_file.is_symlink(),
        "minecraft_bridge_connected": connection_ok,
        "advertised_capabilities": capabilities,
        "bridge_error": bridge_error,
        "token_printed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--scope", choices=("workspace", "global"), default="workspace")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = diagnose(args.connection_file, scope=args.scope, workspace=args.workspace)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    healthy = (
        result["mcp_sdk_installed"]
        and result["cursor_server_registered"]
        and result["minecraft_bridge_connected"]
    )
    return 0 if healthy else 1


if __name__ == "__main__":
    raise SystemExit(main())

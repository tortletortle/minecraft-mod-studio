#!/usr/bin/env python3
"""Install the MMS Live Debugger MCP server into Cursor without exposing its token."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

SERVER_NAME = "minecraft-live-debugger"
TRANSIENT_TOOLS = (
    "mms_move_player",
    "mms_move_player_and_verify",
    "mms_look_player",
    "mms_trigger_animation",
)
SAFE_AUTO_APPROVE_TOOLS = (
    "mms_game_status",
    "mms_get_scene_snapshot",
    "mms_list_nearby_entities",
    "mms_inspect_entity",
    "mms_inspect_block",
    "mms_read_entity_attributes",
    "mms_capture_screenshot",
    "mms_stop_player",
)


def _read_object(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError(f"Refusing to modify symbolic-link configuration: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot safely parse existing JSON configuration: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Configuration root must be a JSON object: {path}")
    return value


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(f"Refusing to replace symbolic-link configuration: {path}")
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def build_cursor_config(connection_file: Path) -> dict[str, Any]:
    script = Path(__file__).resolve().with_name("live_debugger_mcp.py")
    return {
        "type": "stdio",
        "command": str(Path(sys.executable).resolve()),
        "args": [
            "-B",
            str(script),
            "--connection-file",
            str(connection_file.resolve(strict=True)),
        ],
    }


def install(
    connection_file: Path,
    *,
    scope: str = "workspace",
    workspace: Path | None = None,
    auto_approve_safe_tools: bool = False,
    auto_approve_transient_tools: bool = False,
    dry_run: bool = False,
) -> tuple[Path, Path | None]:
    connection_file = connection_file.expanduser()
    if connection_file.is_symlink() or not connection_file.is_file():
        raise ValueError("connection file must be an existing regular file, not a symbolic link")

    if scope == "workspace":
        root = (workspace or Path.cwd()).expanduser().resolve()
        cursor_dir = root / ".cursor"
    elif scope == "global":
        cursor_dir = Path.home() / ".cursor"
    else:
        raise ValueError("scope must be workspace or global")

    mcp_path = cursor_dir / "mcp.json"
    mcp_config = _read_object(mcp_path)
    servers = mcp_config.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError(f"mcpServers must be a JSON object in {mcp_path}")
    servers[SERVER_NAME] = build_cursor_config(connection_file)

    permissions_path: Path | None = None
    permissions: dict[str, Any] | None = None
    if auto_approve_safe_tools or auto_approve_transient_tools:
        permissions_path = cursor_dir / "permissions.json"
        permissions = _read_object(permissions_path)
        current = permissions.get("mcpAllowlist", [])
        if not isinstance(current, list) or any(not isinstance(item, str) for item in current):
            raise ValueError(f"mcpAllowlist must be an array of strings in {permissions_path}")
        additions = []
        if auto_approve_safe_tools:
            additions.extend(SAFE_AUTO_APPROVE_TOOLS)
        if auto_approve_transient_tools:
            additions.extend(TRANSIENT_TOOLS)
        permissions["mcpAllowlist"] = list(dict.fromkeys(
            [*current, *(f"{SERVER_NAME}:{tool}" for tool in additions)]
        ))

    if not dry_run:
        _atomic_write_json(mcp_path, mcp_config)
        if permissions_path is not None and permissions is not None:
            _atomic_write_json(permissions_path, permissions)
    return mcp_path, permissions_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", type=Path, required=True)
    parser.add_argument("--scope", choices=("workspace", "global"), default="workspace")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--allow-safe-tools-without-approval",
        action="store_true",
        help="Opt in to auto-approving read-only inspection and the emergency stop tool in Cursor.",
    )
    parser.add_argument(
        "--allow-transient-actions-without-approval",
        action="store_true",
        help="Opt in to auto-approving transient movement, camera and animation tools; the short-lived authorization tool stays gated.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        mcp_path, permissions_path = install(
            args.connection_file,
            scope=args.scope,
            workspace=args.workspace,
            auto_approve_safe_tools=args.allow_safe_tools_without_approval,
            auto_approve_transient_tools=args.allow_transient_actions_without_approval,
            dry_run=args.dry_run,
        )
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Cursor MCP installation failed: {exc}\n")
    print(json.dumps({
        "installed": not args.dry_run,
        "server": SERVER_NAME,
        "mcp_config": str(mcp_path),
        "permissions_config": str(permissions_path) if permissions_path else None,
        "safe_tools_auto_approved": list(SAFE_AUTO_APPROVE_TOOLS) if args.allow_safe_tools_without_approval else [],
        "transient_tools_auto_approved": list(TRANSIENT_TOOLS) if args.allow_transient_actions_without_approval else [],
        "transient_control_and_persistent_write_tools_auto_approved": False,
        "token_written_to_cursor_config": False,
        "next_step": "Restart Cursor, then run diagnose_cursor_mcp.py with the same connection file.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

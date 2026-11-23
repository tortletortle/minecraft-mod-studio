import asyncio
import base64
import hashlib
import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

try:
    from mcp import Client, StdioServerParameters
except ModuleNotFoundError as exc:
    if exc.name != "mcp":
        raise
    raise unittest.SkipTest("optional MCP SDK is not installed") from exc


class FakeBridge:
    def __init__(self):
        self.token = "a" * 64
        self.listener = socket.socket()
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen()
        self.listener.settimeout(0.2)
        self.port = self.listener.getsockname()[1]
        self.requests = []
        self.game_time = 42
        self.position = {"x": 1.5, "y": 64.0, "z": -2.5}
        self.pending_move_ticks = 0
        self.capture_path = None
        self.lock = threading.Lock()
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self.stopping.is_set():
            try:
                conn, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(3)
                reader = conn.makefile("rb")
                hello = json.loads(reader.readline())
                if hello.get("protocol") != 1 or hello.get("token") != self.token:
                    conn.sendall(b'{"ok":false,"error":"AUTH_FAILED"}\n')
                    continue
                conn.sendall(b'{"ok":true,"protocol":1,"capabilities":["status","scene_snapshot","capture_screenshot","move","look","stop","entities","inspect_entity","entity_attributes","set_entity_attribute","reset_entity_attributes","trigger_animation","block","command_catalog","command_inspect","command_validate"]}\n')
                line = reader.readline()
                if not line:
                    continue
                request = json.loads(line)
                with self.lock:
                    self.requests.append(request)
                command = request["command"]
                if command == "status":
                    if self.pending_move_ticks:
                        self.game_time += self.pending_move_ticks
                        self.position["x"] += 0.25
                        self.pending_move_ticks = 0
                    result = {
                        "dimension": "minecraft:overworld",
                        "game_time": self.game_time,
                        "movement_active": False,
                        "player": {
                            "uuid": "00000000-0000-0000-0000-000000000001",
                            **self.position,
                        },
                    }
                elif command == "scene_snapshot":
                    result = {
                        "dimension": "minecraft:overworld",
                        "game_time": self.game_time,
                        "movement_active": False,
                        "player": {"uuid": "00000000-0000-0000-0000-000000000001", **self.position},
                        "nearby_entities": [],
                        "entity_count": 0,
                        "entities_truncated": False,
                        "nearby_blocks": {},
                        "snapshot_consistency": "single_client_thread_capture",
                    }
                elif command == "move":
                    self.pending_move_ticks = request["ticks"]
                    result = {"accepted": True, "remaining_ticks": request["ticks"], "max_ticks": 40}
                elif command == "capture_screenshot":
                    if self.capture_path is None:
                        raise RuntimeError("capture_path was not configured in the fake bridge")
                    png_data = base64.b64decode(
                        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p0sAAAAASUVORK5CYII="
                    )
                    self.capture_path.write_bytes(png_data)
                    (self.capture_path.parent / "capture.json").write_text(json.dumps({
                        "capture_id": "00000000-0000-0000-0000-000000000001",
                        "file_name": "capture.png", "width": 1, "height": 1,
                        "sha256": hashlib.sha256(png_data).hexdigest(),
                    }), encoding="utf-8")
                    result = {"capture_id": "00000000-0000-0000-0000-000000000001", "file_name": "capture.png", "capture_requested": True}
                elif command == "command_catalog":
                    catalog = [
                        {"name": "fill", "executable_at_root": False, "child_count": 3, "redirect": False},
                        {"name": "summon", "executable_at_root": False, "child_count": 2, "redirect": False},
                        {"name": "weather", "executable_at_root": False, "child_count": 2, "redirect": False},
                        *[
                            {"name": f"testmod_{index:02d}", "executable_at_root": True, "child_count": 0, "redirect": False}
                            for index in range(20)
                        ],
                    ]
                    catalog[3]["manifest_summary"] = {
                        "source_mod_id": "example_npc_mod",
                        "source_mod_version": "1.0.0",
                        "description_locale": "zh_cn",
                        "description": "召唤发光测试精灵",
                        "keywords": ["发光测试精灵", "召唤精灵"],
                        "root_present_in_live_dispatcher": True,
                        "ownership_verified": False,
                        "trust": "untrusted_mod_supplied_metadata",
                    }
                    offset = request.get("offset", 0)
                    limit = request.get("limit", 50)
                    page = catalog[offset:offset + limit]
                    result = {
                        "operator_id": "MMS_AI_OPERATOR",
                        "operator_entity_bound": False,
                        "permission_view": "ALL_PERMISSIONS",
                        "execution_enabled": False,
                        "catalog_source": "live_integrated_server_brigadier_dispatcher",
                        "manifest_source": "mms/commands.json",
                        "manifest_file_count": 1,
                        "manifest_command_count": 1,
                        "manifest_scanned_mods": 24,
                        "manifest_issues": [],
                        "manifest_issue_count": 0,
                        "manifest_issues_truncated": False,
                        "total": len(catalog),
                        "offset": offset,
                        "limit": limit,
                        "has_more": offset + len(page) < len(catalog),
                        "commands": page,
                    }
                elif command == "command_inspect":
                    result = {
                        "operator_id": "MMS_AI_OPERATOR",
                        "execution_enabled": False,
                        "command": request["name"],
                        "usage_count": 2,
                        "usages": ["fill <from> <to> <block>", "fill <from> <to> <block> replace <filter>"],
                        "smart_usage": ["fill <from> <to> <block>"],
                        "children": [{"name": "from", "node_type": "RequiredArgumentCommandNode", "executable": False, "child_count": 1, "redirect": False}],
                    }
                elif command == "command_validate":
                    normalized = request["command"].lstrip("/")
                    valid = normalized.startswith("fill ")
                    result = {
                        "operator_id": "MMS_AI_OPERATOR",
                        "execution_enabled": False,
                        "syntax_only": True,
                        "command": normalized,
                        "parsed_characters": len(normalized),
                        "valid": valid,
                        "error_code": "" if valid else "COMMAND_SYNTAX_INVALID",
                        "message": "Brigadier parsed an executable command path. No command was executed." if valid else "Unknown command.",
                    }
                elif command == "entities":
                    result = {"radius": request.get("radius", 16.0), "returned": 0, "truncated": False, "entities": []}
                else:
                    result = {"accepted": True, "command": command}
                response = {"id": request["id"], "ok": True, "result": result}
                conn.sendall((json.dumps(response) + "\n").encode("utf-8"))

    def snapshot(self):
        with self.lock:
            return list(self.requests)

    def close(self):
        self.stopping.set()
        self.listener.close()
        self.thread.join(timeout=2)


def mcp_client(game_dir: Path):
    script = Path(__file__).resolve().parents[1] / "tools" / "live_debugger_mcp.py"
    return Client(StdioServerParameters(
        command=sys.executable,
        args=["-B", str(script), "--connection-file", str(game_dir / "connection.json")],
    ))


class LiveDebuggerMcpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.game_dir = Path(self.temporary.name)
        self.bridge = FakeBridge()
        self.bridge.capture_path = self.game_dir / "capture.png"
        (self.game_dir / "connection.json").write_text(json.dumps({
            "protocol": 1, "host": "127.0.0.1", "port": self.bridge.port, "token": self.bridge.token, "mod_version": "0.6.0",
        }), encoding="utf-8")

    async def asyncTearDown(self):
        self.bridge.close()
        self.temporary.cleanup()

    async def test_read_tools_expose_status_and_nearby_entities(self):
        async with mcp_client(self.game_dir) as client:
            tools = (await client.list_tools()).tools
            names = {tool.name for tool in tools}
            self.assertEqual(names, {
                "mms_game_status", "mms_get_scene_snapshot", "mms_capture_screenshot",
                "mms_list_nearby_entities", "mms_inspect_entity", "mms_inspect_block",
                "mms_read_entity_attributes", "mms_authorize_transient_controls",
                "mms_move_player", "mms_move_player_and_verify", "mms_look_player",
                "mms_stop_player", "mms_set_entity_attribute", "mms_reset_entity_attributes",
                "mms_trigger_animation", "mms_search_commands", "mms_inspect_command", "mms_validate_command",
            })
            status = await client.call_tool("mms_game_status", {})
            self.assertFalse(status.is_error)
            self.assertEqual(status.structured_content["result"]["player"]["x"], 1.5)
            nearby = await client.call_tool("mms_list_nearby_entities", {"radius": 12.0})
            self.assertFalse(nearby.is_error)
            self.assertEqual(nearby.structured_content["result"]["radius"], 12.0)

        requests = self.bridge.snapshot()
        self.assertEqual([item["command"] for item in requests], ["status", "entities"])

    async def test_command_search_inspection_and_validation_are_read_only(self):
        async with mcp_client(self.game_dir) as client:
            search = await client.call_tool("mms_search_commands", {"query": "批量替换方块"})
            self.assertFalse(search.is_error)
            search_result = search.structured_content["result"]
            self.assertEqual(search_result["operator"]["operator_id"], "MMS_AI_OPERATOR")
            self.assertFalse(search_result["operator"]["execution_enabled"])
            self.assertEqual(search_result["total_indexed"], 23)
            self.assertFalse(search_result["catalog_truncated"])
            self.assertEqual(search_result["results"][0]["name"], "fill")

            inspected = await client.call_tool("mms_inspect_command", {"name": "fill"})
            self.assertFalse(inspected.is_error)
            self.assertEqual(inspected.structured_content["result"]["usages"][0], "fill <from> <to> <block>")

            validated = await client.call_tool("mms_validate_command", {"command": "/fill ~ ~ ~ ~1 ~1 ~1 stone"})
            self.assertFalse(validated.is_error)
            validation = validated.structured_content["result"]
            self.assertTrue(validation["valid"])
            self.assertTrue(validation["syntax_only"])
            self.assertFalse(validation["execution_enabled"])

            invalid = await client.call_tool("mms_validate_command", {"command": "not_a_real_command"})
            self.assertFalse(invalid.is_error)
            self.assertFalse(invalid.structured_content["result"]["valid"])

        requests = self.bridge.snapshot()
        self.assertEqual(
            [item["command"] for item in requests],
            ["command_catalog", "command_catalog", "command_catalog", "command_inspect", "command_validate", "command_validate"],
        )
        self.assertNotIn("execute", [item["command"] for item in requests])

    async def test_mod_manifest_enriches_search_but_is_marked_untrusted(self):
        async with mcp_client(self.game_dir) as client:
            search = await client.call_tool("mms_search_commands", {"query": "发光测试精灵"})
            self.assertFalse(search.is_error)
            result = search.structured_content["result"]
            self.assertEqual(result["operator"]["manifest_file_count"], 1)
            self.assertEqual(result["operator"]["manifest_command_count"], 1)
            self.assertEqual(result["operator"]["manifest_source"], "mms/commands.json")
            self.assertEqual(result["results"][0]["name"], "testmod_00")
            manifest = result["results"][0]["manifest_summary"]
            self.assertEqual(manifest["source_mod_id"], "example_npc_mod")
            self.assertEqual(manifest["trust"], "untrusted_mod_supplied_metadata")
            self.assertFalse(manifest["ownership_verified"])
            self.assertTrue(manifest["root_present_in_live_dispatcher"])
            self.assertIn("mod_manifest_keyword", result["results"][0]["match_basis"])
        requests = self.bridge.snapshot()
        self.assertEqual(
            [item["command"] for item in requests],
            ["command_catalog", "command_catalog", "command_catalog"],
        )

    async def test_scene_snapshot_and_screenshot_return_rich_context(self):
        async with mcp_client(self.game_dir) as client:
            snapshot = await client.call_tool("mms_get_scene_snapshot", {"radius": 12.0})
            self.assertFalse(snapshot.is_error)
            self.assertEqual(snapshot.structured_content["result"]["snapshot_consistency"], "single_client_thread_capture")
            self.assertIn("nearby_entities", snapshot.structured_content["result"])

            screenshot = await client.call_tool("mms_capture_screenshot", {})
            self.assertFalse(screenshot.is_error)
            self.assertEqual(screenshot.content[0].type, "image")

        requests = self.bridge.snapshot()
        self.assertEqual([item["command"] for item in requests], ["scene_snapshot", "capture_screenshot"])

    async def test_transient_session_authorization_and_move_verification(self):
        async with mcp_client(self.game_dir) as client:
            refused = await client.call_tool("mms_move_player_and_verify", {
                "forward": 1.0, "strafe": 0.0, "ticks": 3,
            })
            self.assertTrue(refused.is_error)
            self.assertEqual(self.bridge.snapshot(), [])

            authorized = await client.call_tool("mms_authorize_transient_controls", {
                "confirm": True, "duration_seconds": 60,
            })
            self.assertFalse(authorized.is_error)
            self.assertTrue(authorized.structured_content["result"]["authorized"])

            moved = await client.call_tool("mms_move_player_and_verify", {
                "forward": 1.0, "strafe": 0.0, "ticks": 3,
            })
            self.assertFalse(moved.is_error)
            result = moved.structured_content["result"]
            self.assertTrue(result["movement_completed"])
            self.assertTrue(result["movement_observed"])
            self.assertEqual(result["elapsed_game_ticks"], 3)
            self.assertGreater(result["distance_moved_blocks"], 0.05)

        commands = [item["command"] for item in self.bridge.snapshot()]
        self.assertEqual(commands, ["status", "move", "status"])

    async def test_transient_session_required_and_persistent_writes_still_confirmed(self):
        async with mcp_client(self.game_dir) as client:
            before = len(self.bridge.snapshot())
            refused = await client.call_tool("mms_move_player", {
                "forward": 1.0, "strafe": 0.0, "ticks": 5,
            })
            self.assertTrue(refused.is_error)
            self.assertEqual(len(self.bridge.snapshot()), before)

            unapproved_session = await client.call_tool("mms_authorize_transient_controls", {
                "duration_seconds": 60,
            })
            self.assertTrue(unapproved_session.is_error)
            self.assertEqual(len(self.bridge.snapshot()), before)

            authorized = await client.call_tool("mms_authorize_transient_controls", {
                "confirm": True, "duration_seconds": 60,
            })
            self.assertFalse(authorized.is_error)

            moved = await client.call_tool("mms_move_player", {
                "forward": 1.0, "strafe": 0.0, "ticks": 5,
            })
            self.assertFalse(moved.is_error)

            stopped = await client.call_tool("mms_stop_player", {})
            self.assertFalse(stopped.is_error)

            unconfirmed_change = await client.call_tool("mms_set_entity_attribute", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "attribute": "attack_damage", "value": 12.0,
            })
            self.assertTrue(unconfirmed_change.is_error)

            changed = await client.call_tool("mms_set_entity_attribute", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "attribute": "attack_damage", "value": 12.0, "confirm": True,
            })
            self.assertFalse(changed.is_error)

            unconfirmed_reset = await client.call_tool("mms_reset_entity_attributes", {
                "uuid": "00000000-0000-0000-0000-000000000001",
            })
            self.assertTrue(unconfirmed_reset.is_error)

            reset = await client.call_tool("mms_reset_entity_attributes", {
                "uuid": "00000000-0000-0000-0000-000000000001", "confirm": True,
            })
            self.assertFalse(reset.is_error)

        requests = self.bridge.snapshot()
        self.assertEqual([item["command"] for item in requests], ["move", "stop", "set_entity_attribute", "reset_entity_attributes"])
        self.assertEqual(requests[0]["ticks"], 5)
        self.assertNotIn("confirm", requests[0])
        self.assertIs(requests[2]["confirm"], True)

    async def test_attribute_bounds_and_animation_session_gate(self):
        async with mcp_client(self.game_dir) as client:
            invalid = await client.call_tool("mms_set_entity_attribute", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "attribute": "attack_damage", "value": 500.0, "confirm": True,
            })
            self.assertTrue(invalid.is_error)
            self.assertEqual(self.bridge.snapshot(), [])

            refused = await client.call_tool("mms_trigger_animation", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "animation_id": "attack",
            })
            self.assertTrue(refused.is_error)
            self.assertEqual(self.bridge.snapshot(), [])

            authorized = await client.call_tool("mms_authorize_transient_controls", {
                "confirm": True, "duration_seconds": 60,
            })
            self.assertFalse(authorized.is_error)

            triggered = await client.call_tool("mms_trigger_animation", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "animation_id": "attack",
            })
            self.assertFalse(triggered.is_error)

        requests = self.bridge.snapshot()
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["command"], "trigger_animation")


if __name__ == "__main__":
    unittest.main()

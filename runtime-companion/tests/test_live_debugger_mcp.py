import asyncio
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
                conn.sendall(b'{"ok":true,"protocol":1,"capabilities":["status","move","look","stop","entities","inspect_entity","entity_attributes","set_entity_attribute","reset_entity_attributes","trigger_animation","block"]}\n')
                line = reader.readline()
                if not line:
                    continue
                request = json.loads(line)
                with self.lock:
                    self.requests.append(request)
                command = request["command"]
                if command == "status":
                    result = {
                        "dimension": "minecraft:overworld",
                        "game_time": 42,
                        "player": {"uuid": "00000000-0000-0000-0000-000000000001", "x": 1.5, "y": 64.0, "z": -2.5},
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
        (self.game_dir / "connection.json").write_text(json.dumps({
            "protocol": 1, "host": "127.0.0.1", "port": self.bridge.port, "token": self.bridge.token,
        }), encoding="utf-8")

    async def asyncTearDown(self):
        self.bridge.close()
        self.temporary.cleanup()

    async def test_read_tools_expose_status_and_nearby_entities(self):
        async with mcp_client(self.game_dir) as client:
            tools = (await client.list_tools()).tools
            names = {tool.name for tool in tools}
            self.assertEqual(names, {
                "mms_game_status", "mms_list_nearby_entities", "mms_inspect_entity",
                "mms_inspect_block", "mms_read_entity_attributes", "mms_move_player",
                "mms_look_player", "mms_stop_player", "mms_set_entity_attribute",
                "mms_reset_entity_attributes", "mms_trigger_animation",
            })
            status = await client.call_tool("mms_game_status", {})
            self.assertFalse(status.is_error)
            self.assertEqual(status.structured_content["result"]["player"]["x"], 1.5)
            nearby = await client.call_tool("mms_list_nearby_entities", {"radius": 12.0})
            self.assertFalse(nearby.is_error)
            self.assertEqual(nearby.structured_content["result"]["radius"], 12.0)

        requests = self.bridge.snapshot()
        self.assertEqual([item["command"] for item in requests], ["status", "entities"])

    async def test_mutating_tools_require_confirmation_before_bridge_access(self):
        async with mcp_client(self.game_dir) as client:
            before = len(self.bridge.snapshot())
            refused = await client.call_tool("mms_move_player", {
                "forward": 1.0, "strafe": 0.0, "ticks": 5,
            })
            self.assertTrue(refused.is_error)
            self.assertEqual(len(self.bridge.snapshot()), before)

            moved = await client.call_tool("mms_move_player", {
                "forward": 1.0, "strafe": 0.0, "ticks": 5, "confirm": True,
            })
            self.assertFalse(moved.is_error)

            stopped = await client.call_tool("mms_stop_player", {})
            self.assertFalse(stopped.is_error)

            changed = await client.call_tool("mms_set_entity_attribute", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "attribute": "attack_damage", "value": 12.0, "confirm": True,
            })
            self.assertFalse(changed.is_error)

        requests = self.bridge.snapshot()
        self.assertEqual([item["command"] for item in requests], ["move", "stop", "set_entity_attribute"])
        self.assertEqual(requests[0]["ticks"], 5)
        self.assertNotIn("confirm", requests[0])
        self.assertIs(requests[2]["confirm"], True)

    async def test_attribute_bounds_and_animation_confirmation(self):
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

            triggered = await client.call_tool("mms_trigger_animation", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "animation_id": "attack", "confirm": True,
            })
            self.assertFalse(triggered.is_error)

        requests = self.bridge.snapshot()
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["command"], "trigger_animation")


if __name__ == "__main__":
    unittest.main()

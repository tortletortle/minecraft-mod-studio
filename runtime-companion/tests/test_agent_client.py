import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from live_debugger_client import BridgeClient, BridgeError


class FakeBridge:
    """Small deterministic TCP peer; sendall avoids buffered makefile test ambiguity."""

    def __init__(self, response_id_transform=None):
        self.token = "a" * 64
        self.server = socket.socket()
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.response_id_transform = response_id_transform
        self.received = None
        self.error = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @staticmethod
    def _read_line(conn):
        data = bytearray()
        while len(data) <= 8192:
            chunk = conn.recv(1)
            if not chunk:
                return bytes(data)
            if chunk == b"\n":
                return bytes(data)
            data.extend(chunk)
        raise AssertionError("test peer received an oversized line")

    def _serve(self):
        try:
            conn, _ = self.server.accept()
            with conn:
                conn.settimeout(3)
                hello_line = self._read_line(conn)
                if not hello_line:
                    raise AssertionError("client disconnected before handshake")
                hello = json.loads(hello_line)
                if hello.get("token") != self.token or hello.get("protocol") != 1:
                    conn.sendall(b'{"ok":false,"error":"AUTH_FAILED"}\n')
                    return
                conn.sendall(b'{"ok":true,"protocol":1,"capabilities":["status"]}\n')

                request_line = self._read_line(conn)
                if request_line:
                    request = json.loads(request_line)
                    self.received = request
                    response_id = request["id"]
                    if self.response_id_transform:
                        response_id = self.response_id_transform(response_id)
                    response = {"id": response_id, "ok": True, "result": {"pong": True}}
                    conn.sendall((json.dumps(response) + "\n").encode("utf-8"))
        except BaseException as exc:
            self.error = exc
        finally:
            self.server.close()

    def join_and_check(self, testcase):
        self.thread.join(timeout=4)
        testcase.assertFalse(self.thread.is_alive(), "fake bridge thread did not terminate")
        if self.error is not None:
            raise self.error


class BridgeClientTests(unittest.TestCase):
    def write_config(self, directory: Path, host="127.0.0.1", port=1, token="a" * 64):
        path = directory / "connection.json"
        path.write_text(json.dumps({
            "protocol": 1, "host": host, "port": port, "token": token
        }), encoding="utf-8")
        return path

    def test_handshake_and_request_round_trip(self):
        fake = FakeBridge()
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), port=fake.port)
            with BridgeClient(config) as client:
                self.assertEqual(client.capabilities, ["status"])
                result = client.request("status")
                self.assertEqual(result, {"pong": True})
        fake.join_and_check(self)
        self.assertEqual(fake.received["command"], "status")
        self.assertIsInstance(fake.received["id"], str)

    def test_refuses_non_loopback_host_before_connecting(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), host="192.0.2.1")
            with self.assertRaisesRegex(BridgeError, "non-loopback"):
                BridgeClient(config)

    def test_rejects_invalid_token_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), token="short")
            with self.assertRaisesRegex(BridgeError, "token"):
                BridgeClient(config)

    def test_rejects_wrong_token(self):
        fake = FakeBridge()
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), port=fake.port, token="b" * 64)
            with self.assertRaisesRegex(BridgeError, "authentication failed"):
                BridgeClient(config)
        fake.join_and_check(self)

    def test_rejects_response_id_mismatch(self):
        fake = FakeBridge(response_id_transform=lambda value: value + "-wrong")
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), port=fake.port)
            with BridgeClient(config) as client:
                with self.assertRaisesRegex(BridgeError, "ID mismatch"):
                    client.request("status")
        fake.join_and_check(self)

    def test_reserved_request_fields_cannot_be_overridden(self):
        fake = FakeBridge()
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), port=fake.port)
            with BridgeClient(config) as client:
                with self.assertRaisesRegex(BridgeError, "Reserved"):
                    client.request("status", command="move")
        fake.join_and_check(self)

    def test_v261_mob_commands_are_serialized(self):
        cases = (
            ("entity_attributes", {"uuid": "00000000-0000-0000-0000-000000000001"}),
            ("set_entity_attribute", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "attribute": "max_health",
                "value": 80,
                "confirm": True,
            }),
            ("trigger_animation", {
                "uuid": "00000000-0000-0000-0000-000000000001",
                "animation_id": "attack",
            }),
        )
        for command, payload in cases:
            with self.subTest(command=command):
                fake = FakeBridge()
                with tempfile.TemporaryDirectory() as tmp:
                    config = self.write_config(Path(tmp), port=fake.port)
                    with BridgeClient(config) as client:
                        self.assertEqual(client.request(command, **payload), {"pong": True})
                fake.join_and_check(self)
                self.assertEqual(fake.received["command"], command)
                for key, value in payload.items():
                    self.assertEqual(fake.received[key], value)


if __name__ == "__main__":
    unittest.main()

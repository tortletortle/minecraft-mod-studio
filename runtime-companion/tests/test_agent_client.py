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
    def __init__(self, response_id_transform=None):
        self.token = "a" * 64
        self.server = socket.socket()
        self.server.bind(("127.0.0.1", 0))
        self.server.listen(1)
        self.port = self.server.getsockname()[1]
        self.response_id_transform = response_id_transform
        self.received = None
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        conn, _ = self.server.accept()
        with conn, conn.makefile("rb") as reader, conn.makefile("wb") as writer:
            hello = json.loads(reader.readline())
            if hello.get("token") != self.token or hello.get("protocol") != 1:
                writer.write(b'{"ok":false,"error":"AUTH_FAILED"}\n')
                writer.flush()
                return
            writer.write(b'{"ok":true,"protocol":1,"capabilities":["status"]}\n')
            writer.flush()
            request_line = reader.readline()
            if request_line:
                request = json.loads(request_line)
                self.received = request
                response_id = request["id"]
                if self.response_id_transform:
                    response_id = self.response_id_transform(response_id)
                response = {"id": response_id, "ok": True, "result": {"pong": True}}
                writer.write((json.dumps(response) + "\n").encode())
                writer.flush()
        self.server.close()


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
        fake.thread.join(timeout=2)
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

    def test_rejects_response_id_mismatch(self):
        fake = FakeBridge(response_id_transform=lambda value: value + "-wrong")
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), port=fake.port)
            with BridgeClient(config) as client:
                with self.assertRaisesRegex(BridgeError, "ID mismatch"):
                    client.request("status")
        fake.thread.join(timeout=2)

    def test_reserved_request_fields_cannot_be_overridden(self):
        fake = FakeBridge()
        with tempfile.TemporaryDirectory() as tmp:
            config = self.write_config(Path(tmp), port=fake.port)
            with BridgeClient(config) as client:
                with self.assertRaisesRegex(BridgeError, "Reserved"):
                    client.request("status", command="move")
        fake.thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()

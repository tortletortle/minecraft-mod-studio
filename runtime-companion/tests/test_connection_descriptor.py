import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from live_debugger_client import BridgeClient, BridgeError


class ConnectionDescriptorTests(unittest.TestCase):
    def write_config(self, path: Path, **overrides):
        value = {
            "protocol": 1,
            "host": "127.0.0.1",
            "port": 12345,
            "token": "a" * 64,
        }
        value.update(overrides)
        path.write_text(json.dumps(value), encoding="utf-8")
        return path

    def assert_rejected(self, path: Path):
        with self.assertRaises(BridgeError):
            BridgeClient(path)

    def test_rejects_boolean_protocol(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assert_rejected(self.write_config(Path(temporary) / "connection.json", protocol=True))

    def test_rejects_boolean_port(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assert_rejected(self.write_config(Path(temporary) / "connection.json", port=True))

    def test_rejects_non_hex_token(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assert_rejected(self.write_config(Path(temporary) / "connection.json", token="g" * 64))

    def test_rejects_unexpected_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            self.assert_rejected(self.write_config(Path(temporary) / "connection.json", extra="unexpected"))

    def test_rejects_oversized_descriptor(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "connection.json"
            path.write_bytes(b" " * 4097)
            self.assert_rejected(path)

    def test_rejects_symbolic_link(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = self.write_config(root / "real.json")
            link = root / "connection.json"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable in this environment")
            self.assert_rejected(link)


if __name__ == "__main__":
    unittest.main()

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Thread
import unittest
from unittest.mock import patch

from chat_bridge import DESCRIPTOR_NAME, DIAGNOSE_PATH, MAX_REQUEST_BYTES, MODEL_PATH, LocalModel, chat_bridge
from runtime_cache import CacheLockTimeout


PAYLOAD = {
    "question": "为什么这个矿石没有掉落？",
    "context": {
        "dimension": "minecraft:overworld",
        "target": {"kind": "block", "id": "minecraft:iron_ore", "properties": {}},
        "held": {"id": "minecraft:wooden_pickaxe", "count": 1},
        "requires_correct_tool_for_drops": True,
        "held_item_correct_for_drops": False,
    },
}
REPLY = "铁矿石需要石镐或更好的镐，当前木镐不会使它掉落。"


@contextmanager
def running(server):
    thread = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    try:
        yield
    finally:
        server.shutdown()
        thread.join(timeout=2)


@contextmanager
def model_fixture(respond=None, timeout=2.0):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, data))
            if respond is None:
                status, headers = 200, {}
                body = json.dumps({"choices": [{"message": {"content": REPLY}}]}).encode()
            else:
                status, headers, body = respond()
            try:
                self.send_response(status)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except ConnectionError:
                # The timeout test intentionally closes the connection before this response.
                pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server, running(server):
        yield LocalModel(f"http://127.0.0.1:{server.server_port}{MODEL_PATH}", "fixture", timeout), calls


def request(descriptor, payload=PAYLOAD, *, token=True, path=DIAGNOSE_PATH):
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {descriptor['token'] if token is True else token}"
    body = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    connection = http.client.HTTPConnection("127.0.0.1", descriptor["port"], timeout=3)
    try:
        connection.request("POST", path, body=body, headers=headers)
        with connection.getresponse() as response:
            return response.status, json.loads(response.read())
    finally:
        connection.close()


class BridgeTests(unittest.TestCase):
    @contextmanager
    def bridge(self, model):
        with TemporaryDirectory() as directory:
            game_dir = Path(directory)
            path = game_dir / "config" / DESCRIPTOR_NAME
            with chat_bridge(game_dir, model) as server, running(server):
                yield game_dir, json.loads(path.read_text(encoding="utf-8"))

    def test_real_http_exchange_forwards_only_validated_evidence_and_returns_reply(self):
        with model_fixture() as (model, calls), self.bridge(model) as (_, descriptor):
            with patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "NO_PROXY": ""}):
                self.assertEqual(request(descriptor), (200, {"reply": REPLY}))
        [(path, completion)] = calls
        self.assertEqual(path, MODEL_PATH)
        self.assertEqual(completion["model"], "fixture")
        self.assertEqual([m["role"] for m in completion["messages"]], ["system", "user"])
        self.assertEqual(json.loads(completion["messages"][1]["content"]), PAYLOAD)
        self.assertNotIn("tools", completion)
        self.assertNotIn(descriptor["token"], json.dumps(completion))

    def test_rejects_unknown_path_missing_or_invalid_token_and_oversized_body(self):
        with model_fixture() as (model, calls), self.bridge(model) as (_, descriptor):
            self.assertEqual(request(descriptor, path="/debug")[0], 404)
            self.assertEqual(request(descriptor, token=False)[0], 401)
            self.assertEqual(request(descriptor, token="wrong")[0], 401)
            self.assertEqual(request(descriptor, b"x" * (MAX_REQUEST_BYTES + 1))[0], 413)
        self.assertEqual(calls, [])

    def test_rejects_invalid_block_evidence_and_supports_entity_and_miss(self):
        with model_fixture() as (model, calls), self.bridge(model) as (_, descriptor):
            invalid = deepcopy(PAYLOAD)
            del invalid["context"]["requires_correct_tool_for_drops"]
            self.assertEqual(request(descriptor, invalid)[0], 400)
            invalid = deepcopy(PAYLOAD)
            invalid["context"]["held_item_correct_for_drops"] = 1
            self.assertEqual(request(descriptor, invalid)[0], 400)
            invalid = deepcopy(PAYLOAD)
            invalid["context"]["player_name"] = "private data"
            self.assertEqual(request(descriptor, invalid)[0], 400)
            invalid = deepcopy(PAYLOAD)
            invalid["question"] = "矿" * 321
            self.assertEqual(request(descriptor, invalid)[0], 400)
            for target in ({"kind": "entity", "id": "minecraft:pig"}, {"kind": "miss"}):
                evidence = {"dimension": "minecraft:overworld", "held": {"id": "minecraft:air", "count": 0}, "target": target}
                self.assertEqual(request(descriptor, {"question": "看到了什么？", "context": evidence})[0], 200)
        self.assertEqual(len(calls), 2)

    def test_refuses_redirects_and_non_loopback_provider_addresses(self):
        for url in ("http://192.0.2.1" + MODEL_PATH, "http://localhost" + MODEL_PATH,
                    "http://user:pass@127.0.0.1" + MODEL_PATH, "https://127.0.0.1" + MODEL_PATH):
            with self.subTest(url=url), self.assertRaises(ValueError):
                LocalModel(url, "fixture")
        with model_fixture(lambda: (307, {"Location": "/unexpected"}, b"")) as (model, calls):
            with self.bridge(model) as (_, descriptor):
                self.assertEqual(request(descriptor)[0], 502)
        self.assertEqual([path for path, _ in calls], [MODEL_PATH])

    def test_serializes_inference_and_returns_timeout(self):
        entered = Event()
        release = Event()

        def respond():
            entered.set()
            release.wait(2)
            return 500, {}, b""

        with model_fixture(respond, timeout=0.75) as (model, calls), self.bridge(model) as (_, descriptor):
            with ThreadPoolExecutor() as executor:
                future = executor.submit(request, descriptor)
                try:
                    self.assertTrue(entered.wait(2))
                    self.assertEqual(request(descriptor)[0], 429)
                    self.assertEqual(future.result(timeout=2)[0], 504)
                finally:
                    release.set()
        self.assertEqual(len(calls), 1)

    def test_descriptor_is_exclusive_and_rotates_on_restart(self):
        model = LocalModel("http://127.0.0.1:1" + MODEL_PATH, "fixture")
        with TemporaryDirectory() as directory:
            game_dir = Path(directory)
            path = game_dir / "config" / DESCRIPTOR_NAME
            with chat_bridge(game_dir, model) as server:
                first = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(first["version"], 1)
                self.assertEqual(first["port"], server.server_port)
                with self.assertRaises(CacheLockTimeout), chat_bridge(game_dir, model):
                    self.fail("A second bridge took the active descriptor")
                self.assertEqual(json.loads(path.read_text(encoding="utf-8")), first)
            self.assertFalse(path.exists())
            with chat_bridge(game_dir, model):
                self.assertNotEqual(json.loads(path.read_text(encoding="utf-8"))["token"], first["token"])
                self.assertEqual(list(path.parent.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()

import json
import re
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mms_project_operator import (
    ALLOWED_OPERATIONS,
    BridgeBroker,
    BridgeSession,
    ProjectBridgeError,
    ProjectOperatorHost,
)


class BridgeBrokerTests(unittest.TestCase):
    def test_request_is_correlated_with_browser_result(self):
        broker = BridgeBroker()
        received = {}

        def caller():
            try:
                received["result"] = broker.request(
                    "snapshot", {"include_validation": True}, timeout=2
                )
            except Exception as exc:
                received["error"] = str(exc)

        worker = threading.Thread(target=caller)
        worker.start()
        request = broker.next_request(timeout=1)
        self.assertIsNotNone(request)
        self.assertEqual(request["operation"], "snapshot")
        self.assertEqual(request["arguments"], {"include_validation": True})
        self.assertTrue(broker.complete(
            request["id"], {"revision": "abc123"}, None
        ))
        worker.join(timeout=2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(received, {"result": {"revision": "abc123"}})

    def test_unknown_operation_is_rejected(self):
        broker = BridgeBroker()
        with self.assertRaises(ProjectBridgeError):
            broker.request("execute_javascript", {})

    def test_request_timeout_cleans_pending_entry(self):
        broker = BridgeBroker()
        with self.assertRaisesRegex(ProjectBridgeError, "TIMEOUT"):
            broker.request("snapshot", {}, timeout=0.01)
        self.assertEqual(broker.pending_count, 0)

    def test_disconnect_fails_waiting_requests(self):
        broker = BridgeBroker()
        received = {}

        def caller():
            try:
                broker.request("snapshot", {}, timeout=2)
            except Exception as exc:
                received["error"] = str(exc)

        worker = threading.Thread(target=caller)
        worker.start()
        deadline = time.monotonic() + 1
        while broker.pending_count == 0 and time.monotonic() < deadline:
            time.sleep(0.005)
        broker.disconnect("PROJECT_BROWSER_DISCONNECTED")
        worker.join(timeout=1)
        self.assertEqual(received["error"], "PROJECT_BROWSER_DISCONNECTED")
        self.assertEqual(broker.pending_count, 0)


class BridgeSessionTests(unittest.TestCase):
    def test_pairing_token_is_single_use_and_session_is_authenticated(self):
        session = BridgeSession()
        pairing = session._pairing_token
        bearer = session.pair(pairing)
        self.assertEqual(len(pairing), 64)
        self.assertEqual(len(bearer), 64)
        self.assertTrue(session.connected)
        with self.assertRaisesRegex(ProjectBridgeError, "SESSION_ALREADY_ACTIVE"):
            session.pair(pairing)
        with self.assertRaisesRegex(ProjectBridgeError, "SESSION_INVALID"):
            session.authenticate("0" * 64)
        session.authenticate(bearer)
        session.disconnect(bearer)
        self.assertFalse(session.connected)

    def test_page_reload_rotates_pairing_and_disconnects_old_session(self):
        session = BridgeSession()
        old_pairing = session._pairing_token
        old_session = session.pair(old_pairing)
        new_pairing = session.prepare_page()
        self.assertNotEqual(old_pairing, new_pairing)
        self.assertFalse(session.connected)
        with self.assertRaisesRegex(ProjectBridgeError, "PAIRING_TOKEN_INVALID"):
            session.pair(old_pairing)
        new_session = session.pair(new_pairing)
        self.assertNotEqual(old_session, new_session)


class ProjectOperatorHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.editor = root / "editor.html"
        self.api = root / "api.js"
        self.client = root / "client.js"
        self.editor.write_text(
            "<!doctype html><html><body><main>Mod Studio</main></body></html>",
            encoding="utf-8",
        )
        self.api.write_text("window.__apiLoaded = true;", encoding="utf-8")
        self.client.write_text("window.__clientLoaded = true;", encoding="utf-8")
        self.host = ProjectOperatorHost(self.editor, self.api, self.client, port=0)
        self.host.start()
        self.origin = self.host.url.rstrip("/")
        self.base = self.host.url

    def tearDown(self):
        self.host.close()
        self.temp.cleanup()

    def request(self, path, method="GET", payload=None, token=None, origin=None, host=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {}
        if data is not None:
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(data))
        if token:
            headers["X-MMS-Session"] = token
        if origin is not None:
            headers["Origin"] = origin
        if host is not None:
            headers["Host"] = host
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        return urllib.request.urlopen(req, timeout=2)

    def pair(self):
        page = self.request("/").read().decode("utf-8")
        match = re.search(
            r'window\.__MMS_PROJECT_OPERATOR_PAIRING_TOKEN=("[0-9a-f]{64}")',
            page,
        )
        self.assertIsNotNone(match)
        pairing = json.loads(match.group(1))
        self.assertNotIn(pairing, self.base)
        response = self.request(
            "/bridge/pair",
            method="POST",
            payload={"token": pairing},
            origin=self.origin,
        )
        return json.loads(response.read().decode("utf-8"))["session_token"]

    def test_editor_page_injects_one_time_token_without_putting_it_in_url(self):
        response = self.request("/")
        page = response.read().decode("utf-8")
        self.assertIn("window.__MMS_PROJECT_OPERATOR_PAIRING_TOKEN=", page)
        self.assertIn("/mms_project_operator_api.js", page)
        self.assertIn("/mms_project_operator_client.js", page)
        self.assertNotIn("token=", self.base)

    def test_client_script_is_served_from_exact_route(self):
        response = self.request("/mms_project_operator_client.js")
        self.assertIn("window.__clientLoaded", response.read().decode("utf-8"))

    def test_api_script_is_served_from_exact_route(self):
        response = self.request("/mms_project_operator_api.js")
        self.assertIn("MMSProjectOperatorFactory", response.read().decode("utf-8"))

    def test_pairing_rejects_wrong_origin(self):
        page = self.request("/").read().decode("utf-8")
        match = re.search(
            r'window\.__MMS_PROJECT_OPERATOR_PAIRING_TOKEN=("[0-9a-f]{64}")',
            page,
        )
        pairing = json.loads(match.group(1))
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(
                "/bridge/pair",
                method="POST",
                payload={"token": pairing},
                origin="https://attacker.invalid",
            )
        self.assertEqual(caught.exception.code, 403)

    def test_pairing_and_authenticated_poll(self):
        token = self.pair()
        response = self.request(
            "/bridge/poll",
            method="POST",
            payload={"wait_ms": 0},
            token=token,
            origin=self.origin,
        )
        self.assertIsNone(json.loads(response.read().decode("utf-8"))["request"])

    def test_wrong_host_is_rejected(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request("/health", host="localhost:12345")
        self.assertEqual(caught.exception.code, 403)

    def test_page_reload_invalidates_old_session(self):
        token = self.pair()
        self.request("/")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(
                "/bridge/poll",
                method="POST",
                payload={"wait_ms": 0},
                token=token,
                origin=self.origin,
            )
        self.assertEqual(caught.exception.code, 401)

    def test_bridge_only_exposes_read_only_operations(self):
        self.assertEqual(
            ALLOWED_OPERATIONS,
            {
                "snapshot", "search", "inspectResource", "inspectProjectObject",
                "analyzeCompatibility", "planMigration",
            },
        )


if __name__ == "__main__":
    unittest.main()

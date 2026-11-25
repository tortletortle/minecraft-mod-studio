import json
import tempfile
import unittest
from pathlib import Path

from startup_status import StartupTracker, FLAT_SETTINGS


class StartupTests(unittest.TestCase):
    def test_observed_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            tracker = StartupTracker(path, 100)
            self.assertEqual(tracker.update("starting", 101)["stage"], "launcher_bootstrap")
            path.write_text("Read timed out\nLoading Minecraft 26.2", encoding="utf-8")
            result = tracker.update("starting", 120)
            self.assertTrue(result["network_warning_observed"])
            self.assertEqual(result["network_warning_reasons"], ["read_timeout"])
            self.assertEqual(result["stage"], "fabric_loading")
            self.assertEqual(tracker.update("waiting_for_probe", 130)["stage"], "waiting_for_probe")
            self.assertEqual(tracker.update("ready", 132)["ready_elapsed_s"], 32)
            self.assertEqual(tracker.update("ready", 150)["ready_elapsed_s"], 32)

    def test_phase_markers_are_first_observation_times(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            tracker = StartupTracker(path, 100)
            path.write_text("Loading Minecraft 26.2", encoding="utf-8")
            first = tracker.update("starting", 110)
            self.assertEqual(first["phase_markers_elapsed_s"], {"fabric_loading": 10})
            path.write_text(
                "Loading Minecraft 26.2\\nStarting minecraft server version 26.2\\nDone (0.4s)!",
                encoding="utf-8",
            )
            second = tracker.update("starting", 120)
            self.assertEqual(second["phase_markers_elapsed_s"], {
                "fabric_loading": 10, "server_start": 20, "server_done": 20,
            })
            path.write_text(
                "Loading Minecraft 26.2\\nStarting minecraft server version 26.2\\nDone (0.4s)!\\nStopping server",
                encoding="utf-8",
            )
            third = tracker.update("ready", 125)
            self.assertEqual(third["phase_markers_elapsed_s"]["fabric_loading"], 10)
            self.assertEqual(third["phase_markers_elapsed_s"]["server_stopping"], 25)
            self.assertEqual(third["probe_ready_elapsed_s"], 25)

    def test_network_warning_variants(self):
        cases = (
            ("Read timed out", ["read_timeout"]),
            ("Timed out after reading 4674 bytes", ["read_timeout"]),
            ("java.net.SocketTimeoutException: connect timed out",
             ["connection_timeout", "socket_timeout_exception"]),
            ("DIRECT failed", ["proxy_failure"]),
        )
        for message, expected in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "server.log"
                path.write_text(message, encoding="utf-8")
                result = StartupTracker(path, 0).update("starting", 1)
                self.assertTrue(result["network_warning_observed"])
                self.assertEqual(result["network_warning_reasons"], expected)

    def test_network_warning_reasons_are_sticky_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            tracker = StartupTracker(path, 0)
            path.write_text("Read timed out", encoding="utf-8")
            self.assertEqual(tracker.update("starting", 1)["network_warning_reasons"], ["read_timeout"])
            path.write_text("Read timed out\nTimed out after reading 4674 bytes", encoding="utf-8")
            result = tracker.update("starting", 2)
            self.assertEqual(result["network_warning_reasons"], ["read_timeout"])

    def test_generic_startup_timeout_is_not_network_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "server.log"
            path.write_text("startup timeout after 600 seconds", encoding="utf-8")
            result = StartupTracker(path, 0).update("starting", 1)
            self.assertFalse(result["network_warning_observed"])
            self.assertEqual(result["network_warning_reasons"], [])

    def test_timeout_and_flat_layers(self):
        tracker = StartupTracker("not-a-real-log", 0)
        self.assertEqual(tracker.update("startup_timeout", 601)["stage"], "startup_timeout")
        self.assertIsNone(tracker.ready)
        self.assertEqual([layer["height"] for layer in json.loads(FLAT_SETTINGS)["layers"]], [1, 2, 1])


if __name__ == "__main__":
    unittest.main()

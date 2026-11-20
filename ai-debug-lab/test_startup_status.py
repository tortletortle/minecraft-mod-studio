import json
import tempfile
import unittest
from pathlib import Path
from startup_status import StartupTracker,FLAT_SETTINGS
class StartupTests(unittest.TestCase):
    def test_observed_stages(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"server.log";t=StartupTracker(p,100)
            self.assertEqual(t.update("starting",101)["stage"],"launcher_bootstrap")
            p.write_text("Read timed out\nLoading Minecraft 26.2")
            r=t.update("starting",120)
            self.assertTrue(r["network_warning_observed"]);self.assertEqual(r["stage"],"fabric_loading")
            self.assertEqual(t.update("waiting_for_probe",130)["stage"],"waiting_for_probe")
            self.assertEqual(t.update("ready",132)["ready_elapsed_s"],32)
            self.assertEqual(t.update("ready",150)["ready_elapsed_s"],32)
    def test_timeout_and_flat_layers(self):
        t=StartupTracker("not-a-real-log",0)
        self.assertEqual(t.update("startup_timeout",601)["stage"],"startup_timeout")
        self.assertIsNone(t.ready)
        self.assertEqual([x["height"] for x in json.loads(FLAT_SETTINGS)["layers"]],[1,2,1])

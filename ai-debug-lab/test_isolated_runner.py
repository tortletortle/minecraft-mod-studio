import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from isolated_runner import IsolatedRunner

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        for p in ("launcher.jar","server.jar","a.jar","b.jar"):
            (self.root/p).write_bytes(p.encode())
    def runner(self,approved=True,jars=None):
        return IsolatedRunner(self.root/"launcher.jar",self.root/"server.jar",
                              jars or {"a":self.root/"a.jar","b":self.root/"b.jar"},
                              self.root/"evidence",lambda *a:None,approved=approved)
    def test_approval_required(self):
        with self.assertRaises(ValueError):self.runner(False)
        self.assertFalse((self.root/"evidence").exists())
    def test_invalid_config_and_trial_id(self):
        r=self.runner()
        for config,trial_id in [(("unknown",),"a"*32+"-1"),(("a","a"),"a"*32+"-1"),(("a",),"../bad")]:
            with self.assertRaises(ValueError):r(config,42,0,trial_id)
        self.assertEqual(list(r.output.iterdir()),[])
    def test_duplicate_jar_paths(self):
        with self.assertRaises(ValueError):self.runner(jars={"a":self.root/"a.jar","b":self.root/"a.jar"})
    def test_drift_invalid_before_launch(self):
        r=self.runner();(self.root/"a.jar").write_bytes(b"drift")
        with patch("isolated_runner.subprocess.Popen") as popen:
            receipt=r(("a",),42,0,"a"*32+"-1")
            self.assertEqual(receipt["outcome"],"invalid")
            self.assertIsNone(receipt["fingerprint"])
            popen.assert_not_called()
        self.assertTrue((r.output/("a"*32+"-1")/"receipt.json").is_file())
    def test_never_overwrite_evidence(self):
        r=self.runner();trial_id="a"*32+"-1"
        (r.output/trial_id).mkdir()
        with self.assertRaises(FileExistsError):r(("a",),42,0,trial_id)

if __name__=="__main__":unittest.main()

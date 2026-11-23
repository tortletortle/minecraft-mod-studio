import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("audit-corpus-report.py")


class CorpusReportAuditorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.jars = self.root / "jars"
        self.reports = self.root / "reports"
        self.jars.mkdir()
        self.reports.mkdir()
        self.jar_name = "demo-version-demo.jar"
        self.jar_bytes = b"synthetic jar bytes for report cross-check"
        (self.jars / self.jar_name).write_bytes(self.jar_bytes)
        self.sha256 = hashlib.sha256(self.jar_bytes).hexdigest()
        self.sha512 = hashlib.sha512(self.jar_bytes).hexdigest()
        self.manifest = self.root / "manifest-26.2-fabric.csv"
        self.report = self.reports / "umpd-26.2-fabric.json"
        self.write_manifest()
        self.write_report()

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, filename=None, sha256=None):
        with self.manifest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                "project_name", "modrinth_slug", "category", "selected_minecraft_version",
                "loader_target", "modrinth_version_id", "local_file_name", "size_bytes",
                "sha256", "sha512", "scanner_status", "manual_audit_status"
            ])
            writer.writeheader()
            writer.writerow({
                "project_name": "Demo", "modrinth_slug": "demo", "category": "api",
                "selected_minecraft_version": "26.2", "loader_target": "fabric",
                "modrinth_version_id": "version-id", "local_file_name": filename or self.jar_name,
                "size_bytes": len(self.jar_bytes), "sha256": sha256 or self.sha256,
                "sha512": self.sha512, "scanner_status": "DOWNLOADED", "manual_audit_status": "PENDING"
            })

    def write_report(self, *, input_dir=None, artifact_file=None, artifact_sha=None, artifacts=None):
        artifact = {
            "file": artifact_file or self.jar_name,
            "sizeBytes": len(self.jar_bytes),
            "sha256": artifact_sha or self.sha256,
            "status": "SCANNED",
            "loader": "FABRIC",
            "protocols": ["DFU_CODEC"],
            "modIds": ["demo"],
            "protocolEvidence": [{"protocol": "DFU_CODEC", "evidenceLevel": "BYTECODE_CALL_SITE"}],
            "warnings": [],
            "warningOverflow": 0,
            "nestedJarArchivesScanned": 1
        }
        payload = {
            "reportVersion": 1,
            "scanner": "UMPD-0.1.0",
            "createdAt": "2026-11-23T00:00:00Z",
            "inputDirectory": str(input_dir or self.jars.resolve()),
            "summary": {"jarsDiscovered": 1, "jarsScanned": 1, "jarsFailed": 0},
            "classMapping": {"applied": False},
            "artifacts": artifacts if artifacts is not None else [artifact]
        }
        self.report.write_text(json.dumps(payload), encoding="utf-8")

    def run_auditor(self):
        return subprocess.run([
            sys.executable, str(SCRIPT), "--corpus-dir", str(self.root),
            "--minecraft-version", "26.2", "--loader", "fabric",
            "--manifest", str(self.manifest), "--report", str(self.report)
        ], capture_output=True, text=True)

    def test_matched_artifact_and_callsite_observation(self):
        result = self.run_auditor()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        summary = json.loads((self.reports / "crosscheck" / "cohort-summary.json").read_text())
        self.assertEqual(summary["matchedArtifacts"], 1)
        self.assertEqual(summary["protocolArtifactsWithDirectCallSites"], {"DFU_CODEC": 1})
        self.assertIn("not computed", summary["metricsWarning"])

    def test_local_hash_mismatch_is_rejected(self):
        self.write_manifest(sha256="0" * 64)
        result = self.run_auditor()
        self.assertEqual(result.returncode, 1)
        text = (self.reports / "crosscheck" / "cohort-crosscheck.csv").read_text(encoding="utf-8-sig")
        self.assertIn("LOCAL_HASH_MISMATCH", text)

    def test_missing_report_artifact_is_rejected(self):
        self.write_report(artifacts=[])
        result = self.run_auditor()
        self.assertEqual(result.returncode, 1)
        summary = json.loads((self.reports / "crosscheck" / "cohort-summary.json").read_text())
        self.assertEqual(summary["missingFromReport"], 1)

    def test_report_from_different_input_directory_is_rejected(self):
        self.write_report(input_dir=self.root / "somewhere-else")
        result = self.run_auditor()
        self.assertEqual(result.returncode, 1)
        summary = json.loads((self.reports / "crosscheck" / "cohort-summary.json").read_text())
        self.assertFalse(summary["reportInputDirectoryMatchesCorpusJars"])

    def test_manifest_path_traversal_is_rejected(self):
        self.write_manifest(filename="../outside.jar")
        result = self.run_auditor()
        self.assertEqual(result.returncode, 1)
        text = (self.reports / "crosscheck" / "cohort-crosscheck.csv").read_text(encoding="utf-8-sig")
        self.assertIn("INVALID_MANIFEST_FILE_NAME", text)


if __name__ == "__main__":
    unittest.main()

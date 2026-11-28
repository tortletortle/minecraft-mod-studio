from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creature_studio.blockbench import import_bbmodel
from creature_studio.compiler import compile_project
from creature_studio.generator import generate

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples/void_scout"


class CompilerTests(unittest.TestCase):
    def test_compiler_returns_deterministic_in_memory_file_map(self):
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        model_path = SAMPLE / "void_scout.bbmodel"
        model = import_bbmodel(model_path)
        source = model_path.read_bytes()
        first = compile_project(project, model, source)
        second = compile_project(project, model, source)
        self.assertEqual(first.files, second.files)
        self.assertIn("studio-build-manifest.json", first.files)
        manifest = json.loads(first.files["studio-build-manifest.json"])
        self.assertIn("src/main/java/com/example/voidscout/ModMain.java", manifest["files"])
        self.assertEqual(first.report["status"], "COMPILED")
        self.assertEqual(first.report["fileCount"], len(first.files))

    def test_file_generator_persists_the_same_compiler_output(self):
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        model_path = SAMPLE / "void_scout.bbmodel"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "void_scout.bbmodel").write_bytes(model_path.read_bytes())
            project["creature"]["model"]["file"] = "void_scout.bbmodel"
            project_file = input_dir / "creature.json"
            project_file.write_text(json.dumps(project), encoding="utf-8")
            output = root / "output"
            report = generate(project_file, output)
            self.assertEqual(report["status"], "GENERATED")
            self.assertTrue((output / "studio-build-manifest.json").is_file())
            self.assertTrue((output / "source-assets/void_scout.bbmodel").is_file())


if __name__ == "__main__":
    unittest.main()

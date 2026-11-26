from __future__ import annotations

import json
import unittest
from pathlib import Path

from creature_studio.schema import ProjectValidationError, validate_project

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples/void_scout/creature.json"


class SchemaTests(unittest.TestCase):
    def test_sample_project_matches_schema(self):
        project = json.loads(SAMPLE.read_text(encoding="utf-8"))
        validate_project(project, SAMPLE)

    def test_rejects_unsupported_minecraft_version(self):
        project = json.loads(SAMPLE.read_text(encoding="utf-8"))
        project["target"]["minecraftVersion"] = "1.21.1"
        with self.assertRaises(ProjectValidationError):
            validate_project(project, SAMPLE)

    def test_rejects_path_traversal_model_reference(self):
        project = json.loads(SAMPLE.read_text(encoding="utf-8"))
        project["creature"]["model"]["file"] = "../outside.bbmodel"
        with self.assertRaises(ProjectValidationError):
            validate_project(project, SAMPLE)


if __name__ == "__main__":
    unittest.main()

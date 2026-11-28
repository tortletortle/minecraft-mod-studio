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

    def test_rejects_groovy_injection_in_dependency_versions(self):
        project = json.loads(SAMPLE.read_text(encoding="utf-8"))
        project["target"]["renderBackend"] = "geckolib"
        project["target"]["geckolibVersion"] = "5.5.8"
        malicious = {
            "fabricLoaderVersion": "0.18.1'\napply plugin: 'evil",
            "fabricApiVersion": '0.100.0"; println("owned")',
            "loomVersion": "1.13.0 { println 'owned' }",
            "geckolibVersion": "5.5.8\nrepositories { mavenCentral() }",
        }
        for field, value in malicious.items():
            with self.subTest(field=field):
                candidate = json.loads(json.dumps(project))
                candidate["target"][field] = value
                with self.assertRaises(ProjectValidationError):
                    validate_project(candidate)

    def test_rejects_java_reserved_identifiers_for_mod_and_creature(self):
        reserved = (
            "abstract", "assert", "boolean", "break", "byte", "case", "catch", "char",
            "class", "const", "continue", "default", "do", "double", "else", "enum",
            "extends", "final", "finally", "float", "for", "goto", "if", "implements",
            "import", "instanceof", "int", "interface", "long", "native", "new",
            "package", "private", "protected", "public", "return", "short", "static",
            "strictfp", "super", "switch", "synchronized", "this", "throw", "throws",
            "transient", "try", "void", "volatile", "while", "null", "true", "false",
            "record", "var", "yield", "sealed", "permits", "module", "open", "exports",
            "requires", "transitive", "uses", "provides", "to", "with", "when",
        )
        for word in reserved:
            with self.subTest(field="modId", word=word):
                candidate = json.loads(SAMPLE.read_text(encoding="utf-8"))
                candidate["project"]["modId"] = word
                with self.assertRaises(ProjectValidationError):
                    validate_project(candidate)
            with self.subTest(field="creature.id", word=word):
                candidate = json.loads(SAMPLE.read_text(encoding="utf-8"))
                candidate["creature"]["id"] = word
                with self.assertRaises(ProjectValidationError):
                    validate_project(candidate)

    def test_rejects_path_traversal_model_reference(self):
        project = json.loads(SAMPLE.read_text(encoding="utf-8"))
        project["creature"]["model"]["file"] = "../outside.bbmodel"
        with self.assertRaises(ProjectValidationError):
            validate_project(project, SAMPLE)


if __name__ == "__main__":
    unittest.main()

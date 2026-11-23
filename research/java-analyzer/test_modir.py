import json
import unittest
from pathlib import Path

from modir import build_modir


def static_report():
    return {
        "schemaVersion": "0.2",
        "analyzer": {"version": "0.2.0"},
        "input": {"fileName": "sample.jar", "sizeBytes": 1024, "sha256": "a" * 64},
        "metadata": {
            "loaderCandidates": ["fabric"],
            "mods": [{
                "loader": "fabric", "id": "sample_mod", "version": "1.0",
                "name": "Sample", "environment": "*"
            }],
            "dependencies": [{
                "id": "fabricloader", "constraint": ">=0.15",
                "kind": "required", "source": "fabric.mod.json"
            }],
            "entrypoints": [{
                "loader": "fabric", "key": "main", "adapter": "default",
                "value": "demo.Main", "source": "fabric.mod.json"
            }],
        },
        "summary": {"classEntries": 1, "classMajorVersions": {"65": 1}},
        "bytecode": {"classes": [{
            "name": "demo/Main", "path": "demo/Main.class", "majorVersion": 65,
            "superclass": "java/lang/Object", "interfaces": [],
            "methodCount": 2, "invocationCount": 1
        }]},
        "mixins": [{
            "path": "sample.mixins.json", "package": "demo.mixin", "environment": "*",
            "mixinClasses": ["demo.mixin.EntityMixin"], "targetClasses": [],
            "targetDiscoveryStatus": "NOT_ANALYZED", "unresolvedMixinClasses": [],
            "plugin": None, "refmap": "sample.refmap.json"
        }],
        "resources": {
            "count": 1, "inventoryTruncated": False,
            "inventory": [{"path": "assets/sample/icon.png", "category": "texture"}]
        }
    }


class ModIRTests(unittest.TestCase):
    def test_schema_document_is_valid_json_and_versioned(self):
        schema_path = Path(__file__).with_name("modir.schema.json")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"], "urn:modir:schema:0.1.0")
        self.assertEqual(schema["properties"]["schemaVersion"]["const"], "0.1.0")

    def test_builds_provenance_graph_without_inventing_migration_support(self):
        report = build_modir(static_report())
        self.assertEqual(report["schemaVersion"], "0.1.0")
        self.assertEqual(report["artifact"]["sha256"], "a" * 64)
        self.assertIsNone(report["targetProfile"])
        self.assertEqual(report["mappings"], [])
        self.assertEqual(report["migrationAssessment"]["overallStatus"], "UNASSESSED")
        self.assertEqual(report["entities"]["entrypoints"][0]["adapter"], "default")
        self.assertEqual(report["entities"]["classes"][0]["internalName"], "demo/Main")
        self.assertEqual(report["entities"]["mixinConfigs"][0]["targetDiscoveryStatus"], "NOT_ANALYZED")
        evidence_ids = [item["id"] for item in report["evidence"]]
        self.assertEqual(len(evidence_ids), len(set(evidence_ids)))
        referenced = []
        for group in report["entities"].values():
            for entity in group:
                if entity.get("evidenceId"):
                    referenced.append(entity["evidenceId"])
                referenced.extend(entity.get("annotationEvidenceIds", []))
        self.assertTrue(set(referenced).issubset(set(evidence_ids)))

    def test_asm_enrichment_is_joined_by_exact_artifact_hash(self):
        static = static_report()
        asm = {
            "input": {"sha256": "a" * 64},
            "summary": {"passed": True},
            "classes": [{
                "path": "demo/Main.class",
                "status": "COMPARED",
                "classIdentityEqual": True,
                "methodSignaturesEqual": True,
                "invocationsEqual": True,
                "invocationsTruncated": False,
                "invokedynamicEqual": True,
                "asm": {"className": "demo/Main"}
            }],
            "mixins": [{
                "path": "sample.mixins.json", "package": "demo.mixin", "environment": "*",
                "mixinClasses": ["demo.mixin.EntityMixin"],
                "targetClasses": ["net/minecraft/world/entity/Entity"],
                "targetDiscoveryStatus": "COMPLETE", "unresolvedMixinClasses": [],
                "plugin": None, "refmap": "sample.refmap.json",
                "mixinClassEvidence": [{
                    "mixinClass": "demo.mixin.EntityMixin",
                    "classEntryPath": "demo/mixin/EntityMixin.class",
                    "annotationPresent": True,
                    "targetClasses": ["net/minecraft/world/entity/Entity"],
                    "status": "TARGETS_FOUND"
                }]
            }]
        }
        report = build_modir(static, asm)
        self.assertTrue(report["coverage"]["asmDifferentialRun"])
        self.assertTrue(report["coverage"]["asmDifferentialPassed"])
        self.assertEqual(
            report["entities"]["mixinConfigs"][0]["targetClasses"],
            ["net/minecraft/world/entity/Entity"]
        )
        class_evidence = next(x for x in report["evidence"] if x["kind"] == "class_header")
        self.assertEqual(class_evidence["verification"], "parser_cross_checked")
        annotation_evidence = next(x for x in report["evidence"] if x["kind"] == "annotation")
        self.assertEqual(annotation_evidence["source"]["entryPath"], "demo/mixin/EntityMixin.class")

    def test_rejects_asm_report_from_a_different_jar(self):
        asm = {"input": {"sha256": "b" * 64}, "summary": {}, "classes": [], "mixins": []}
        with self.assertRaises(ValueError):
            build_modir(static_report(), asm)


if __name__ == "__main__":
    unittest.main()

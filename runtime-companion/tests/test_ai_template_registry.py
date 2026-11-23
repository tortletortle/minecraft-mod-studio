import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from ai_template_registry import (  # noqa: E402
    DEFAULT_CATALOG_PATH,
    TemplateRegistry,
    TemplateRegistryError,
    validate_catalog,
)


class TemplateRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = TemplateRegistry()

    def test_catalog_loads_and_lists_all_seven_templates(self):
        self.assertEqual(self.registry.count, 7)
        templates = self.registry.list_templates(limit=32)
        self.assertEqual(len(templates), 7)
        self.assertEqual(len({item["id"] for item in templates}), 7)

    def test_category_and_mode_filters_are_applied(self):
        builders = self.registry.list_templates(category="world_design")
        self.assertEqual([item["id"] for item in builders], ["world-builder"])
        read_only = self.registry.list_templates(mode="read_only", limit=32)
        self.assertEqual(
            {item["id"] for item in read_only},
            {"mod-understanding", "command-finder", "diagnostics"},
        )

    def test_get_template_returns_a_detached_copy(self):
        first = self.registry.get_template("world-builder")
        first["name"] = "tampered"
        second = self.registry.get_template("world-builder")
        self.assertEqual(second["name"], "世界与建筑规划")

    def test_router_recommends_world_builder_for_a_build_request(self):
        result = self.registry.route_task("帮我设计一座城堡建筑蓝图")
        self.assertEqual(result["routing_status"], "recommended")
        self.assertEqual(result["recommended_template_id"], "world-builder")
        self.assertFalse(result["execution_started"])

    def test_router_recommends_diagnostics_for_a_crash_report(self):
        result = self.registry.route_task("游戏启动后崩溃了")
        self.assertEqual(result["routing_status"], "recommended")
        self.assertEqual(result["recommended_template_id"], "diagnostics")

    def test_router_does_not_guess_when_no_intent_matches(self):
        result = self.registry.route_task("你好")
        self.assertEqual(result["routing_status"], "no_match")
        self.assertIsNone(result["recommended_template_id"])
        self.assertFalse(result["execution_started"])

    def test_capability_adapter_checks_exact_bridge_commands(self):
        capabilities = {
            "inspect_entity",
            "entity_attributes",
            "set_entity_attribute",
            "reset_entity_attributes",
        }
        result = self.registry.resolve_capabilities(
            "entity-workbench",
            bridge_capabilities=capabilities,
            runtime_status="connected",
        )
        self.assertTrue(result["required_capabilities_satisfied"])
        self.assertEqual(result["effective_mode"], "approval_gated")
        resolved = {item["name"]: item for item in result["capabilities"]}
        self.assertEqual(resolved["entity.inspect"]["status"], "available")
        self.assertEqual(resolved["entity.attribute.read"]["status"], "available")
        self.assertEqual(resolved["entity.attribute.write_bounded"]["status"], "available")
        self.assertTrue(resolved["entity.attribute.write_bounded"]["approval_required"])
        self.assertEqual(result["permissions_granted"], [])
        self.assertFalse(result["execution_enabled"])

    def test_missing_required_capabilities_force_a_narrower_fallback(self):
        result = self.registry.resolve_capabilities(
            "world-builder",
            bridge_capabilities={"block"},
            runtime_status="connected",
        )
        self.assertFalse(result["required_capabilities_satisfied"])
        self.assertEqual(result["effective_mode"], "plan_only_with_explicit_unknowns")
        self.assertIn("world.region.inspect", result["missing_required"])

    def test_unavailable_runtime_is_not_reported_as_an_empty_successful_runtime(self):
        result = self.registry.resolve_capabilities(
            "entity-workbench",
            bridge_capabilities=None,
            runtime_status="unavailable",
        )
        self.assertEqual(result["runtime_status"], "unavailable")
        self.assertFalse(result["required_capabilities_satisfied"])
        self.assertTrue(
            all(
                item["status"] == "runtime_unavailable"
                for item in result["capabilities"]
                if item["source"] == "fabric_companion_bridge"
            )
        )

    def test_catalog_rejects_an_unapproved_mutation_step(self):
        catalog = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
        target = next(item for item in catalog["templates"] if item["id"] == "world-builder")
        target["workflow"][0]["operationClass"] = "mutation"
        target["workflow"][0]["approval"] = "not_required"
        with self.assertRaises(TemplateRegistryError):
            validate_catalog(catalog)

    def test_catalog_rejects_generic_command_execution_capability(self):
        catalog = json.loads(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
        target = next(item for item in catalog["templates"] if item["id"] == "command-finder")
        target["optionalCapabilities"].append("command.execute")
        with self.assertRaises(TemplateRegistryError):
            validate_catalog(catalog)

    def test_duplicate_json_fields_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text('{"schemaVersion":"1.0.0","schemaVersion":"1.0.0"}', encoding="utf-8")
            with self.assertRaises(TemplateRegistryError):
                TemplateRegistry(path)


if __name__ == "__main__":
    unittest.main()

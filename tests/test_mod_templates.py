import copy
import json
import unittest
from pathlib import Path

from scripts.validate_mod_templates import ROOT, load_catalog, validate_catalog


class ModTemplateCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()

    def test_catalog_is_valid(self):
        self.assertEqual(validate_catalog(self.catalog), [])

    def test_template_ids_are_unique(self):
        ids = [item["id"] for item in self.catalog["templates"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_template_has_localized_content(self):
        for template in self.catalog["templates"]:
            for field in ("name", "description", "limitations"):
                self.assertEqual(set(template[field]), {"zh-CN", "en-US"})

    def test_design_only_templates_are_not_mislabeled_as_codegen(self):
        for template in self.catalog["templates"]:
            kinds = {resource["kind"] for resource in template["resources"]}
            if kinds - {"items", "blocks"}:
                self.assertEqual(template["supportLevel"], "design_only")

    def test_relationships_use_template_keys_not_uids(self):
        for template in self.catalog["templates"]:
            keys = {resource["key"] for resource in template["resources"]}
            for relation in template["relations"]:
                self.assertIn(relation["from"], keys)
                self.assertIn(relation["to"], keys)


    def test_embedded_browser_catalog_matches_canonical_json(self):
        html = (ROOT / "Minecraft_Mod_Studio_V25.html").read_text(encoding="utf-8")
        marker = "const MMT_CATALOG="
        start = html.index(marker) + len(marker)
        end = html.index(";\\nconst MMT_COPY", start)
        embedded = json.loads(html[start:end])
        self.assertEqual(embedded, self.catalog)

    def test_malformed_nested_values_return_errors_instead_of_crashing(self):
        mutations = []

        data = copy.deepcopy(self.catalog)
        data["templates"][0]["id"] = []
        mutations.append(data)

        data = copy.deepcopy(self.catalog)
        data["templates"][0]["resources"][0]["key"] = {"bad": "key"}
        mutations.append(data)

        data = copy.deepcopy(self.catalog)
        data["templates"][5]["relations"][0]["from"] = []
        mutations.append(data)

        data = copy.deepcopy(self.catalog)
        data["templates"][13]["resources"][0]["properties"]["components"][0]["type"] = []
        mutations.append(data)

        data = copy.deepcopy(self.catalog)
        data["categories"][0]["id"] = []
        mutations.append(data)

        for malformed in mutations:
            with self.subTest(malformed=malformed):
                self.assertTrue(validate_catalog(malformed))

    def test_duplicate_recipe_slots_are_rejected(self):
        data = copy.deepcopy(self.catalog)
        template = next(t for t in data["templates"] if t["id"] == "ore-progression-pack")
        template["relations"].append({
            "type": "item_recipe",
            "from": "weapon",
            "to": "raw_ore",
            "slot": 4,
        })
        errors = validate_catalog(data)
        self.assertTrue(any("duplicate item_recipe slot" in error for error in errors))

    def test_categories_are_unique_and_complete(self):
        data = copy.deepcopy(self.catalog)
        data["categories"].append(copy.deepcopy(data["categories"][0]))
        errors = validate_catalog(data)
        self.assertTrue(any("duplicate category id" in error for error in errors))

    def test_no_executable_source_is_embedded(self):
        forbidden = {"javaSource", "sourceCode", "javascript", "script", "shellCommand", "commandText", "eval"}
        def walk(value):
            if isinstance(value, dict):
                self.assertFalse(forbidden.intersection(value))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.catalog)


if __name__ == "__main__":
    unittest.main()

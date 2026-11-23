import unittest

from scripts.validate_mod_templates import load_catalog, validate_catalog


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

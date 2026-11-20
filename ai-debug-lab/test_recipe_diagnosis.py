import unittest
from recipe_diagnosis import diagnose_recipe

def evidence():
    k={"schema":1,"archives":[{"jar":"a.jar","mod_id":"a","version":"1","sha256":"a"*64}],
       "resources":[{"jar":"a.jar","kind":"recipe","id":"a:out","path":"data/a/recipe/out.json","serializer":"minecraft:crafting_shapeless","recognized":True}],
       "edges":[{"source":0,"relation":"requires","target_kind":"item","target":"a:missing"},
                {"source":0,"relation":"requires","target_kind":"tag","target":"c:metal"},
                {"source":0,"relation":"produces","target_kind":"item","target":"a:out"}]}
    s={"schema":1,"session":"12345678-1234-1234-1234-123456789abc","at":"2026-11-20T00:00:00Z",
       "registrations":{"items":["a:out"],"items_total":1,"mods":[{"id":"a","version":"1"}],"mods_total":1}}
    return k,s

class DiagnosisTests(unittest.TestCase):
    def test_join(self):
        k,s=evidence();r=diagnose_recipe(k,s,"a:out")
        self.assertEqual(r["status"],"hypotheses_only")
        self.assertEqual([x["kind"] for x in r["hypotheses"]],["unregistered_item_reference","tag_resolution_unknown"])
        self.assertEqual(r["declarations"][0]["source"]["runtime_alignment"],"id_version_match")
        self.assertTrue(all(x["status"]=="unverified" for x in r["hypotheses"]))
    def test_truncated_registry(self):
        k,s=evidence();s["registrations"]["items_total"]=100
        r=diagnose_recipe(k,s,"a:out")
        self.assertNotIn("unregistered_item_reference",[x["kind"] for x in r["hypotheses"]])
        self.assertEqual(r["declarations"][0]["references"][0]["status"],"unknown_truncated_registry")
    def test_version_mismatch(self):
        k,s=evidence();s["registrations"]["mods"][0]["version"]="2"
        self.assertEqual(diagnose_recipe(k,s,"a:out")["hypotheses"][0]["kind"],"workspace_runtime_mismatch")
    def test_truncated_mod_list(self):
        k,s=evidence();s["registrations"].update(mods=[],mods_total=2)
        self.assertEqual(diagnose_recipe(k,s,"a:out")["declarations"][0]["source"]["runtime_alignment"],"unknown_truncated_mod_list")
    def test_duplicate_declarations(self):
        k,s=evidence();k["resources"].append(dict(k["resources"][0]))
        self.assertIn("multiple_recipe_declarations",[x["kind"] for x in diagnose_recipe(k,s,"a:out")["hypotheses"]])
    def test_unknown_recipe(self):
        k,s=evidence();self.assertEqual(diagnose_recipe(k,s,"a:other")["hypotheses"][0]["kind"],"no_indexed_declaration")
    def test_no_missing_if_present(self):
        k,s=evidence();s["registrations"]["items"].append("a:missing");s["registrations"]["items_total"]=2
        self.assertNotIn("unregistered_item_reference",[x["kind"] for x in diagnose_recipe(k,s,"a:out")["hypotheses"]])
    def test_invalid_evidence(self):
        k,s=evidence();s["registrations"]["items_total"]=0
        with self.assertRaises(ValueError):diagnose_recipe(k,s,"a:out")
        k,s=evidence()
        with self.assertRaises(ValueError):diagnose_recipe(k,s,"../bad")

if __name__=="__main__":unittest.main()

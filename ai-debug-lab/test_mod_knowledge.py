import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from mod_knowledge import index,recipe_refs,identifier

class KnowledgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
    def jar(self,name,entries):
        with zipfile.ZipFile(self.root/name,"w") as z:
            for p,v in entries.items():z.writestr(p,json.dumps(v) if isinstance(v,dict) else v)
    def test_cross_jar_shared_tag(self):
        self.jar("a.jar",{"fabric.mod.json":{"id":"a","version":"1"},"data/a/recipe/plate.json":{"type":"minecraft:crafting_shapeless","ingredients":["#c:ingots/copper"],"result":{"id":"a:plate"}}})
        self.jar("b.jar",{"fabric.mod.json":{"id":"b","version":"1"},"data/c/tags/item/ingots/copper.json":{"values":["b:copper_ingot"]},"data/b/recipes/gear.json":{"type":"minecraft:crafting_shaped","key":{"X":{"tag":"c:ingots/copper"}},"result":{"item":"b:gear"}}})
        r=index(self.root)
        self.assertEqual(len(r["resources"]),3)
        self.assertIn({"kind":"tag","id":"c:ingots/copper","jars":["a.jar","b.jar"]},r["shared_references"])
        self.assertTrue(any(e["target"]=="b:copper_ingot" for e in r["edges"]))
        self.assertEqual(len(r["archives"][0]["sha256"]),64)
    def test_duplicate_declarations_not_conflicts(self):
        for name in ["a.jar","b.jar"]:
            self.jar(name,{"data/c/tags/items/ores.json":{"values":["minecraft:iron_ore"]}})
        r=index(self.root)
        self.assertEqual(len(r["multiple_declarations"]),1)
    def test_unknown_serializer_no_fake_edges(self):
        self.jar("a.jar",{"data/a/recipe/x.json":{"type":"a:magic","input":"minecraft:diamond","result":"a:artifact"}})
        r=index(self.root);self.assertFalse(r["resources"][0]["recognized"]);self.assertEqual(r["edges"],[])
    def test_invalid_path_and_json(self):
        self.jar("a.jar",{"data/a/recipe/../bad.json":{},"data/a/recipe/bad.json":'{"x":1,"x":2}',"data/a/recipe/big.json":"x"*270000})
        r=index(self.root);self.assertEqual(len(r["resources"]),0);self.assertEqual(len(r["issues"]),3)
    def test_bad_archive(self):
        (self.root/"bad.jar").write_bytes(b"bad")
        self.assertEqual(index(self.root)["archives"][0]["status"],"unreadable")
    def test_old_and_new_ingredients(self):
        _,refs,recognized=recipe_refs({"type":"minecraft:smelting","ingredient":{"item":"iron_ore"},"result":"iron_ingot"})
        self.assertTrue(recognized)
        self.assertIn(("requires","item","minecraft:iron_ore"),refs)
    def test_identifier(self):
        self.assertIsNone(identifier("a:../b"));self.assertIsNone(identifier("x:bad path"))
        self.assertEqual(identifier("stone"),"minecraft:stone")
if __name__=="__main__":unittest.main()

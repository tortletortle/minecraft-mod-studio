import io
import json
import tempfile
import unittest
from pathlib import Path
from ide_bridge import Bridge, serve

class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"mods").mkdir()
        (self.root/"logs").mkdir()
        (self.root/"logs/latest.log").write_text("untrusted mod message")
        self.calls=[]
        def observe(*args):
            self.calls.append(args)
            return {"measurements":[]}
        self.bridge=Bridge(self.root,"secret",observer=observe)

    def call(self,name,arguments):
        return self.bridge.dispatch({"id":1,"method":"tools.call","params":{"name":name,"arguments":arguments}})

    def test_discovery(self):
        result=self.bridge.dispatch({"id":2,"method":"tools.list","params":{}})["result"]
        self.assertEqual(len(result["tools"]),6)
        self.assertFalse(result["capabilities"]["write"])
        self.assertNotIn("secret",json.dumps(result))

    def test_typed_observation(self):
        self.assertTrue(self.call("game.observe",{"operations":[{"op":"ticks"}]})["ok"])
        self.assertEqual(len(self.calls),1)
        for args in [{"operations":[{"op":"stop"}]},{"operations":[{"op":"ticks"}],"repeat":True},
                     {"operations":[{"op":"ticks"}],"password":"x"},{"operations":[{"op":"ticks"}],"host":"other"}]:
            self.assertFalse(self.call("game.observe",args)["ok"])
        self.assertEqual(len(self.calls),1)

    def test_fixed_workspace(self):
        self.assertTrue(self.call("mods.inventory",{})["ok"])
        self.assertFalse(self.call("mods.inventory",{"path":"../"})["ok"])
        self.assertEqual(self.call("logs.tail",{})["result"]["text"],"untrusted mod message")
        self.assertFalse(self.call("logs.tail",{"path":"../../secret"})["ok"])

    def test_symlink_denied(self):
        p=self.root/"logs/latest.log";p.unlink()
        p.symlink_to(self.root/"missing")
        self.assertFalse(self.call("logs.tail",{})["ok"])

    def test_jsonl_stream(self):
        q={"id":"a","method":"tools.list","params":{}}
        source=io.BytesIO(b"not json\n"+json.dumps(q).encode()+b"\n")
        sink=io.StringIO();serve(self.bridge,source,sink)
        results=[json.loads(s) for s in sink.getvalue().splitlines()]
        self.assertFalse(results[0]["ok"])
        self.assertEqual(results[1]["id"],"a")
        self.assertTrue(results[1]["ok"])

    def test_oversize_rejected(self):
        sink=io.StringIO()
        serve(self.bridge,io.BytesIO(b"x"*70000+b"\n"),sink)
        self.assertFalse(json.loads(sink.getvalue())["ok"])

    def test_no_rcon(self):
        self.bridge.password=None
        self.assertFalse(self.call("game.observe",{"operations":[{"op":"players"}]})["ok"])
        self.assertEqual(self.calls,[])

    def test_native_snapshot(self):
        ident="12345678-1234-1234-1234-123456789abc"
        path=self.root/"mms-debug"/ident/"snapshot.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema":1,"session":ident,"registrations":{"items":["mod:item"]}}))
        result=self.call("game.native_snapshot",{"session":ident})
        self.assertTrue(result["ok"])
        self.assertEqual(result["result"]["data"]["registrations"]["items"],["mod:item"])
        self.assertFalse(self.call("game.native_snapshot",{"session":"../../"})["ok"])
        path.write_text(json.dumps({"schema":1,"session":"wrong"}))
        self.assertFalse(self.call("game.native_snapshot",{"session":ident})["ok"])

    def test_recipe_diagnosis_bridge(self):
        import zipfile
        ident="12345678-1234-1234-1234-123456789abc"
        path=self.root/"mms-debug"/ident/"snapshot.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"schema":1,"session":ident,"at":"2026-11-20T00:00:00Z","registrations":{"items":["a:out"],"items_total":1,"mods":[{"id":"a","version":"1"}],"mods_total":1}}))
        with zipfile.ZipFile(self.root/"mods/a.jar","w") as z:
            z.writestr("fabric.mod.json",json.dumps({"id":"a","version":"1"}))
            z.writestr("data/a/recipe/out.json",json.dumps({"type":"minecraft:crafting_shapeless","ingredients":["minecraft:stone"],"result":{"id":"a:out"}}))
        result=self.call("mods.diagnose_recipe",{"recipe":"a:out","session":ident})
        self.assertTrue(result["ok"],result)
        self.assertEqual(result["result"]["data"]["hypotheses"][0]["kind"],"unregistered_item_reference")
        self.assertFalse(self.call("mods.diagnose_recipe",{"recipe":"a:out","session":ident,"path":"../"})["ok"])

    def test_bad_id(self):
        self.assertFalse(self.bridge.dispatch({"id":[],"method":"tools.list","params":{}})["ok"])

if __name__=="__main__": unittest.main()

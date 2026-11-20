import json
import tempfile
import unittest
import sys
from pathlib import Path
from mcp import Client, StdioServerParameters
from mcp_adapter import build_server
from ide_bridge import Bridge

SESSION="12345678-1234-1234-1234-123456789abc"
BASE={"mods_inventory","game_native_snapshot","game_recipe_status","mods_diagnose_recipe","trials_summarize"}

class MCPTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        (self.root/"mods").mkdir()
        (self.root/"logs").mkdir()
        (self.root/"logs/latest.log").write_text("untrusted fixture")
        p=self.root/"mms-debug"/SESSION/"snapshot.json"
        p.parent.mkdir(parents=True)
        p.write_text(json.dumps({"schema":1,"session":SESSION,"at":"2026-11-20T00:00:00Z","recipe_probe":{"recipe":{"id":"a:out","status":"present"}}}))
        self.observed=[]
        def observe(*args):
            self.observed.append(args)
            return {"measurements":[]}
        self.bridge=Bridge(self.root,"secret",observer=observe)

    async def test_default_discovery(self):
        async with Client(build_server(self.bridge),raise_exceptions=True) as c:
            tools=(await c.list_tools()).tools
            self.assertEqual({t.name for t in tools},BASE)
            self.assertTrue(all(t.annotations.read_only_hint for t in tools))
            self.assertFalse((await c.call_tool("game_native_snapshot",{"session":SESSION})).is_error)
            self.assertTrue((await c.call_tool("game_native_snapshot",{"session":"../bad"})).is_error)
            self.assertTrue((await c.call_tool("game_observe",{"operations":[{"op":"stop"}]})).is_error)

    async def test_opt_in(self):
        async with Client(build_server(self.bridge,allow_logs=True,allow_rcon=True),raise_exceptions=True) as c:
            self.assertEqual({t.name for t in (await c.list_tools()).tools},BASE|{"logs_tail","game_tick_observe"})
            self.assertFalse((await c.call_tool("logs_tail",{})).is_error)
            self.assertFalse((await c.call_tool("game_tick_observe",{"operations":["ticks","gametime"]})).is_error)
            self.assertEqual(len(self.observed),1)
            for args in [{"operations":["stop"]},{"operations":["ticks"],"repeat":True},{"operations":["entity_nbt"]}]:
                self.assertTrue((await c.call_tool("game_tick_observe",args)).is_error)
            self.assertEqual(len(self.observed),1)

    async def test_stdio_subprocess(self):
        script=Path(__file__).with_name("mcp_adapter.py").resolve()
        params=StdioServerParameters(command=sys.executable,args=[str(script),"--workspace",str(self.root)])
        async with Client(params) as c:
            self.assertEqual({t.name for t in (await c.list_tools()).tools},BASE)
            ans=await c.call_tool("mods_inventory",{})
            self.assertFalse(ans.is_error)
            self.assertTrue(ans.structured_content is not None)
            ans=await c.call_tool("game_recipe_status",{"session":SESSION})
            self.assertFalse(ans.is_error)

if __name__=="__main__":unittest.main()

"""Actual MCP client exercising a fresh Java Fabric server; not an LLM."""
import asyncio
import argparse
import json
import sys
import time
from pathlib import Path
from mcp import Client,StdioServerParameters

async def main(assets,evidence):
    args=[str(Path(__file__).with_name("playtest.py").resolve()),"serve","--assets",str(assets.resolve()),"--evidence",str(evidence.resolve()),"--accept-eula"]
    params=StdioServerParameters(command=sys.executable,args=args)
    transcript=[]
    async with Client(params) as c:
        names={t.name for t in (await c.list_tools()).tools}
        assert {"playtest_status","playtest_set_block","playtest_tick_steps","game_recipe_status"}<=names,names
        async def call(name,args):
            ans=await c.call_tool(name,args)
            assert not ans.is_error,(name,ans)
            data=ans.structured_content["evidence"]
            transcript.append({"tool":name,"arguments":args,"result":data})
            return data
        end=time.monotonic()+300
        while True:
            status=await call("playtest_status",{})
            if status["status"]=="ready":break
            assert status["status"] in ("starting","waiting_for_probe"),status
            assert time.monotonic()<end,"startup timeout"
            await asyncio.sleep(2)
        session=status["session"]
        inv=await call("mods_inventory",{})
        assert any(j.get("id")=="mms_playtest" for j in inv["data"]["jars"]),inv
        recipe=await call("game_recipe_status",{"session":session})
        assert recipe["data"]["recipe"]["experiment"]["output"]=="minecraft:emerald",recipe
        for block in ("minecraft:chest","minecraft:stone"):
            result=await call("playtest_set_block",{"block":block})
            assert result["status"]=="verified",result
        result=await call("playtest_tick_steps",{"steps":[1,5]})
        assert result["status"]=="passed" and result["cleanup"]=="verified_running",result
        assert [e["delta"] for e in result["events"] if e["kind"]=="step_verified"]==[1,5]
        bad=await c.call_tool("playtest_set_block",{"block":"minecraft:tnt"})
        assert bad.is_error,"invalid block accepted"
    (evidence/"mcp-transcript.json").write_text(json.dumps(transcript,indent=2))
    print("MMS_REAL_MCP_PLAYTEST_PASS")

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--assets",type=Path,required=True);p.add_argument("--evidence",type=Path,required=True)
    a=p.parse_args();a.evidence.mkdir(parents=True,exist_ok=True);asyncio.run(main(a.assets,a.evidence))

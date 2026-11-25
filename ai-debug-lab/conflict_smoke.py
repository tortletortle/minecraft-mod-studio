"""Real Fabric conflict: two independent tick listeners alter the same output."""
import argparse
import json
import time
from pathlib import Path
from debug_lab import query
from fault_minimizer import minimize
from isolated_runner import IsolatedRunner
from probe_smoke import download,LAUNCHER,API
from live_smoke import download_server,until

TARGET="fixture:double_transform_obsidian"
GRAPH={"fabric_api":[],"fixture_lib":[],"fixture_alpha":["fabric_api","fixture_lib"],
       "fixture_beta":["fabric_api"],"fixture_noise":[]}

def predicate(console,read,proc):
    def matches(pos,block):
        raw=read({"op":"block_matches","dimension":"minecraft:overworld","pos":pos,"block":"minecraft:"+block})
        if "test passed" in raw.lower():return True
        if "test failed" in raw.lower():return False
        # Unloaded chunk and malformed response are not clean controls.
        raise ValueError("unrecognized block test: "+raw[:150])
    def setblock(pos,block):
        console("execute in minecraft:overworld run setblock "+" ".join(map(str,pos))+" minecraft:"+block)
    trigger=[0,80,0];output=[1,80,0]
    console("execute in minecraft:overworld run forceload add 0 0")
    def setup():
        setblock(trigger,"stone");setblock(output,"white_wool")
        return matches(trigger,"stone") and matches(output,"white_wool")
    until(setup,35,proc)
    setblock(trigger,"diamond_block")
    until(lambda:matches(trigger,"diamond_block"),15,proc)
    def gametime():
        import re
        m=re.fullmatch(r"The game time is ([0-9]+) tick\(s\)",read({"op":"gametime"}).strip())
        if not m:raise ValueError("invalid game time")
        return int(m.group(1))
    start=gametime()
    until(lambda:gametime()>=start+40,20,proc)
    states=[block for block in ("white_wool","red_wool","obsidian") if matches(output,block)]
    if len(states)!=1 or not matches(trigger,"diamond_block"):
        return {"outcome":"invalid","fingerprint":None,"states":states}
    end=gametime()
    return {"outcome":"observed" if states==["obsidian"] else "absent",
            "fingerprint":TARGET if states==["obsidian"] else None,
            "output":states[0],"trigger":"diamond_block","start":start,"end":end}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--fixtures",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--accept-eula",action="store_true")
    a=p.parse_args()
    if not a.accept_eula:p.error("explicit EULA consent required")
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    assets=out/"assets";assets.mkdir()
    download(LAUNCHER,assets/"fabric-server.jar")
    download(API,assets/"fabric-api.jar")
    download_server(assets/"server.jar","26.2")
    jars={k:(assets/"fabric-api.jar" if k=="fabric_api" else a.fixtures/(k+".jar")) for k in GRAPH}
    runner=IsolatedRunner(assets/"fabric-server.jar",assets/"server.jar",jars,out/"trials",predicate,approved=True)
    report=minimize(GRAPH,["fabric_api"],runner,fingerprint=TARGET,seeds=[42,173],repeats=2,budget=64)
    (out/"minimization.json").write_text(json.dumps(report,indent=2))
    assert report["status"]=="candidate_confirmed",report["reason"]
    assert set(report["candidate"])=={"fabric_api","fixture_lib","fixture_alpha","fixture_beta"},report["candidate"]
    # Validate the planted mechanism independently of the search result.
    # A-only must really produce red wool, not silently fail to execute.
    seen=set()
    for row in report["trials"]:
        receipt=json.loads((out/"trials"/row["trial_id"]/"receipt.json").read_text())
        config=set(row["config"])
        alpha,beta="fixture_alpha" in config,"fixture_beta" in config
        expected="obsidian" if alpha and beta else "red_wool" if alpha else "white_wool"
        assert receipt["outcome"]!="invalid",receipt.get("error")
        assert receipt["predicate"]["output"]==expected,(config,receipt["predicate"],expected)
        assert receipt["predicate"]["end"]-receipt["predicate"]["start"]>=40
        seen.add((alpha,beta))
    assert seen=={(False,False),(True,False),(False,True),(True,True)},seen
    print("MMS_REAL_CONFLICT_PASS",report["trials_used"],report["candidate"])
if __name__=="__main__":main()

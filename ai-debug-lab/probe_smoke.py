"""Install production JARs in a fresh Fabric server and read the native probe via IDE."""
import argparse
import json
import hashlib
import shutil
import secrets
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from debug_lab import query
from ide_bridge import Bridge
from native_trace import Trace
from tick_experiment import run_tick_experiment, ExperimentFailure
from live_smoke import free_port, until

LAUNCHER="https://meta.fabricmc.net/v2/versions/loader/26.2/0.20.1/1.1.2/server/jar"
API="https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/0.161.0+26.2/fabric-api-0.161.0+26.2.jar"

def download(url,path):
    with urllib.request.urlopen(url,timeout=90) as f, path.open("wb") as out:
        shutil.copyfileobj(f,out)
def sha(path):
    with path.open("rb") as f: return hashlib.file_digest(f,"sha256").hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--probe",type=Path,required=True)
    p.add_argument("--fixture",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--accept-eula",action="store_true")
    a=p.parse_args()
    if not a.accept_eula: p.error("explicit EULA consent required")
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mms-probe-") as tmp:
        root=Path(tmp);mods=root/"mods";mods.mkdir()
        for src in (a.probe,a.fixture):
            shutil.copyfile(src,mods/src.name)
            assert sha(src)==sha(mods/src.name)
        download(LAUNCHER,root/"fabric-server.jar")
        download(API,mods/"fabric-api.jar")
        # Independent data-only fixture referring to a real Studio-generated item.
        recipe_id="mms_recipe_fixture:gem"
        with zipfile.ZipFile(mods/"mms-recipe-fixture.jar","w") as z:
            z.writestr("fabric.mod.json",json.dumps({"schemaVersion":1,"id":"mms_recipe_fixture","name":"MMS recipe diagnostic fixture","version":"1.0.0","environment":"*","depends":{"stormshard_mod":"*","minecraft":"26.2"}}))
            z.writestr("data/mms_recipe_fixture/recipe/gem.json",json.dumps({"type":"minecraft:crafting_shapeless","ingredients":["minecraft:stone","#minecraft:planks"],"result":{"id":"stormshard_mod:stormshard_gem","count":1}}))
        initial={j.name:sha(j) for j in mods.glob("*.jar")}
        rcon,game=free_port(),free_port()
        while game==rcon:game=free_port()
        password=secrets.token_hex(24)
        (root/"eula.txt").write_text("eula=true\n")
        (root/"server.properties").write_text(f"server-ip=127.0.0.1\nserver-port={game}\nenable-rcon=true\nrcon.port={rcon}\nrcon.password={password}\nlevel-seed=42\nlevel-type=minecraft:flat\nview-distance=3\nsimulation-distance=3\nonline-mode=true\npause-when-empty-seconds=-1\n")
        with (out/"server.log").open("wb") as log:
            proc=subprocess.Popen(["java","-Xmx3G","-Dmms.debug.enabled=true","-Dmms.debug.overworld.pos=0,80,0","-jar","fabric-server.jar","nogui"],cwd=root,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
            def console(cmd):
                proc.stdin.write(cmd+"\n");proc.stdin.flush()
            def ready():
                return "players online" in query({"op":"players"},password,rcon,8).lower()
            def snapshot(block):
                paths=list(root.glob("mms-debug/*/snapshot.json"))
                if len(paths)!=1:return None
                result=Bridge(root).dispatch({"id":1,"method":"tools.call","params":{"name":"game.native_snapshot","arguments":{"session":paths[0].parent.name}}})
                if not result["ok"]:return None
                data=result["result"]["data"]
                return data if data["block"].get("id")==block else None
            try:
                until(ready,300,proc)
                console("execute in minecraft:overworld run forceload add 0 0")
                def chest():
                    console("execute in minecraft:overworld run setblock 0 80 0 minecraft:chest")
                    return snapshot("minecraft:chest")
                first=until(chest,90,proc)
                assert first["block"]["block_entity_type"]=="minecraft:chest",first["block"]
                assert first["dedicated"] is True
                reg=first["registrations"]
                assert {"stormshard_mod","mms_debug_probe"}<={m["id"] for m in reg["mods"]}
                assert "stormshard_mod:stormshard_gem" in reg["items"]
                assert "stormshard_mod:storm_crystal_ore" in reg["blocks"]
                console("execute in minecraft:overworld run setblock 0 80 0 stormshard_mod:storm_crystal_ore")
                second=until(lambda:snapshot("stormshard_mod:storm_crystal_ore"),90,proc)
                assert second["tick_callbacks"]>first["tick_callbacks"]
                assert second["session"]==first["session"]
                trace=Trace(first["session"])
                assert trace.append(first)
                assert not trace.append(first)
                assert trace.append(second)
                report=trace.report("scripted_fixture_complete")
                changes=[e for e in report["events"] if e["type"]=="observed_block_changed"]
                assert len(changes)==1,report
                assert changes[0]["before"]["id"]=="minecraft:chest"
                assert changes[0]["after"]["id"]=="stormshard_mod:storm_crystal_ore"
                (out/"timeline-evidence.json").write_text(json.dumps(report,indent=2))
                print("MMS_NATIVE_TRACE_PASS")
                assert initial=={j.name:sha(j) for j in mods.glob("*.jar")}
                (out/"probe-evidence.json").write_text(json.dumps({"before":first,"after":second,"jar_sha256":initial,"scope":"production jars in standalone dedicated server; no source-set injection"},indent=2))
                print("MMS_NATIVE_PROBE_PASS")
                result=Bridge(root).dispatch({"id":2,"method":"tools.call","params":{"name":"mods.diagnose_recipe","arguments":{"session":second["session"],"recipe":recipe_id}}})
                (out/"recipe-diagnosis.json").write_text(json.dumps(result,indent=2))
                assert result["ok"],result
                diagnosis=result["result"]["data"]
                assert diagnosis["registry_complete"],diagnosis
                assert len(diagnosis["declarations"])==1,diagnosis
                declaration=diagnosis["declarations"][0]
                assert declaration["source"]["runtime_alignment"]=="id_version_match",declaration
                assert declaration["source"]["sha256"]==initial["mms-recipe-fixture.jar"],declaration
                refs={(row["relation"],row["id"]):row["status"] for row in declaration["references"]}
                assert refs[("requires","minecraft:stone")]=="present",refs
                assert refs[("requires","minecraft:planks")]=="runtime_tag_membership_unknown",refs
                assert refs[("produces","stormshard_mod:stormshard_gem")]=="present",refs
                assert diagnosis["status"]=="hypotheses_only"
                print("MMS_RECIPE_DIAGNOSIS_PASS")
                try:
                    exp=run_tick_experiment(proc,lambda op:query(op,password,rcon,8),[1,5,20],approved_disposable=True)
                except ExperimentFailure as exc:
                    (out/"tick-experiment.json").write_text(json.dumps(exc.report,indent=2))
                    raise
                (out/"tick-experiment.json").write_text(json.dumps(exp,indent=2))
                print("MMS_TICK_EXPERIMENT_PASS")
            finally:
                if proc.poll() is None:
                    try:console("stop");proc.wait(timeout=30)
                    except (OSError,subprocess.TimeoutExpired):proc.kill();proc.wait(timeout=10)
if __name__=="__main__":main()

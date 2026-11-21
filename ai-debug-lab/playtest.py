"""Real local AI playtest host; stdio is reserved for MCP. Trusted demo only."""
import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import zipfile
from pathlib import Path
from debug_lab import query
from ide_bridge import Bridge
from live_smoke import free_port,download_server,until
from probe_smoke import download,LAUNCHER,API
from tick_experiment import run_tick_experiment,ExperimentFailure,validate_steps
from runtime_cache import RuntimeCache
from mcp_adapter import build_server

ASSETS=("fabric-server.jar","server.jar","fabric-api.jar","probe.jar")
BLOCKS=("minecraft:chest","minecraft:stone","minecraft:air")
RECIPE="mms_playtest:gem"
from startup_status import StartupTracker, FLAT_SETTINGS
def sha(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

def prepare(root,probe):
    root=Path(root).resolve()
    root.mkdir(parents=True,exist_ok=False)
    shutil.copyfile(probe,root/"probe.jar")
    download(LAUNCHER,root/"fabric-server.jar")
    download(API,root/"fabric-api.jar")
    download_server(root/"server.jar","26.2")
    (root/"hashes.json").write_text(json.dumps({name:sha(root/name) for name in ASSETS},indent=2))

class Playtest:
    def __init__(self,assets,root,evidence,runtime_cache_dir=None):
        self.root,self.evidence=Path(root),Path(evidence)
        self.proc=None
        self.log=None
        self.session=None
        self.start=time.monotonic()
        self.startup=StartupTracker(self.evidence/"server.log",self.start)
        self.password=secrets.token_hex(24)
        self.rcon,self.game=free_port(),free_port()
        while self.rcon==self.game:self.game=free_port()
        self.count=0
        self.dead=False
        hashes=json.loads((assets/"hashes.json").read_text())
        if set(hashes)!=set(ASSETS):raise ValueError("invalid asset manifest")
        self.runtime_cache=RuntimeCache(assets,runtime_cache_dir)
        self.cache_restore=self.runtime_cache.restore(self.root)
        self.cache_publish=None
        self.cache_publish_attempted=False
        (self.root/"mods").mkdir()
        for name in ASSETS:
            path=assets/name
            if path.is_symlink() or not path.is_file() or sha(path)!=hashes[name]:
                raise ValueError("asset drift")
            target=self.root/("mods" if name in ("probe.jar","fabric-api.jar") else "")/name
            shutil.copyfile(path,target)
            if sha(target)!=hashes[name]:raise ValueError("copy drift")
        with zipfile.ZipFile(self.root/"mods/playtest.jar","w") as z:
            z.writestr("fabric.mod.json",json.dumps({"schemaVersion":1,"id":"mms_playtest","name":"MMS playtest fixture","version":"1.0.0","environment":"*","depends":{"minecraft":"26.2"}}))
            z.writestr("data/mms_playtest/recipe/gem.json",json.dumps({"type":"minecraft:crafting_shapeless","ingredients":["minecraft:stone","#minecraft:planks"],"result":{"id":"minecraft:emerald","count":1}}))
        (self.root/"eula.txt").write_text("eula=true\n")
        (self.root/"server.properties").write_text(f"server-ip=127.0.0.1\nserver-port={self.game}\nenable-rcon=true\nrcon.port={self.rcon}\nrcon.password={self.password}\nlevel-seed=42\nlevel-type=minecraft:flat\ngenerator-settings={FLAT_SETTINGS}\nview-distance=3\nsimulation-distance=3\nonline-mode=true\npause-when-empty-seconds=-1\n")
        self.bridge=Bridge(self.root,self.password,self.rcon)
        self.evidence.joinpath("session.json").write_text(json.dumps({"asset_hashes":hashes,"scope":"fresh temporary world","recipe":RECIPE},indent=2))
        self._write_cache_report()
    def _write_cache_report(self):
        report={
            "scope":"Fabric runtime only; no world, mods, config, credentials, or user saves",
            "cache_key":self.runtime_cache.key,
            "restore":self.cache_restore,
            "publish":self.cache_publish,
        }
        temporary=self.evidence/"cache.json.tmp"
        temporary.write_text(json.dumps(report,indent=2),encoding="utf-8")
        temporary.replace(self.evidence/"cache.json")
    def launch(self):
        # Keep the constructor timestamp so ready_elapsed_s includes cache restore
        # and per-instance preparation, not only the Java process lifetime.
        self.startup=StartupTracker(self.evidence/"server.log",self.start)
        self.log=(self.evidence/"server.log").open("wb")
        self.proc=subprocess.Popen(["java","-Xms512M","-Xmx2G","-Dmms.debug.enabled=true","-Dmms.debug.overworld.pos=0,80,0",
            "-Dmms.debug.recipe="+RECIPE,"-Dmms.debug.item_tag=minecraft:planks","-Dmms.debug.recipe_experiment=true",
            "-Dmms.debug.recipe_input=minecraft:stone,minecraft:oak_planks","-jar","fabric-server.jar","nogui"],
            cwd=self.root,stdin=subprocess.PIPE,stdout=self.log,stderr=subprocess.STDOUT,text=True)
    def read(self,op):
        return query(op,self.password,self.rcon,5)
    def console(self,cmd):
        if self.proc is None or self.proc.poll() is not None:raise RuntimeError("test server stopped")
        self.proc.stdin.write(cmd+"\n");self.proc.stdin.flush()
    def status(self):
        result={"scope":"disposable_demo","recipe":RECIPE,"position":[0,80,0],"evidence_dir":str(self.evidence)}
        def report(state):
            data=self.startup.update(state,time.monotonic())
            (self.evidence/"startup.json").write_text(json.dumps(data,indent=2),encoding="utf-8")
            return dict(result,status=state,startup=data)
        if self.dead or self.proc is None or self.proc.poll() is not None:
            return report("stopped")
        ready=False
        try:ready="players online" in self.read({"op":"players"}).lower()
        except (OSError,ValueError,RuntimeError):pass
        sessions=list((self.root/"mms-debug").glob("*/snapshot.json")) if ready else []
        if ready and len(sessions)==1:
            self.session=sessions[0].parent.name
            ready_report=report("ready")
            if not self.cache_publish_attempted:
                self.cache_publish_attempted=True
                if self.cache_restore.get("status")=="hit":
                    self.cache_publish={"status":"not_needed","reason":"cache_hit","elapsed_ms":0.0}
                else:
                    self.cache_publish=self.runtime_cache.publish(self.root)
                self._write_cache_report()
            return dict(ready_report,session=self.session)
        if time.monotonic()-self.start>=self.startup.timeout:
            return report("startup_timeout")
        return report("waiting_for_probe" if ready else "starting")
    def require(self):
        state=self.status()
        if state["status"]!="ready":raise RuntimeError("temporary server not ready")
        if self.count>=24:raise RuntimeError("playtest action budget exhausted")
        self.count+=1
    def record(self,kind,data):
        with (self.evidence/"actions.jsonl").open("a",encoding="utf-8") as f:
            f.write(json.dumps({"action":kind,"sequence":self.count,"data":data},ensure_ascii=True)+"\n")
        return data
    def set_block(self,block):
        if block not in BLOCKS:raise ValueError("block not allowlisted")
        self.require()
        try:
            self.console("execute in minecraft:overworld run forceload add 0 0")
            op={"op":"block_matches","dimension":"minecraft:overworld","pos":[0,80,0],"block":block}
            def place():
                self.console("execute in minecraft:overworld run setblock 0 80 0 "+block)
                raw=self.read(op)
                return raw if "test passed" in raw.lower() else None
            raw=until(place,15,self.proc)
            return self.record("set_block",{"status":"verified","operation":op,"raw_response":raw})
        except (OSError,ValueError,RuntimeError) as exc:
            return self.record("set_block",{"status":"invalid","error_type":type(exc).__name__})
    def tick_steps(self,steps):
        validate_steps(steps)
        self.require()
        try:
            result=run_tick_experiment(self.proc,self.read,steps,approved_disposable=True)
        except ExperimentFailure as exc:
            result=exc.report
            if result.get("cleanup")=="failed_terminate_owned_server":
                self.dead=True
                self.close()
        return self.record("tick_steps",result)
    def close(self):
        if self.proc is not None:
            if self.proc.poll() is None:
                try:self.console("stop");self.proc.wait(timeout=25)
                except (OSError,RuntimeError,subprocess.TimeoutExpired):
                    self.proc.kill();self.proc.wait(timeout=10)
            self.proc.stdin.close()
            self.proc=None
        if self.log:self.log.close();self.log=None

def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest="action",required=True)
    prep=sub.add_parser("prepare")
    prep.add_argument("--assets",type=Path,required=True);prep.add_argument("--probe",type=Path,required=True)
    serve=sub.add_parser("serve")
    serve.add_argument("--assets",type=Path,required=True);serve.add_argument("--evidence",type=Path,required=True)
    serve.add_argument("--runtime-cache-dir",type=Path,default=None,
                       help="Override the shared Fabric runtime cache directory")
    serve.add_argument("--accept-eula",action="store_true")
    a=p.parse_args()
    if a.action=="prepare":
        prepare(a.assets,a.probe);return
    if not a.accept_eula:p.error("Review Minecraft EULA before passing --accept-eula")
    a.evidence.mkdir(parents=True,exist_ok=True)
    evidence=Path(tempfile.mkdtemp(prefix="playtest-",dir=a.evidence.resolve()))
    with tempfile.TemporaryDirectory(prefix="mms-ai-world-") as tmp:
        test=Playtest(a.assets.resolve(),Path(tmp),evidence,a.runtime_cache_dir)
        try:
            test.launch()
            print("MMS AI playtest evidence: "+str(evidence),file=sys.stderr,flush=True)
            build_server(test.bridge,allow_rcon=True,playtest=test).run(transport="stdio")
        finally:test.close()
if __name__=="__main__":main()

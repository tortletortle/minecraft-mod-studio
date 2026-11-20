"""Trusted disposable Fabric trial runner; never attaches to an existing world.

The caller explicitly supplies trusted executable JARs and a trusted predicate.
This is process/data separation, not OS sandboxing of untrusted Java mods.
"""
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from live_smoke import free_port, until
from debug_lab import query

TRIAL_ID=re.compile(r"[0-9a-f]{32}-[1-9][0-9]*")

def digest(path):
    with path.open("rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()

class IsolatedRunner:
    def __init__(self,launcher,server_jar,jars,evidence_dir,predicate,*,approved=False):
        if approved is not True:raise ValueError("explicit trusted fixture and EULA authorization required")
        self.launcher=Path(launcher).resolve(strict=True)
        self.server_jar=Path(server_jar).resolve(strict=True)
        self.jars={k:Path(v).resolve(strict=True) for k,v in jars.items()}
        if not self.jars or len(set(self.jars.values()))!=len(self.jars):raise ValueError("unique JAR paths required")
        if any(not p.is_file() or p.suffix!=".jar" for p in [self.launcher,self.server_jar,*self.jars.values()]):raise ValueError("expected regular JARs")
        if len({p.name for p in self.jars.values()})!=len(self.jars):raise ValueError("JAR filename collision")
        self.hashes={k:digest(p) for k,p in self.jars.items()}
        self.runtime={p.name:digest(p) for p in (self.launcher,self.server_jar)}
        self.output=Path(evidence_dir).resolve()
        self.output.mkdir(parents=True,exist_ok=True)
        self.predicate=predicate

    def __call__(self,config,seed,repeat,trial_id):
        if not TRIAL_ID.fullmatch(trial_id) or not set(config)<=self.jars.keys() or len(set(config))!=len(config):
            raise ValueError("invalid trial parameters")
        if type(seed) is not int or type(repeat) is not int:raise ValueError("invalid seed or repetition")
        dest=self.output/trial_id
        dest.mkdir() # never overwrite evidence
        record={"trial_id":trial_id,"config":list(config),"seed":seed,"repeat":repeat,
                "jars":{k:self.hashes[k] for k in config},"runtime":self.runtime,
                "outcome":"invalid","fingerprint":None,"cleanup":"not_started"}
        start=time.monotonic()
        try:
            with tempfile.TemporaryDirectory(prefix="mms-disposable-") as tmp:
                root=Path(tmp);mods=root/"mods";mods.mkdir()
                for k in config:
                    p=self.jars[k]
                    shutil.copyfile(p,mods/p.name)
                    if digest(mods/p.name)!=self.hashes[k]:raise ValueError("source JAR drift")
                for p in (self.launcher,self.server_jar):
                    if digest(p)!=self.runtime[p.name]:raise ValueError("runtime JAR drift")
                shutil.copyfile(self.launcher,root/"fabric-server.jar")
                shutil.copyfile(self.server_jar,root/"server.jar")
                rcon,game=free_port(),free_port()
                while rcon==game:game=free_port()
                password=secrets.token_hex(24)
                (root/"eula.txt").write_text("eula=true\n")
                (root/"server.properties").write_text(f"server-ip=127.0.0.1\nserver-port={game}\nenable-rcon=true\nrcon.port={rcon}\nrcon.password={password}\nlevel-seed={seed}\nlevel-type=minecraft:flat\nview-distance=3\nsimulation-distance=3\nonline-mode=true\npause-when-empty-seconds=-1\n",encoding="utf-8")
                with (dest/"server.log").open("wb") as log:
                    proc=subprocess.Popen(["java","-Xms256M","-Xmx2G","-jar","fabric-server.jar","nogui"],cwd=root,stdin=subprocess.PIPE,stdout=log,stderr=subprocess.STDOUT,text=True)
                    def console(cmd):
                        if proc.poll() is not None:raise RuntimeError("server exited")
                        proc.stdin.write(cmd+"\n");proc.stdin.flush()
                    def read(op):
                        return query(op,password,rcon,6)
                    try:
                        until(lambda:"players online" in read({"op":"players"}).lower(),120,proc)
                        value=self.predicate(console,read,proc)
                        if not isinstance(value,dict) or value.get("outcome") not in ("observed","absent","invalid"):
                            raise ValueError("invalid predicate result")
                        fp=value.get("fingerprint")
                        if (value["outcome"]=="observed" and (not isinstance(fp,str) or not fp)) or (value["outcome"]!="observed" and fp is not None):
                            raise ValueError("invalid predicate fingerprint")
                        record.update(outcome=value["outcome"],fingerprint=fp,predicate=value)
                        if {p.name:digest(p) for p in mods.glob("*.jar")}!={self.jars[k].name:self.hashes[k] for k in config}:
                            raise ValueError("trial modified mod inventory")
                    finally:
                        if proc.poll() is None:
                            try:
                                console("stop");proc.wait(timeout=25)
                            except (OSError,RuntimeError,subprocess.TimeoutExpired):
                                proc.kill();proc.wait(timeout=10)
                        record["cleanup"]="process_exited"
                        if proc.returncode!=0:
                            record["outcome"]="invalid";record["fingerprint"]=None
                        proc.stdin.close()
        except Exception as exc:
            record.update(outcome="invalid",fingerprint=None,error_type=type(exc).__name__,
                          error=str(exc)[:512])
        record["elapsed_s"]=round(time.monotonic()-start,2)
        data=json.dumps(record,indent=2,sort_keys=True).encode()
        (dest/"receipt.json").write_bytes(data)
        print("MMS_TRIAL",trial_id,record["outcome"],",".join(config),record["elapsed_s"],flush=True)
        return {"trial_id":trial_id,"outcome":record["outcome"],"fingerprint":record["fingerprint"],
                "evidence_id":trial_id+":"+hashlib.sha256(data).hexdigest()}

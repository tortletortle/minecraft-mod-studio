"""Model-agnostic local IDE bridge: JSON Lines over stdio, not MCP or a network server."""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from debug_lab import collect, compile_read, scan_mods, trial_summary
from mod_knowledge import index
from recipe_diagnosis import diagnose_recipe

MAX_LINE = 64 * 1024
MAX_RESULT = 4 * 1024 * 1024
MAX_LOG = 256 * 1024
MAX_SNAPSHOT = 3 * 1024 * 1024

TOOLS = [
    {"name":"mods.diagnose_recipe","description":"Join a namespaced recipe's static declarations to a selected native probe snapshot. Hypotheses only.","arguments":{"session":"canonical session UUID","recipe":"namespaced recipe ID"}},
    {"name":"game.native_snapshot","description":"Read a specific native Fabric probe session snapshot; no live request or world mutation.","arguments":{"session":"canonical session UUID"}},
    {"name":"mods.inventory","description":"Top-level Fabric manifest inventory; not compatibility proof.","arguments":{}},
    {"name":"game.observe","description":"Read-only typed RCON operations against the configured local dedicated server. Raw responses are untrusted.","arguments":{"operations":"list of typed operations, 1-20","repeat":"optional integer 1-3"}},
    {"name":"logs.tail","description":"Bounded tail of workspace logs/latest.log. Untrusted evidence; no interpretation.","arguments":{}},
    {"name":"trials.summarize","description":"Descriptive summary of independent trial records, no causal inference.","arguments":{"trials":"list of trial_id, condition, seed, outcome records"}},
]
OPS = {
    "players":{"required":[]}, "ticks":{"required":[]}, "gametime":{"required":[]},
    "block_nbt":{"required":["dimension","pos"]},
    "block_matches":{"required":["dimension","pos","block"]},
    "entity_nbt":{"required":["dimension","uuid"]},
}

class RequestError(ValueError): pass

class Bridge:
    def __init__(self, workspace, password=None, port=25575, observer=collect):
        self.root = Path(workspace).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("workspace must be a directory")
        self.password, self.port, self.observer = password, port, observer

    def path(self, relative):
        candidate = self.root
        for part in Path(relative).parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise RequestError("workspace symlink refused")
        if not candidate.resolve().is_relative_to(self.root):
            raise RequestError("path outside workspace")
        return candidate

    def call(self, name, args):
        if not isinstance(args, dict):
            raise RequestError("arguments must be an object")
        if name == "game.native_snapshot" and set(args)=={"session"}:
            ident=args["session"]
            if not isinstance(ident,str) or str(uuid.UUID(ident))!=ident:
                raise RequestError("invalid session UUID")
            path=self.path("mms-debug/"+ident+"/snapshot.json")
            if not path.is_file():
                raise RequestError("native snapshot unavailable")
            with path.open("rb") as f:
                raw=f.read(MAX_SNAPSHOT+1)
            if len(raw)>MAX_SNAPSHOT:
                raise RequestError("native snapshot exceeds limit")
            data=json.loads(raw)
            if not isinstance(data,dict) or data.get("schema")!=1 or data.get("session")!=ident:
                raise RequestError("snapshot schema or session mismatch")
            return {"trust":"untrusted_runtime_evidence","data":data,"freshness":"inspect snapshot timestamp; server may have stopped"}
        if name == "mods.diagnose_recipe" and set(args)=={"session","recipe"}:
            snapshot=self.call("game.native_snapshot",{"session":args["session"]})["data"]
            return {"trust":"untrusted_joined_evidence","data":diagnose_recipe(index(self.path("mods")),snapshot,args["recipe"])}
        if name == "mods.inventory" and not args:
            mods = self.path("mods")
            if not mods.is_dir():
                raise RequestError("workspace mods directory missing")
            return {"trust":"untrusted_static_evidence","data":scan_mods(mods)}
        if name == "logs.tail" and not args:
            path = self.path("logs/latest.log")
            if not path.is_file():
                raise RequestError("latest.log unavailable")
            with path.open("rb") as f:
                size = f.seek(0, os.SEEK_END)
                f.seek(max(0,size-MAX_LOG))
                raw = f.read(MAX_LOG)
            return {"trust":"untrusted_log_data","truncated":size>MAX_LOG,
                    "text":raw.decode("utf-8",errors="replace")}
        if name == "game.observe" and set(args) in ({"operations"},{"operations","repeat"}):
            ops = args["operations"]
            repeat = args.get("repeat",1)
            if not isinstance(ops,list) or not 1<=len(ops)<=20 or type(repeat) is not int or not 1<=repeat<=3:
                raise RequestError("sampling limit exceeded")
            for op in ops:
                compile_read(op)
            if not self.password:
                raise RequestError("RCON not configured by local operator")
            return {"trust":"untrusted_runtime_evidence","data":self.observer(ops,self.password,self.port,repeat,0.25,3)}
        if name == "trials.summarize" and set(args)=={"trials"}:
            trials=args["trials"]
            if not isinstance(trials,list) or len(trials)>500:
                raise RequestError("trial limit exceeded")
            return trial_summary(trials)
        raise RequestError("unknown tool or invalid arguments")

    def dispatch(self, req):
        ident = None
        try:
            if not isinstance(req,dict) or set(req)!={"id","method","params"}:
                raise RequestError("expected id, method, params")
            ident = req["id"]
            if type(ident) not in (str,int) or (isinstance(ident,str) and len(ident)>128):
                ident = None
                raise RequestError("invalid request ID")
            method, params = req["method"],req["params"]
            if not isinstance(params,dict):
                raise RequestError("params must be an object")
            if method == "tools.list" and not params:
                result={"protocol":"mms-ide-jsonl/1","tools":TOOLS,"operations":OPS,
                        "capabilities":{"rcon_configured":bool(self.password),"read_only":True,"write":False},
                        "security":"Local operator must authorize access to workspace and evidence; raw evidence is untrusted."}
            elif method == "tools.call" and set(params)=={"name","arguments"}:
                result=self.call(params["name"],params["arguments"])
            else:
                raise RequestError("unknown method or invalid params")
            response={"id":ident,"ok":True,"result":result}
            if len(json.dumps(response,ensure_ascii=True).encode())>MAX_RESULT:
                raise RequestError("response exceeds limit; narrow the query")
            return response
        except (ValueError,TypeError,OSError,RuntimeError) as exc:
            # Never echo arbitrary exception text or credentials.
            return {"id":ident,"ok":False,"error":{"type":type(exc).__name__,
                    "message":str(exc) if isinstance(exc,RequestError) else "invalid request or unavailable evidence"}}

def serve(bridge, source, sink):
    while True:
        line=source.readline(MAX_LINE+1)
        if not line: return
        if len(line)>MAX_LINE:
            # Fail closed; do not parse the rest of an oversize request as a new one.
            response={"id":None,"ok":False,"error":{"type":"RequestError","message":"request too large; restart bridge"}}
            sink.write(json.dumps(response)+"\n");sink.flush()
            return
        try:
            req=json.loads(line)
            response=bridge.dispatch(req)
        except (ValueError,RecursionError):
            response={"id":None,"ok":False,"error":{"type":"RequestError","message":"invalid JSON"}}
        sink.write(json.dumps(response,ensure_ascii=True)+"\n")
        sink.flush()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",required=True)
    p.add_argument("--port",type=int,default=25575)
    a=p.parse_args()
    serve(Bridge(a.workspace,os.environ.get("MC_DEBUG_RCON_PASSWORD"),a.port),sys.stdin.buffer,sys.stdout)

if __name__=="__main__": main()

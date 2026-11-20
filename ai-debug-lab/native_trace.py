"""Bounded read-only native probe timeline. No causal or event-completeness claims."""
import argparse
import json
import math
import time
import uuid
from datetime import datetime
from pathlib import Path
from ide_bridge import Bridge

MAX_RECORDS = 120
MAX_POLL_SECONDS = 180

def utc_time(value):
    if not isinstance(value,str) or len(value)>64:
        raise ValueError("invalid timestamp")
    parsed=datetime.fromisoformat(value.replace("Z","+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be offset-aware")
    return parsed

def canonical_session(value):
    if not isinstance(value,str) or str(uuid.UUID(value))!=value:
        raise ValueError("invalid session UUID")
    return value

def compact(snapshot, session):
    if not isinstance(snapshot,dict) or snapshot.get("schema")!=1 or snapshot.get("session")!=session:
        raise ValueError("snapshot session or schema mismatch")
    tick=snapshot.get("tick_callbacks")
    window=snapshot.get("window_callbacks")
    elapsed=snapshot.get("window_elapsed_ms")
    if type(tick) is not int or type(window) is not int or tick<1 or not 1<=window<=tick or isinstance(elapsed,bool) or not isinstance(elapsed,(int,float)) or not math.isfinite(elapsed) or elapsed<0:
        raise ValueError("invalid tick measurement")
    stamp=snapshot.get("at")
    utc_time(stamp)
    b=snapshot.get("block")
    if not isinstance(b,dict) or b.get("status") not in ("observed","chunk_not_loaded"):
        raise ValueError("invalid block status")
    coord={k:b.get(k) for k in ("dimension","x","y","z")}
    if not isinstance(coord["dimension"],str) or len(coord["dimension"])>128 or any(type(coord[k]) is not int for k in ("x","y","z")):
        raise ValueError("invalid block coordinates")
    state={"status":b["status"],**coord}
    if b["status"]=="observed":
        for k in ("id","block_entity_type"):
            if k=="id" or k in b:
                value=b.get(k)
                if not isinstance(value,str) or not value or len(value)>256:
                    raise ValueError("invalid registry identifier")
                state[k]=value
    return {"tick":tick,"at":stamp,"window_callbacks":window,"window_elapsed_ms":elapsed,"block":state}

class Trace:
    def __init__(self,session):
        self.session=canonical_session(session)
        self.records=[]
        self.events=[]
        self.duplicates=0
        self.read_errors=0

    def append(self,snapshot):
        row=compact(snapshot,self.session)
        if self.records:
            prev=self.records[-1]
            if row["tick"]==prev["tick"]:
                if row!=prev:
                    raise ValueError("conflicting snapshot for same tick")
                self.duplicates+=1
                return False
            if row["tick"]<prev["tick"]:
                raise ValueError("out-of-order snapshot")
            if any(row["block"][k]!=prev["block"][k] for k in ("dimension","x","y","z")):
                raise ValueError("probe target changed within session")
        if len(self.records)>=MAX_RECORDS:
            raise ValueError("record limit reached")
        if self.records:
            delta=row["tick"]-prev["tick"]
            event={"from_tick":prev["tick"],"to_tick":row["tick"]}
            if delta>row["window_callbacks"]:
                self.events.append({**event,"type":"observation_gap","unobserved_callbacks":delta-row["window_callbacks"]})
            if utc_time(row["at"])<utc_time(prev["at"]):
                self.events.append({**event,"type":"wall_clock_regression"})
            before,after=prev["block"],row["block"]
            if before["status"]!=after["status"]:
                self.events.append({**event,"type":"visibility_changed","before":before,"after":after})
            elif before["status"]=="observed" and before!=after:
                self.events.append({**event,"type":"observed_block_changed","before":before,"after":after})
        self.records.append(row)
        return True

    def report(self,reason):
        return {"schema":1,"session":self.session,"stop_reason":reason,
                "records":self.records,"events":self.events,"duplicate_polls":self.duplicates,"read_errors":self.read_errors,
                "limitations":["Snapshot differences are observations, not an event log or proof of cause.",
                               "Intermediate changes may be missed even between adjacent snapshots.",
                               "Chunk not loaded is missing observation, not air or block removal.",
                               "Window elapsed time includes wall-clock scheduling; it is not MSPT.",
                               "A stopped or paused server may publish no new snapshots."]}

def capture(bridge,session,seconds=30,interval=1,limit=20,clock=time.monotonic,sleep=time.sleep):
    if isinstance(seconds,bool) or not isinstance(seconds,(int,float)) or not 0<seconds<=MAX_POLL_SECONDS:
        raise ValueError("invalid capture duration")
    if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 0.1<=interval<=10:
        raise ValueError("invalid polling interval")
    if type(limit) is not int or not 1<=limit<=MAX_RECORDS:
        raise ValueError("invalid record limit")
    trace=Trace(session)
    deadline=clock()+seconds
    while clock()<deadline:
        response=bridge.dispatch({"id":1,"method":"tools.call","params":{"name":"game.native_snapshot","arguments":{"session":session}}})
        if not response["ok"]:
            trace.read_errors+=1
        else:
            # Fail closed on corrupt or inconsistent evidence rather than fabricate a change.
            trace.append(response["result"]["data"])
            if len(trace.records)>=limit:
                return trace.report("record_limit")
        remaining=deadline-clock()
        if remaining>0:sleep(min(interval,remaining))
    return trace.report("deadline")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--workspace",required=True)
    p.add_argument("--session",required=True)
    p.add_argument("--seconds",type=float,default=30)
    p.add_argument("--interval",type=float,default=1)
    p.add_argument("--limit",type=int,default=20)
    a=p.parse_args()
    print(json.dumps(capture(Bridge(a.workspace),a.session,a.seconds,a.interval,a.limit),ensure_ascii=True,indent=2))

if __name__=="__main__": main()

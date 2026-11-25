"""Bounded tick experiments for a launcher-owned disposable server only.

No remote attach or agent-facing write tool. The trusted launcher owns the
subprocess and its console, and must terminate it on failure.
"""
import re
import time

GAME_TIME=re.compile(r"The game time is ([0-9]+) tick\(s\)")
MAX_STEP=100
MAX_TOTAL=200

def validate_steps(steps):
    if not isinstance(steps,list) or not 1<=len(steps)<=10:
        raise ValueError("expected 1-10 step counts")
    if any(type(n) is not int or not 1<=n<=MAX_STEP for n in steps) or sum(steps)>MAX_TOTAL:
        raise ValueError("step budget exceeded")
    return tuple(steps)

class ExperimentFailure(RuntimeError):
    def __init__(self,report):
        super().__init__("tick experiment failed; inspect report")
        self.report=report

def run_tick_experiment(process,read,steps,*,approved_disposable=False,clock=time.monotonic,sleep=time.sleep):
    steps=validate_steps(steps)
    if approved_disposable is not True or process.poll() is not None or process.stdin is None:
        raise ValueError("requires an approved, live launcher-owned disposable server")
    evidence={"schema":1,"scope":"launcher_owned_disposable_server","steps":list(steps),"events":[],"status":"invalid","cleanup":"not_required"}
    events=evidence["events"]
    def record(kind,**data):
        events.append({"kind":kind,"elapsed_s":round(clock()-start,3),**data})
    def check_process():
        if process.poll() is not None:
            raise RuntimeError("owned server exited")
    def send(command):
        check_process()
        process.stdin.write(command+"\n")
        process.stdin.flush()
        record("command",command=command)
    def observe(op):
        check_process()
        raw=read({"op":op})
        if not isinstance(raw,str) or len(raw)>16384:
            raise ValueError("invalid response")
        record("observation",operation=op,raw=raw)
        return raw
    def status():
        raw=observe("ticks").lower()
        if "the game is frozen" in raw:return "frozen"
        if "the game is running" in raw:return "running"
        raise RuntimeError("unrecognized tick status")
    def game_time():
        m=GAME_TIME.fullmatch(observe("gametime").strip())
        if not m:raise RuntimeError("unrecognized game time response")
        return int(m.group(1))
    def until(fn,seconds=12):
        end=clock()+seconds
        while clock()<end:
            value=fn()
            if value is not None:return value
            sleep(.1)
        raise TimeoutError("observation deadline exceeded")
    def frozen():
        return True if status()=="frozen" else None
    def stable_time():
        a=game_time()
        sleep(.35)
        b=game_time()
        if b!=a:raise RuntimeError("game time advanced during freeze control")
        return a
    start=clock()
    attempted=False
    try:
        if status()!="running":
            raise RuntimeError("experiment requires initially running server")
        a=game_time()
        until(lambda: True if game_time()>a else None)
        attempted=True
        send("tick freeze")
        until(frozen)
        before=stable_time()
        record("negative_control",before=before,after=before,passed=True)
        for n in steps:
            send("tick step "+str(n))
            target=before+n
            def reached():
                current=game_time()
                if current>target:raise RuntimeError("step overshot target")
                return current if current==target else None
            after=until(reached)
            until(frozen)
            if stable_time()!=after:raise RuntimeError("step did not stop")
            record("step_verified",requested=n,before=before,after=after,delta=after-before)
            before=after
        evidence["status"]="passed"
    except (OSError,ValueError,RuntimeError) as exc:
        evidence["failure"]={"type":type(exc).__name__,"message":str(exc)}
    finally:
        if attempted:
            try:
                send("tick unfreeze")
                until(lambda: True if status()=="running" else None)
                a=game_time()
                until(lambda: True if game_time()>a else None)
                evidence["cleanup"]="verified_running"
            except (OSError,ValueError,RuntimeError) as exc:
                evidence["cleanup"]="failed_terminate_owned_server"
                evidence["cleanup_error"]=type(exc).__name__
                evidence["status"]="invalid"
    if evidence["status"]!="passed":raise ExperimentFailure(evidence)
    return evidence

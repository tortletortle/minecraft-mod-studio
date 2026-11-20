"""Observe startup without claiming unmeasured per-download durations."""
import json
from pathlib import Path

FLAT_SETTINGS=json.dumps({"biome":"minecraft:plains","features":False,"lakes":False,"structure_overrides":[],
    "layers":[{"block":"minecraft:bedrock","height":1},{"block":"minecraft:dirt","height":2},
              {"block":"minecraft:grass_block","height":1}]},separators=(",",":"))

class StartupTracker:
    timeout=600
    def __init__(self,log,start):
        self.log=Path(log);self.start=start;self.stage="launcher_bootstrap"
        self.ready=None;self.network_warning=False;self.transitions=[]
    def update(self,state,now):
        elapsed=round(max(0,now-self.start),3)
        try:
            with self.log.open("rb") as f:
                f.seek(max(0,f.seek(0,2)-256*1024));tail=f.read(256*1024).decode("utf-8","replace")
        except OSError:tail=""
        if "Read timed out" in tail or "DIRECT failed" in tail:self.network_warning=True
        stage=self.stage
        if "Loading Minecraft " in tail and self.stage=="launcher_bootstrap":stage="fabric_loading"
        if state=="waiting_for_probe" and self.ready is None:stage="waiting_for_probe"
        if state=="ready":
            stage="ready"
            if self.ready is None:self.ready=elapsed
        if state in ("startup_timeout","stopped"):stage=state
        if stage!=self.stage:
            self.transitions.append({"observed_stage":stage,"elapsed_s":elapsed})
            self.stage=stage
        return {"stage":self.stage,"elapsed_s":elapsed,"timeout_s":self.timeout,"ready_elapsed_s":self.ready,
                "network_warning_observed":self.network_warning,"transitions":list(self.transitions),
                "measurement":"poll observations, not exact internal phase or download duration"}

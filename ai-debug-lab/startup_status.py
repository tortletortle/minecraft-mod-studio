"""Observe startup stages and classify network warnings from Fabric logs."""
import json
import re
from pathlib import Path

FLAT_SETTINGS=json.dumps({"biome":"minecraft:plains","features":False,"lakes":False,"structure_overrides":[],
    "layers":[{"block":"minecraft:bedrock","height":1},{"block":"minecraft:dirt","height":2},
              {"block":"minecraft:grass_block","height":1}]},separators=(",",":"))

# Keep patterns specific: a generic application startup timeout is not proof
# of a network failure. Fabric/Java versions emit several message variants.
NETWORK_WARNING_PATTERNS = (
    ("read_timeout", re.compile(r"\b(?:read\s+timed\s+out|timed\s+out\s+after\s+reading)\b", re.IGNORECASE)),
    ("connection_timeout", re.compile(r"\bconnect(?:ion)?\s+timed\s+out\b", re.IGNORECASE)),
    ("socket_timeout_exception", re.compile(r"\bSocketTimeoutException\b", re.IGNORECASE)),
    ("proxy_failure", re.compile(r"\bDIRECT\s+failed\b", re.IGNORECASE)),
)


class StartupTracker:
    timeout = 600

    def __init__(self, log, start):
        self.log = Path(log)
        self.start = start
        self.stage = "launcher_bootstrap"
        self.ready = None
        self.network_warning = False
        self.network_warning_reasons = []
        self.transitions = []
        self.phase_markers = {}

    def update(self, state, now):
        elapsed = round(max(0, now - self.start), 3)
        try:
            with self.log.open("rb") as stream:
                stream.seek(max(0, stream.seek(0, 2) - 256 * 1024))
                tail = stream.read(256 * 1024).decode("utf-8", "replace")
        except OSError:
            tail = ""

        for reason, pattern in NETWORK_WARNING_PATTERNS:
            if pattern.search(tail) and reason not in self.network_warning_reasons:
                self.network_warning_reasons.append(reason)
        self.network_warning = bool(self.network_warning_reasons)

        marker_patterns = (
            ("fabric_loading", "Loading Minecraft "),
            ("server_start", "Starting minecraft server version"),
            ("server_done", "Done ("),
            ("server_stopping", "Stopping server"),
        )
        for marker, phrase in marker_patterns:
            if marker not in self.phase_markers and phrase in tail:
                self.phase_markers[marker] = elapsed

        stage = self.stage
        if "Loading Minecraft " in tail and self.stage == "launcher_bootstrap":
            stage = "fabric_loading"
        if state == "waiting_for_probe" and self.ready is None:
            stage = "waiting_for_probe"
        if state == "ready":
            stage = "ready"
            if self.ready is None:
                self.ready = elapsed
        if state in ("startup_timeout", "stopped"):
            stage = state
        if stage != self.stage:
            self.transitions.append({"observed_stage": stage, "elapsed_s": elapsed})
            self.stage = stage
        return {
            "stage": self.stage,
            "elapsed_s": elapsed,
            "timeout_s": self.timeout,
            "ready_elapsed_s": self.ready,
            "network_warning_observed": self.network_warning,
            "network_warning_reasons": list(self.network_warning_reasons),
            "transitions": list(self.transitions),
            "phase_markers_elapsed_s": dict(self.phase_markers),
            "probe_ready_elapsed_s": self.ready,
            "measurement": "first poll observing each log marker; probe readiness is observed separately; timings are not exact internal phase or per-request download durations",
        }

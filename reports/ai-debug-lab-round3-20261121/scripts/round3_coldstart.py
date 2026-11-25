"""Measured real Minecraft startup runs using the unchanged AI Debug Lab."""
import argparse
import asyncio
import base64
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from mcp import Client, StdioServerParameters

MARKERS = {
    "fabric_timeout": "Read timed out",
    "fabric_direct_failed": "DIRECT failed",
    "fabric_unpack_first": "Unpacking ",
    "loading_minecraft": "Loading Minecraft ",
    "no_world": "No existing world data",
    "starting_server": "Starting Minecraft server on ",
    "done": "Done (",
}

def utc():
    return datetime.now(timezone.utc).isoformat()

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

async def run(a):
    a.out.mkdir(parents=True, exist_ok=False)
    run_started = time.monotonic()
    evidence_root = a.out.resolve()
    private_tmp = evidence_root / "private-tmp"
    private_tmp.mkdir()
    java = a.jdk.resolve() / "bin" / ("java.exe" if os.name == "nt" else "java")
    env = dict(os.environ)
    env.update({"PATH": str(java.parent) + os.pathsep + env.get("PATH", ""),
                "JAVA_HOME": str(a.jdk.resolve()),
                "JAVA_TOOL_OPTIONS": "-XX:ActiveProcessorCount=4",
                "PYTHONDONTWRITEBYTECODE": "1"})
    if not a.inherit_temp:
        env.update({"TEMP": str(private_tmp), "TMP": str(private_tmp), "TMPDIR": str(private_tmp)})
    effective_temp = Path(env.get("TEMP") or env.get("TMP") or tempfile.gettempdir())
    baseline_jna_dirs = sorted(p.name for p in effective_temp.glob("jna-*") if p.is_dir())
    wrapper = a.wrapper.resolve()
    args = [str(wrapper), "--repo", str(a.repo.resolve()), "--assets", str(a.assets.resolve()),
            "--evidence", str(evidence_root)]
    if a.preserve_root:
        args.append("--preserve-root")
    if a.seed_runtime:
        args += ["--seed-runtime", str(a.seed_runtime.resolve())]
    report = {
        "run_id": a.run_id, "condition": a.condition, "begin_utc": utc(),
        "repo": str(a.repo.resolve()), "commit": "092f5656c51ea66016ee313630ec1807c49e2255",
        "assets": str(a.assets.resolve()),
        "asset_hashes": json.loads((a.assets / "hashes.json").read_text(encoding="utf-8")),
        "environment": {"os": platform.platform(), "python": sys.version,
            "mcp": importlib.metadata.version("mcp"), "jdk": str(a.jdk.resolve()),
            "jvm_options": env["JAVA_TOOL_OPTIONS"], "temp_policy": "inherited" if a.inherit_temp else "isolated",
            "effective_temp": str(effective_temp), "jna_dirs_before": baseline_jna_dirs},
        "command": [sys.executable, *args], "events": [], "markers": {},
        "status_polls": [], "network_connections": [],
    }
    write(a.out / "run.json", report)

    def mark(event, **data):
        item = {"event": event, "utc": utc(), "elapsed_s": round(time.monotonic() - run_started, 3), **data}
        report["events"].append(item)
        write(a.out / "run.json", report)

    def network_sample(pid):
        try:
            import psutil
            p = psutil.Process(pid)
            rows = []
            for c in p.net_connections(kind="tcp"):
                rows.append({"status": c.status, "local": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else None,
                             "remote": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else None})
            return rows
        except Exception as exc:
            return [{"error": type(exc).__name__}]

    async def monitor():
        seen = {}
        last_size = -1
        while True:
            instance_path = a.out / "instance.json"
            if instance_path.exists():
                instance = json.loads(instance_path.read_text(encoding="utf-8"))
                report["instance"] = instance
            process_path = a.out / "process.json"
            if process_path.exists():
                process = json.loads(process_path.read_text(encoding="utf-8"))
                report["process"] = process
            inner = None
            if instance_path.exists():
                obj = json.loads(instance_path.read_text(encoding="utf-8"))
                if obj.get("inner_evidence"):
                    inner = Path(obj["inner_evidence"])
            log = inner / "server.log" if inner else None
            if log and log.exists():
                try:
                    raw = log.read_bytes()
                    if len(raw) != last_size:
                        previous_size = last_size
                        last_size = len(raw)
                        text = raw.decode("utf-8", "replace")
                        chunk = raw[max(previous_size, 0):]
                        observation = {
                            "observed_utc": utc(),
                            "observed_monotonic_ns": time.monotonic_ns(),
                            "elapsed_s": round(time.monotonic() - run_started, 6),
                            "offset_start": max(previous_size, 0),
                            "offset_end": len(raw),
                            "appended_bytes_base64": base64.b64encode(chunk).decode("ascii"),
                            "snapshot_sha256": sha(log),
                        }
                        with (a.out / "log_observations.jsonl").open("a", encoding="utf-8") as observations:
                            observations.write(json.dumps(observation) + "\n")
                        for name, needle in MARKERS.items():
                            if name not in seen and needle in text:
                                seen[name] = {"elapsed_s": round(time.monotonic() - run_started, 3),
                                              "observed_utc": utc(), "log_bytes": len(raw)}
                                report["markers"] = dict(seen)
                                mark(name, log_bytes=len(raw))
                        (a.out / "server.log.raw").write_bytes(raw)
                except OSError:
                    pass
            process = report.get("process")
            if process and process.get("pid"):
                sample = {"elapsed_s": round(time.monotonic() - run_started, 3),
                          "utc": utc(), "pid": process["pid"],
                          "connections": network_sample(process["pid"])}
                report["network_connections"].append(sample)
            write(a.out / "run.json", report)
            if (a.out / "monitor.stop").exists():
                return
            await asyncio.sleep(0.25)

    async def poll(client, index):
        started = utc()
        t0 = time.monotonic()
        answer = await client.call_tool("playtest_status", {})
        data = answer.model_dump(mode="json", by_alias=True)
        item = {"index": index, "started_utc": started, "elapsed_s": round(time.monotonic() - t0, 3),
                "response": data}
        report["status_polls"].append(item)
        write(a.out / "run.json", report)
        (a.out / "status.jsonl").open("a", encoding="utf-8").write(json.dumps(item, ensure_ascii=False) + "\n")
        return data.get("structuredContent", {}).get("evidence", {})

    monitor_task = asyncio.create_task(monitor())
    server = StdioServerParameters(command=sys.executable, args=args, env=env, cwd=str(a.repo.resolve()))
    try:
        async with Client(server, read_timeout_seconds=25) as client:
            tools = await client.list_tools()
            write(a.out / "tools.json", tools.model_dump(mode="json", by_alias=True))
            mark("mcp_ready", tool_count=len(tools.tools))
            deadline = time.monotonic() + 900
            ready = None
            index = 0
            while time.monotonic() < deadline:
                index += 1
                ready = await poll(client, index)
                status = ready.get("status")
                if status == "ready":
                    mark("ready", session=ready.get("session"), startup=ready.get("startup"))
                    break
                if status == "stopped":
                    raise RuntimeError("server stopped before ready")
                await asyncio.sleep(1)
            else:
                raise TimeoutError("startup exceeded 900 seconds")
            if a.do_actions:
                for name, arguments in [
                    ("playtest_set_block", {"block": "minecraft:chest"}),
                    ("playtest_set_block", {"block": "minecraft:air"}),
                    ("playtest_tick_steps", {"steps": [3, 9]}),
                ]:
                    answer = await client.call_tool(name, arguments)
                    (a.out / "actions.jsonl").open("a", encoding="utf-8").write(json.dumps({"tool": name, "arguments": arguments, "response": answer.model_dump(mode="json", by_alias=True)}, ensure_ascii=False) + "\n")
            if a.budget_exhaust:
                with (a.out / "budget-actions.jsonl").open("w", encoding="utf-8") as actions:
                    for index in range(25):
                        arguments = {"block": "minecraft:chest" if index % 2 == 0 else "minecraft:air"}
                        answer = await client.call_tool("playtest_set_block", arguments)
                        item = {"sequence": index + 1, "arguments": arguments,"response": answer.model_dump(mode="json", by_alias=True)}
                        actions.write(json.dumps(item, ensure_ascii=False) + "\n"); actions.flush()
                status_after = await poll(client, len(report["status_polls"]) + 1)
                mark("budget_exhaustion_checked", is_error=answer.isError, status_after=status_after.get("status"))
            (a.out / "shutdown.request").write_text(utc(), encoding="utf-8")
            mark("shutdown_requested")
            for _ in range(120):
                if (a.out / "wrapper-exit.json").exists():
                    break
                await asyncio.sleep(0.25)
    finally:
        (a.out / "monitor.stop").write_text(utc(), encoding="utf-8")
        await asyncio.wait_for(monitor_task, timeout=10)
        report["end_utc"] = utc()
        final_jna_dirs = sorted(p.name for p in effective_temp.glob("jna-*") if p.is_dir())
        report["temp_artifacts"] = {"jna_dirs_before": baseline_jna_dirs,
            "jna_dirs_after": final_jna_dirs,
            "jna_dirs_added": sorted(set(final_jna_dirs) - set(baseline_jna_dirs))}
        report["duration_s"] = round(time.monotonic() - run_started, 3)
        write(a.out / "run.json", report)

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--wrapper", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--jdk", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--condition", choices=["clean", "cache_seeded"], required=True)
    p.add_argument("--seed-runtime", type=Path)
    p.add_argument("--preserve-root", action="store_true")
    p.add_argument("--do-actions", action="store_true")
    p.add_argument("--budget-exhaust", action="store_true")
    p.add_argument("--inherit-temp", action="store_true")
    a = p.parse_args()
    a.out = a.out.resolve(); a.repo = a.repo.resolve(); a.wrapper = a.wrapper.resolve(); a.assets = a.assets.resolve(); a.jdk = a.jdk.resolve()
    asyncio.run(run(a))

if __name__ == "__main__":
    main()

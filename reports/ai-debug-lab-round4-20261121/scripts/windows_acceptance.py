"""Windows acceptance driver for V0.12.2. Uses the official MCP stdio client and unmodified playtest.py."""
import argparse
import asyncio
from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shutil
import statistics
import subprocess
import sys
import time
import traceback

from mcp import StdioServerParameters
from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client
import psutil

EXPECTED_HEAD = "3d265d533a412b453cc0b835b66a05c6f10126ad"
RUNTIME = {".fabric", "libraries", "versions"}
BASELINE = {"cold": 115.375, "hot": 25.672}
COMPARISON_ASSETS = {
    "fabric-server.jar": "4dbe153d1e672beaf14fd8f78f6df6a47060dfbe698b772ca7b6dd476457de6c",
    "server.jar": "cdacdfb25898de5e4b4b0e5ddcc2722f77067e46605709c2d886c000ebb63ec5",
    "fabric-api.jar": "e5b858ceb13290c274e31cb888ff5a1a40cb91067e7ffab0b5b775aec51e216a",
    "probe.jar": "f64b35f34739a65737d107989489b0beefcc69c19d2a3e2da1206f091c57298c",
}


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def file_sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_json(path, data):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False) + "\n")


def links(path):
    return path.is_symlink() or path.is_junction()


def audit(cache, out):
    """Validate the published files without importing the product cache code."""
    root_names = sorted(path.name for path in cache.iterdir())
    entries = [path for path in cache.iterdir() if re.fullmatch(r"[0-9a-f]{64}", path.name)]
    data = {"cache_root_entries": root_names, "entry_count": len(entries), "passed": False}
    if len(entries) == 1 and not links(entries[0]) and entries[0].is_dir():
        entry = entries[0]
        manifest_file = entry / "cache-manifest.json"
        manifest = read_json(manifest_file)
        write_json(out.with_name(out.stem + "-manifest.json"), manifest)
        observed = {}
        forbidden = []
        forbidden_names = {"mods", "world", "world_nether", "world_the_end", "saves", "server.properties",
                           "eula", "eula.txt", "rcon.password", "usercache.json", "ops.json", "logs", "mms-debug"}
        for current, directories, files in os.walk(entry, followlinks=False):
            for name in directories + files:
                path = Path(current) / name
                relative = path.relative_to(entry).as_posix()
                if name.lower() in forbidden_names or links(path):
                    forbidden.append(relative)
                    if name in directories:
                        directories.remove(name)
                elif name in files and relative != "cache-manifest.json" and path.is_file():
                    observed[relative] = {"size": path.stat().st_size, "sha256": file_sha(path)}
        expected = manifest["files"]
        mismatch = sorted(name for name in (expected.keys() | observed.keys()) if expected.get(name) != observed.get(name))
        top = sorted(path.name for path in entry.iterdir())
        root_ok = root_names == sorted([entry.name, entry.name + ".lock"]) and not links(cache / (entry.name + ".lock"))
        data.update(entry=entry.name, entry_top=top, manifest_sha256=file_sha(manifest_file),
                    manifest_file_count=len(expected), file_count=len(observed), mismatch=mismatch,
                    forbidden=forbidden, staging_or_extra=not root_ok,
                    passed=root_ok and set(top) == RUNTIME | {"cache-manifest.json"}
                    and all((entry / name).is_dir() for name in RUNTIME)
                    and manifest["cache_key"] == entry.name and manifest["asset_hashes"] == COMPARISON_ASSETS
                    and bool(observed) and not mismatch and not forbidden)
    write_json(out, data)
    return data


def owned_process(run_output):
    for child in psutil.Process().children():
        try:
            if str(run_output) in child.cmdline():
                return child
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def endpoint_sample(java):
    ports = []
    for conn in java.net_connections(kind="tcp"):
        if conn.raddr and ipaddress.ip_address(conn.raddr.ip.split("%")[0]).is_global:
            ports.append({"remote_port": conn.raddr.port, "status": conn.status})
    return ports


async def observe(result, output, tmp, cache, start, stop):
    last_state = None
    next_network = 0.0
    java = None
    while not stop.is_set():
        try:
            launcher = owned_process(output)
            if launcher:
                result["launcher_pid"] = launcher.pid
                result["launcher_created_epoch_s"] = launcher.create_time()
                if java is None:
                    java = next((p for p in launcher.children() if p.name().lower() == "java.exe"), None)
                    if java:
                        result["java_pid"] = java.pid
                        result["java_created_epoch_s"] = java.create_time()
                        result["java_executable"] = java.exe()
            cache_entries = []
            for path in sorted(cache.iterdir()):
                if path.is_dir():
                    cache_entries.append({"name": path.name, "has_manifest": (path / "cache-manifest.json").is_file()})
                else:
                    cache_entries.append({"name": path.name})
            if cache_entries != last_state:
                append_json(output / "cache-observations.jsonl", {"utc": utc(), "elapsed_s": round(time.monotonic()-start, 3), "entries": cache_entries})
                last_state = cache_entries
            now = time.monotonic()
            if java and now >= next_network:
                next_network = now + 2
                # psutil only observes sockets owned by this test JVM. Do not record IP addresses.
                ports = await asyncio.to_thread(endpoint_sample, java)
                append_json(output / "network.jsonl", {"utc": utc(), "elapsed_s": round(now-start, 3), "java_pid": java.pid, "public_addresses": ports})
        except (psutil.Error, OSError, ValueError) as exc:
            result.setdefault("observer_error_types", [])
            if type(exc).__name__ not in result["observer_error_types"]:
                result["observer_error_types"].append(type(exc).__name__)
        await asyncio.sleep(0.20)


def inspect_world(tmp, session):
    roots = list(tmp.glob("mms-ai-world-*"))
    if len(roots) != 1:
        raise RuntimeError("Expected exactly one world root in private TEMP")
    root = roots[0]
    config = root / "server.properties"
    props = dict(line.split("=", 1) for line in config.read_text(encoding="utf-8").splitlines()
                 if "=" in line and not line.startswith("#"))
    password = props.get("rcon.password", "")
    level = root / props.get("level-name", "world")
    return {"world_root": str(root), "world_level_dat_present": (level / "level.dat").is_file(),
            "config_path": str(config), "bind_loopback": props.get("server-ip") == "127.0.0.1",
            "game_port": int(props["server-port"]), "rcon_port": int(props["rcon.port"]),
            "probe_snapshot_present": (root / "mms-debug" / session / "snapshot.json").is_file(),
            "has_generated_password": bool(re.fullmatch(r"[0-9a-f]{48}", password))}, password


async def run(a, name, cache, credentials, barrier=None):
    evidence = a.out / "evidence" / name
    evidence.mkdir()
    tmp = a.out / "tmp" / name
    tmp.mkdir(parents=True)
    env = dict(os.environ, JAVA_HOME=str(a.jdk), PATH=str(a.jdk / "bin") + os.pathsep + os.environ["PATH"],
               JAVA_TOOL_OPTIONS="-XX:ActiveProcessorCount=4", TEMP=str(tmp), TMP=str(tmp), TMPDIR=str(tmp),
               PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
    for name_to_clear in ("JDK_JAVA_OPTIONS", "_JAVA_OPTIONS", "MMS_AI_RUNTIME_CACHE_DIR"):
        env.pop(name_to_clear, None)
    args = [str(a.repo / "ai-debug-lab" / "playtest.py"), "serve", "--assets", str(a.assets),
            "--evidence", str(evidence), "--runtime-cache-dir", str(cache), "--accept-eula"]
    parameters = StdioServerParameters(command=sys.executable, args=args, env=env, cwd=str(a.repo))
    if barrier:
        await barrier.wait()
    print(f"{utc()} START {name}", flush=True)
    start = time.monotonic()
    result = {"name": name, "request_utc": utc(), "cache_dir": str(cache), "outcome": "failed"}
    stop = asyncio.Event()
    watcher = asyncio.create_task(observe(result, evidence, tmp, cache, start, stop))
    try:
        with (evidence / "stderr.log").open("w", encoding="utf-8") as errlog:
            async with stdio_client(parameters, errlog=errlog) as (read, write):
                async with ClientSession(read, write, read_timeout_seconds=75) as client:
                    initialized = await client.initialize()
                    tools = sorted(tool.name for tool in (await client.list_tools()).tools)
                    append_json(evidence / "client.jsonl", {"kind": "initialize", "utc": utc(), "tools": tools,
                                "response": initialized.model_dump(mode="json", by_alias=True, exclude_none=True)})

                    async def call(tool, arguments):
                        begin = time.monotonic() - start
                        answer = await client.call_tool(tool, arguments=arguments)
                        returned = time.monotonic() - start
                        append_json(evidence / "client.jsonl", {"kind": "call", "tool": tool, "arguments": arguments,
                            "begin_s": round(begin, 3), "return_s": round(returned, 3), "utc": utc(),
                            "response": answer.model_dump(mode="json", by_alias=True, exclude_none=True)})
                        if answer.is_error:
                            raise RuntimeError("MCP tool returned an error, see client.jsonl")
                        return answer.structured_content["evidence"], returned, begin

                    deadline = start + 660
                    while True:
                        status, returned, _ = await call("playtest_status", {})
                        if status["status"] == "ready":
                            result.update(outcome="ready", request_to_ready_s=round(returned, 3), ready_utc=utc(),
                                          session=status["session"], startup=status["startup"])
                            break
                        if status["status"] not in {"starting", "waiting_for_probe"} or time.monotonic() >= deadline:
                            raise RuntimeError("Startup ended before ready: " + status["status"])
                        await asyncio.sleep(1)

                    result["instance"], credentials[name] = inspect_world(tmp, result["session"])
                    recipe, _, _ = await call("game_recipe_status", {"session": result["session"]})
                    result["recipe_output"] = recipe["data"]["recipe"]["experiment"]["output"]
                    if result["recipe_output"] != "minecraft:emerald":
                        raise RuntimeError("Unexpected native probe recipe output")
                    if barrier:
                        await asyncio.wait_for(barrier.wait(), timeout=660)
                    result["outcome"] = "passed"
    except Exception:
        result["outcome"] = "failed"
        (evidence / "failure.log").write_text(traceback.format_exc(), encoding="utf-8")
        if barrier:
            await barrier.abort()
    finally:
        stop.set()
        await watcher
        result["end_utc"] = utc()
        result["world_roots_after_disconnect"] = [path.name for path in tmp.glob("mms-ai-world-*")]
        for role in ("launcher", "java"):
            pid = result.get(role + "_pid")
            if pid is not None:
                try:
                    remains = psutil.Process(pid).create_time() == result[role + "_created_epoch_s"]
                except psutil.NoSuchProcess:
                    remains = False
                result[role + "_alive_after_disconnect"] = remains
        game_logs = list(evidence.glob("playtest-*/server.log"))
        if len(game_logs) == 1:
            log = game_logs[0]
            for key in ("cache", "startup"):
                path = log.with_name(key + ".json")
                if path.is_file():
                    result[key] = read_json(path)
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            marks = {"loading": "Loading Minecraft ", "world_creation": "No existing world data", "server_start": "Starting minecraft server version", "done": "Done (", "stopping": "Stopping server"}
            result["log_markers"] = {key: [line for line in lines if needle in line] for key, needle in marks.items()}
            result["network_log"] = [line for line in lines if re.search(r"(?i)download|https?://|timed out|DIRECT failed", line)]
            result["runtime_unpack_log_count"] = sum("Unpacking " in line for line in lines)
            result["flat_generator_error"] = any("No key layers in MapLike" in line for line in lines)
        created = result.get("java_created_epoch_s")
        ready = result.get("ready_utc")
        if created and ready:
            result["java_create_to_mcp_ready_s"] = round(datetime.fromisoformat(ready).timestamp() - created, 3)
            startup_file = game_logs[0].with_name("startup.json")
            # The last poll's product file is written before synchronous cache publication.
            result["java_create_to_startup_ready_file_s"] = round(startup_file.stat().st_mtime - created, 3)
        write_json(evidence / "result.json", result)
        print(f"{utc()} END {result['name']} {result['outcome']} {result.get('request_to_ready_s')} {result.get('cache')}", flush=True)
    return result


def corrupt(source, target, evidence):
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("*.lock"))
    entry = next(path for path in target.iterdir() if path.is_dir())
    manifest = read_json(entry / "cache-manifest.json")
    relative = min((name for name in manifest["files"] if name.endswith(".jar")), key=lambda name: manifest["files"][name]["size"])
    jar = entry / relative
    if not jar.resolve().is_relative_to(target.resolve()) or links(jar):
        raise RuntimeError("Corruption target outside private test cache")
    before = file_sha(jar)
    size = jar.stat().st_size
    if before != manifest["files"][relative]["sha256"]:
        raise RuntimeError("File already invalid before injection")
    with jar.open("r+b") as stream:
        offset = size // 2
        stream.seek(offset)
        original = stream.read(1)[0]
        stream.seek(offset)
        stream.write(bytes([original ^ 1]))
    data = {"relative_file": relative, "same_length": jar.stat().st_size == size, "offset": offset,
            "size": size, "before_sha256": before, "after_sha256": file_sha(jar), "edited_utc": utc()}
    write_json(evidence / "corrupt-edit.json", data)
    return entry, relative, data


def pair_state(result):
    cache = result.get("cache", {})
    return ((cache.get("restore") or {}).get("status"), (cache.get("publish") or {}).get("status"))


async def execute(a):
    a.out.mkdir(parents=True, exist_ok=False)
    evidence = a.out / "evidence"
    evidence.mkdir()
    env_assets = {name: file_sha(a.assets / name) for name in COMPARISON_ASSETS}
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=a.repo, text=True).strip()
    java = subprocess.run([str(a.jdk / "bin/java.exe"), "-version"], capture_output=True, text=True, check=True)
    write_json(evidence / "environment.json", {"source_commit": head, "os": platform.platform(), "machine": platform.machine(),
        "python": sys.version, "java_version": java.stderr.strip(), "java_sha256": file_sha(a.jdk / "bin/java.exe"),
        "mcp": version("mcp"), "psutil": version("psutil"), "assets": env_assets,
        "minecraft": "26.2", "fabric_loader": "0.20.1", "fabric_installer": "1.1.2", "jvm_options": "-XX:ActiveProcessorCount=4",
        "temp_policy": "isolated per run", "status_poll_interval_s": 1})
    if os.name != "nt" or sys.version_info[:2] != (3, 12) or version("mcp") != "2.3.0" or "25.0.5" not in java.stderr:
        raise RuntimeError("Windows/Python/Java/MCP environment mismatch")
    if head != EXPECTED_HEAD or env_assets != COMPARISON_ASSETS or read_json(a.assets / "hashes.json") != COMPARISON_ASSETS:
        raise RuntimeError("Target commit or test asset mismatch")
    write_json(evidence / "experiment-plan.json", {"reference_r3_s": BASELINE,
        "pairs": 3, "pair_cache": "fresh cache root per group, reused only by the two runs", "cache_option": "--runtime-cache-dir",
        "corruption": "clone the first valid isolated cache, flip one bit without changing size, retry and check subsequent hit",
        "concurrency": "two independent MCP processes, same fresh cache, hold both servers until both probes answer",
        "start_time": "driver enters MCP stdio connection before process spawn", "ready_time": "first ready MCP response received",
        "native_startup_time": "product starts timer before cache restore and stops it before publish",
        "network_samples": "public TCP sockets by owned java PID, ports/state only, approximately 2 seconds"})
    results, audits, credentials = {}, {}, {}
    seed = None
    for group in range(1, 4):
        cache = a.out / "cache" / f"pair-{group}"
        cache.mkdir(parents=True)
        for state in ("cold", "hot"):
            run_name = f"pair-{group}-{state}"
            results[run_name] = await run(a, run_name, cache, credentials)
            audits[run_name] = audit(cache, evidence / (run_name + "-cache-audit.json"))
        if seed is None and audits[f"pair-{group}-hot"]["passed"]:
            seed = cache
    if seed:
        cache = a.out / "cache" / "corrupt"
        entry, relative, edit = corrupt(seed, cache, evidence)
        results["corrupt-recovery"] = await run(a, "corrupt-recovery", cache, credentials)
        audits["corrupt-recovery"] = audit(cache, evidence / "corrupt-recovery-cache-audit.json")
        edit["rebuilt_sha256"] = file_sha(entry / relative) if (entry / relative).is_file() else None
        write_json(evidence / "corrupt-edit.json", edit)
        results["corrupt-verified-hit"] = await run(a, "corrupt-verified-hit", cache, credentials)
    cache = a.out / "cache" / "concurrent"
    cache.mkdir(parents=True)
    barrier = asyncio.Barrier(2)
    shared = await asyncio.gather(*(run(a, f"concurrent-{side}", cache, credentials, barrier) for side in ("a", "b")))
    results.update((item["name"], item) for item in shared)
    audits["concurrent"] = audit(cache, evidence / "concurrent-cache-audit.json")
    instances = [run["instance"] for run in results.values() if "instance" in run]
    simultaneous_ports = [value for item in shared if "instance" in item for value in (item["instance"]["game_port"], item["instance"]["rcon_port"])]
    isolation = {"instances": len(instances), "world_roots_distinct": len({item["world_root"] for item in instances}) == len(results),
        "config_paths_distinct": len({item["config_path"] for item in instances}) == len(results),
        "sessions_distinct": len({item.get("session") for item in results.values() if "session" in item}) == len(results),
        "all_worlds_and_probes_observed": len(instances) == len(results) and all(item["world_level_dat_present"] and item["probe_snapshot_present"] for item in instances),
        "configs_bound_to_loopback": bool(instances) and all(item["bind_loopback"] for item in instances),
        "rcon_passwords_unique": len(set(credentials.values()) - {""}) == len(results),
        "concurrent_ports_distinct": len(set(simultaneous_ports)) == 4,
        "concurrent_jvm_lifetimes_overlap": all("java_created_epoch_s" in item for item in shared) and
           max(item["java_created_epoch_s"] for item in shared) < min(datetime.fromisoformat(item["end_utc"]).timestamp() for item in shared),
        "all_worlds_deleted": all(not item["world_roots_after_disconnect"] for item in results.values()),
        "all_owned_processes_exited": all(item.get("java_alive_after_disconnect") is False and item.get("launcher_alive_after_disconnect") is False for item in results.values())}
    write_json(evidence / "isolation.json", isolation)
    medians = {}
    for state in ("cold", "hot"):
        runs = [results[f"pair-{i}-{state}"] for i in range(1, 4)]
        medians[state] = {key: statistics.median(item[key] for item in runs) for key in
            ("request_to_ready_s", "java_create_to_mcp_ready_s", "java_create_to_startup_ready_file_s") if all(key in item for item in runs)}
        if all((item.get("startup") or {}).get("ready_elapsed_s") is not None for item in runs):
            medians[state]["native_ready_s"] = statistics.median(item["startup"]["ready_elapsed_s"] for item in runs)
    acceptance = {"cache_pairs": all(pair_state(results[f"pair-{i}-{state}"]) == expected for i in range(1, 4)
                        for state, expected in (("cold", ("miss", "stored")), ("hot", ("hit", "not_needed")))),
        "minecraft_runs": len(results) == 10 and all(run["outcome"] == "passed" and bool(run.get("log_markers", {}).get("done")) and not run.get("flat_generator_error") for run in results.values()),
        "cache_audits": len(audits) == 8 and all(item["passed"] for item in audits.values()),
        "concurrent": sorted(pair_state(item) for item in shared if None not in pair_state(item)) == [("miss", "already_valid"), ("miss", "stored")] and isolation["concurrent_jvm_lifetimes_overlap"],
        "isolation": all(value is True for key, value in isolation.items() if key != "instances")}
    if seed:
        recovery = results["corrupt-recovery"]
        restore = recovery.get("cache", {}).get("restore") or {}
        acceptance["corrupt_recovery"] = (pair_state(recovery) == ("miss", "stored") and restore.get("reason") == "invalid_cache_removed"
            and restore.get("detail") == "file_inventory_or_hash_mismatch" and edit["before_sha256"] == edit["rebuilt_sha256"]
            and edit["before_sha256"] != edit["after_sha256"] and edit["same_length"]
            and pair_state(results["corrupt-verified-hit"]) == ("hit", "not_needed"))
    else:
        acceptance["corrupt_recovery"] = False
    write_json(evidence / "summary.json", {"runs": list(results), "medians": medians, "round3_reference_s": BASELINE,
        "acceptance": acceptance, "all_checks_passed": all(acceptance.values())})
    return all(acceptance.values())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "assets", "jdk", "out"):
        parser.add_argument("--" + name, type=lambda value: Path(value).resolve(), required=True)
    raise SystemExit(0 if asyncio.run(execute(parser.parse_args())) else 1)

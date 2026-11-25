"""Validate a Studio-exported production JAR against Fabric and the Studio MCP adapter."""

import argparse
import asyncio
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


WORKSPACE = Path(__file__).resolve().parents[2]
REPO = Path.home() / ".codex/worktrees/mms-v0122-acceptance/minecraft-mod-studio"
ASSETS = WORKSPACE / "outputs/ai-playtest-20261120/assets-run1"
CACHE = WORKSPACE / "work/round4-v0122-20261121/cache/pair-1"
JAVA = WORKSPACE / "work/jdk25-round3/jdk-25.0.5+8/bin/java.exe"
OUT = WORKSPACE / "outputs/crystal-lab-full-pipeline/runtime"
RESOURCE_ID = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")


def resource_id(value):
    if not RESOURCE_ID.fullmatch(value) or ".." in value.partition(":")[2].split("/"):
        raise argparse.ArgumentTypeError("Expected a canonical Minecraft resource ID")
    return value


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def generated_declarations(args):
    namespace, _, recipe_path = args.recipe.partition(":")
    with zipfile.ZipFile(args.jar) as jar:
        require(jar.testzip() is None, "Generated JAR failed CRC check")
        manifest = json.loads(jar.read("fabric.mod.json"))
        require(manifest["id"] == namespace != "mms_playtest", "Unexpected generated mod ID")
        require(manifest["depends"]["minecraft"] == "26.2", "Expected a Minecraft 26.2 export")
        recipe = json.loads(jar.read(f"data/{namespace}/recipe/{recipe_path}.json"))
    require(recipe["result"]["id"] == args.item, "JAR recipe output differs from test input")
    require(recipe["result"].get("count", 1) == args.count, "JAR recipe count differs from test input")
    require(args.item.startswith(namespace + ":"), "Expected the recipe to output a custom item")
    for label, value in (("block", args.block), ("entity", args.entity)):
        if value:
            require(value.startswith(namespace + ":"), f"Expected a generated {label}")
    return manifest, recipe


def send_console(proc, command):
    require(proc.poll() is None, "Minecraft stopped before console command")
    proc.stdin.write(command + "\n")
    proc.stdin.flush()


def stop_server(proc):
    try:
        if proc.poll() is None:
            try:
                send_console(proc, "stop")
                return {"method": "console_stop", "exit_code": proc.wait(timeout=35)}
            except (OSError, subprocess.TimeoutExpired):
                proc.kill()
                return {"method": "owned_process_kill", "exit_code": proc.wait(timeout=10)}
        return {"method": "already_exited", "exit_code": proc.returncode}
    finally:
        proc.stdin.close()


async def until_snapshot(root, proc, deadline):
    while time.monotonic() < deadline:
        require(proc.poll() is None, "Minecraft exited before the native probe answered")
        snapshots = list((root / "mms-debug").glob("*/snapshot.json"))
        require(len(snapshots) <= 1, "Unexpected multiple probe sessions in the private world")
        if snapshots:
            return snapshots[0].parent.name
        await asyncio.sleep(0.75)
    raise TimeoutError("Native probe did not produce a session before the startup deadline")


async def inspect_with_mcp(args, root, proc, password, rcon_port, result, manifest):
    session_id = await until_snapshot(root, proc, time.monotonic() + args.timeout)
    result["probe_ready_s"] = round(time.monotonic() - result["server_started_monotonic"], 3)
    result["session"] = session_id
    params = StdioServerParameters(
        command=sys.executable,
        args=["-B", str(args.repo / "ai-debug-lab/mcp_adapter.py"), "--workspace", str(root),
              "--port", str(rcon_port), "--allow-rcon"],
        env={"MC_DEBUG_RCON_PASSWORD": password},
    )
    with (args.out / "mcp.stderr.log").open("w", encoding="utf-8") as stderr, \
            (args.out / "mcp-transcript.jsonl").open("w", encoding="utf-8") as transcript:
        def record(value):
            transcript.write(json.dumps(value, ensure_ascii=False) + "\n")
            transcript.flush()

        async with stdio_client(params, errlog=stderr) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                init = await asyncio.wait_for(client.initialize(), 30)
                tools = await asyncio.wait_for(client.list_tools(), 30)
                names = {tool.name for tool in tools.tools}
                require({"mods_inventory", "game_native_snapshot", "game_recipe_status",
                         "mods_diagnose_recipe", "game_tick_observe"} <= names, "Required Studio MCP tools missing")
                result["mcp_tools"] = sorted(names)
                record({"initialize": init.model_dump(mode="json", by_alias=True), "tools": sorted(names)})

                async def call(tool, arguments):
                    response = await asyncio.wait_for(client.call_tool(tool, arguments), 20)
                    record({"tool": tool, "arguments": arguments,
                            "response": response.model_dump(mode="json", by_alias=True, exclude_none=True)})
                    require(not response.is_error and response.structured_content, f"MCP tool failed: {tool}")
                    return response.structured_content["evidence"]["data"]

                context = {"session": session_id}
                inventory = await call("mods_inventory", {})
                recorded_jars = [row for row in inventory["jars"] if row.get("id") == manifest["id"]]
                require(len(recorded_jars) == 1, "Expected one generated JAR in MCP inventory")
                installed = recorded_jars[0]
                require(installed["sha256"] == result["jar_sha256"], "Installed JAR differs from export")
                require(installed["version"] == manifest["version"], "Installed JAR version differs from export")
                require(not inventory["duplicate_declared_ids"], "Unexpected duplicate active JAR declarations")
                result["mcp_inventory"] = installed

                snapshot = await call("game_native_snapshot", context)
                require(snapshot["session"] == session_id and snapshot["dedicated"], "Unexpected probe session")
                registrations = snapshot["registrations"]
                require({"id": manifest["id"], "version": manifest["version"]} in registrations["mods"],
                        "Runtime Fabric list does not contain generated mod and version")
                require("mms_playtest" not in {row["id"] for row in registrations["mods"]},
                        "Unexpected fixed playtest fixture loaded")
                for category, resource in (("items", args.item), ("blocks", args.block), ("entity_types", args.entity)):
                    if resource:
                        require(resource in registrations[category], f"Missing real Minecraft registration: {resource}")
                result["generated_registrations"] = {category: [item for item in registrations[category]
                    if item.startswith(manifest["id"] + ":")] for category in ("items", "blocks", "entity_types")}
                dump(args.out / "native-before.json", snapshot)

                active = await call("game_recipe_status", context)
                recipe = active["recipe"]
                require(recipe["id"] == args.recipe and recipe["status"] == "present", "Generated recipe not loaded")
                experiment = recipe["experiment"]
                require(experiment["inputs"] == args.inputs and experiment["status"] == "matched"
                        and experiment["output"] == args.item and experiment["count"] == args.count,
                        "Generated recipe did not assemble the expected output in Minecraft")
                result["recipe"] = recipe

                diagnosed = await call("mods_diagnose_recipe", {**context, "recipe": args.recipe})
                sources = [row["source"] for row in diagnosed["declarations"]]
                require(len(sources) == 1 and sources[0]["sha256"] == result["jar_sha256"]
                        and sources[0]["runtime_alignment"] == "id_version_match", "Recipe declaration could not be tied to the generated JAR")
                result["recipe_source"] = sources[0]

                tick = await call("game_tick_observe", {"operations": ["ticks", "gametime"], "repeat": 1})
                require(len(tick["measurements"]) == 2 and all(m["transport"] == "received" for m in tick["measurements"]),
                        "MCP could not read the dedicated server tick and time")
                result["tick_rcon_observed"] = True

                if args.block:
                    require(snapshot["block"].get("id") != args.block, "Generated fixture block present before placement")
                    send_console(proc, "execute in minecraft:overworld run forceload add 0 0")
                    send_console(proc, "execute in minecraft:overworld run setblock 0 80 0 " + args.block)
                    deadline = time.monotonic() + 45
                    while time.monotonic() < deadline:
                        require(proc.poll() is None, "Minecraft exited during block observation")
                        after = await call("game_native_snapshot", context)
                        if (after["tick_callbacks"] > snapshot["tick_callbacks"]
                                and after["block"].get("status") == "observed" and after["block"].get("id") == args.block):
                            dump(args.out / "native-after.json", after)
                            result["observed_block"] = {"before": snapshot["block"], "after": after["block"],
                                "before_ticks": snapshot["tick_callbacks"], "after_ticks": after["tick_callbacks"]}
                            break
                        await asyncio.sleep(2)
                    else:
                        raise TimeoutError("Native probe did not observe the test placement")


def run(args, result):
    sys.path.insert(0, str(args.repo / "ai-debug-lab"))
    from live_smoke import free_port
    from runtime_cache import ASSET_NAMES, RuntimeCache
    from startup_status import FLAT_SETTINGS

    manifest, recipe = generated_declarations(args)
    result.update(mod_id=manifest["id"], version=manifest["version"], jar_sha256=sha256(args.jar),
                  expected_recipe=args.recipe, recipe_declaration=recipe,
                  source_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip())
    result["java_version"] = subprocess.check_output([str(args.java), "-version"], stderr=subprocess.STDOUT, text=True).strip()
    require('version "25.' in result["java_version"], "Expected Java 25")
    asset_hashes = json.loads((args.assets / "hashes.json").read_text(encoding="utf-8"))
    require(set(asset_hashes) == set(ASSET_NAMES), "Unexpected original asset manifest")
    require(all(sha256(args.assets / name) == digest for name, digest in asset_hashes.items()), "Fixture asset drift")
    result["runtime_asset_hashes"] = asset_hashes

    temporary_path = None
    try:
        with tempfile.TemporaryDirectory(prefix="private-", dir=args.out) as temporary:
            temporary_path = Path(temporary)
            root = temporary_path / "instance"
            root.mkdir()
            private_temp = temporary_path / "java-temp"
            private_temp.mkdir()
            private_cache = temporary_path / "runtime-cache"
            # Use an isolated cache copy because RuntimeCache can remove an invalid entry.
            key = RuntimeCache(args.assets, private_cache).key
            private_cache.mkdir()
            shutil.copytree(args.cache / key, private_cache / key)
            restore = RuntimeCache(args.assets, private_cache).restore(root)
            result["cache_restore"] = restore
            require(restore["status"] == "hit", "Copied test runtime cache did not pass integrity check")
            (root / "mods").mkdir()
            for name in ASSET_NAMES:
                parent = root / "mods" if name in {"probe.jar", "fabric-api.jar"} else root
                shutil.copyfile(args.assets / name, parent / name)
            installed_jar = root / "mods" / "studio-built.jar"
            shutil.copyfile(args.jar, installed_jar)
            require(sha256(installed_jar) == result["jar_sha256"], "Generated JAR copy drift")

            game_port, rcon_port = free_port(), free_port()
            while rcon_port == game_port:
                rcon_port = free_port()
            password = secrets.token_hex(24)
            (root / "eula.txt").write_text("eula=true\n", encoding="utf-8")
            (root / "server.properties").write_text(f"server-ip=127.0.0.1\nserver-port={game_port}\n"
                f"enable-rcon=true\nrcon.port={rcon_port}\nrcon.password={password}\n"
                f"level-seed=42\nlevel-type=minecraft:flat\ngenerator-settings={FLAT_SETTINGS}\n"
                "view-distance=3\nsimulation-distance=3\nonline-mode=true\npause-when-empty-seconds=-1\n",
                encoding="utf-8")
            env = os.environ.copy()
            env.update({key: str(private_temp) for key in ("TEMP", "TMP", "TMPDIR")})
            cmd = [str(args.java), "-Xms512M", "-Xmx2G", "-XX:ActiveProcessorCount=4",
                   "-Dmms.debug.enabled=true", "-Dmms.debug.overworld.pos=0,80,0", f"-Dmms.debug.recipe={args.recipe}",
                   "-Dmms.debug.recipe_experiment=true", f"-Dmms.debug.recipe_input={','.join(args.inputs)}",
                   "-jar", "fabric-server.jar", "nogui"]
            with (args.out / "server.log").open("wb") as log:
                result["server_started_monotonic"] = time.monotonic()
                proc = subprocess.Popen(cmd, cwd=root, env=env, stdin=subprocess.PIPE, stdout=log,
                                        stderr=subprocess.STDOUT, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
                result["java_pid"] = proc.pid
                print(f"Real Fabric process {proc.pid} started; waiting for native probe.", flush=True)
                try:
                    asyncio.run(inspect_with_mcp(args, root, proc, password, rcon_port, result, manifest))
                finally:
                    result["server_exit"] = stop_server(proc)
                    for report in sorted((root / "crash-reports").glob("*.txt")):
                        shutil.copyfile(report, args.out / report.name)
            require(sha256(installed_jar) == result["jar_sha256"] == sha256(args.jar), "JAR changed during test")
            log_text = (args.out / "server.log").read_text(encoding="utf-8", errors="replace")
            require(f"STUDIO_INIT_V1 {manifest['id']}" in log_text, "Generated Java init marker is missing")
            require(re.search(r"\[Server thread/INFO\]: Done \(", log_text), "Minecraft Done marker is missing")
    finally:
        if temporary_path is not None:
            result["private_world_removed"] = not temporary_path.exists()
        result.pop("server_started_monotonic", None)
    require(result["server_exit"] == {"method": "console_stop", "exit_code": 0}, "Test JVM did not stop cleanly")
    require(result["private_world_removed"], "Temporary world still exists")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jar", type=Path, required=True)
    parser.add_argument("--recipe", type=resource_id, required=True)
    parser.add_argument("--inputs", type=resource_id, nargs="+", required=True)
    parser.add_argument("--item", type=resource_id, required=True)
    parser.add_argument("--block", type=resource_id)
    parser.add_argument("--entity", type=resource_id)
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=360)
    for name, path in {"out": OUT, "repo": REPO, "assets": ASSETS, "cache": CACHE, "java": JAVA}.items():
        parser.add_argument("--" + name, type=Path, default=path)
    parser.add_argument("--accept-eula", action="store_true")
    args = parser.parse_args()
    if not args.accept_eula:
        parser.error("Use --accept-eula if Minecraft EULA is already accepted for this test environment")
    if not 1 <= len(args.inputs) <= 3 or args.count <= 0 or args.timeout <= 0:
        parser.error("Provide 1–3 horizontal nonempty recipe slots, positive count, and positive timeout")
    if os.name != "nt":
        parser.error("This acceptance driver is for Windows")
    for name in ("jar", "out", "repo", "assets", "cache", "java"):
        setattr(args, name, getattr(args, name).resolve())
    args.out.mkdir(parents=True, exist_ok=False)
    result = {"status": "FAILED", "scope": "production JAR in a disposable dedicated server; native recipe assembly",
              "jar_file": args.jar.name, "accepted_eula_flag": True}
    try:
        run(args, result)
        result["status"] = "PRODUCTION_JAR_MCP_RUNTIME_PASS"
        return 0
    except Exception as exc:
        result["error"] = str(exc)
        (args.out / "failure.txt").write_text(traceback.format_exc(), encoding="utf-8")
        return 1
    finally:
        dump(args.out / "result.json", result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    sys.exit(main())

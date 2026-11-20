"""Opt-in real Minecraft 26.2 server smoke test, only in a fresh temporary world."""
import argparse
import hashlib
import json
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path
from debug_lab import query, collect

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"

def get_json(url):
    with urllib.request.urlopen(url, timeout=45) as f:
        return json.load(f)

def download_server(path, version):
    entry = next(v for v in get_json(MANIFEST)["versions"] if v["id"] == version)
    info = get_json(entry["url"])["downloads"]["server"]
    h = hashlib.sha1()
    count = 0
    with urllib.request.urlopen(info["url"], timeout=60) as source, path.open("wb") as dest:
        while chunk := source.read(1024 * 1024):
            count += len(chunk)
            if count > info["size"]:
                raise ValueError("unexpected server JAR size")
            h.update(chunk)
            dest.write(chunk)
    if count != info["size"] or h.hexdigest() != info["sha1"]:
        raise ValueError("server JAR checksum mismatch")
    return h.hexdigest()

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]

def until(fn, timeout, process):
    end = time.monotonic() + timeout
    last = ""
    while time.monotonic() < end:
        if process.poll() is not None:
            raise RuntimeError("Minecraft exited before fixture completed")
        try:
            if result := fn():
                return result
        except (OSError, ValueError) as exc:
            last = type(exc).__name__
        time.sleep(1)
    raise TimeoutError("Minecraft fixture deadline exceeded " + last)

def run(seed, output):
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    password = secrets.token_hex(24)
    rcon, game = free_port(), free_port()
    while game == rcon:
        game = free_port()
    with tempfile.TemporaryDirectory(prefix="mms-ai-debug-") as tmp:
        root = Path(tmp)
        sha = download_server(root / "server.jar", "26.2")
        (root / "eula.txt").write_text("eula=true\n")
        (root / "server.properties").write_text(
            f"server-ip=127.0.0.1\nserver-port={game}\nenable-rcon=true\nrcon.port={rcon}\n"
            f"rcon.password={password}\nlevel-seed={seed}\nlevel-type=minecraft:flat\n"
            "view-distance=3\nsimulation-distance=3\nonline-mode=true\n"
            "spawn-protection=0\n", encoding="utf-8")
        with (output / "server.log").open("wb") as log:
            proc = subprocess.Popen(["java","-Xms512M","-Xmx2G","-jar","server.jar","nogui"],
                                    cwd=root, stdin=subprocess.PIPE, stdout=log,
                                    stderr=subprocess.STDOUT, text=True)
            def console(command):
                proc.stdin.write(command + "\n")
                proc.stdin.flush()
            def read(op):
                return query(op, password, rcon, 8)
            chest = {"op":"block_matches","dimension":"minecraft:overworld","pos":[0,80,0],"block":"minecraft:chest"}
            nbt = {"op":"block_nbt","dimension":"minecraft:overworld","pos":[0,80,0]}
            try:
                first = until(lambda: (r if "players online" in (r:=read({"op":"players"})).lower()
                               else None), 180, proc)
                # Test harness setup only: never exposed as agent tool.
                console("execute in minecraft:overworld run forceload add 0 0")
                def place_fixture():
                    console("execute in minecraft:overworld run setblock 0 80 0 minecraft:chest")
                    return "test passed" in read(chest).lower()
                until(place_fixture, 60, proc)
                # Correct credential, real server read-only operations, repeated samples.
                before = read(nbt)
                if "minecraft:chest" not in before:
                    raise AssertionError("expected chest block-entity NBT")
                plan = [{"op":"players"},{"op":"ticks"},{"op":"gametime"},chest,nbt]
                evidence = collect(plan, password, rcon, repeat=3, interval=0.25, timeout=8)
                for row in evidence["measurements"]:
                    if row["transport"] != "received":
                        raise AssertionError("transport error: " + str(row))
                    # RCON transport success alone does not certify Minecraft command success.
                    kind = row["operation"]["op"]
                    raw = row["raw_response"].lower()
                    expected = {"players":"players online","ticks":"tick","gametime":"the time is",
                                "block_matches":"test passed","block_nbt":"minecraft:chest"}[kind]
                    if expected not in raw or "unknown or incomplete command" in raw or "incorrect argument" in raw:
                        raise AssertionError("unexpected vanilla output: " + str(row))
                after = read(nbt)
                if before != after:
                    raise AssertionError("fixture NBT changed")
                try:
                    query({"op":"players"}, "wrong-" + password, rcon, 8)
                except PermissionError:
                    pass
                else:
                    raise AssertionError("invalid password accepted")
                evidence.update(version="26.2", seed=seed, server_jar_sha1=sha,
                                fixture_nbt_unchanged=True, rejects_wrong_password=True,
                                initial_player_query=first, scope="vanilla dedicated server only")
                (output / "evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
                print("AI_DEBUG_LIVE_PASS", seed, len(evidence["measurements"]))
            finally:
                try:
                    if proc.poll() is None:
                        console("stop")
                        proc.wait(timeout=35)
                except (OSError, subprocess.TimeoutExpired):
                    proc.kill()
                    proc.wait(timeout=10)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--accept-eula", action="store_true")
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--out", type=Path, required=True)
    a=p.parse_args()
    if not a.accept_eula:
        p.error("Review https://www.minecraft.net/eula and explicitly pass --accept-eula")
    run(a.seed, a.out)

if __name__=="__main__":
    main()

"""Local, read-only Minecraft diagnostic tools. Python 3.11+, stdlib only."""
import argparse
import hashlib
import json
import os
import re
import socket
import struct
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

MAX_RESPONSE = 2 * 1024 * 1024
MAX_METADATA = 256 * 1024
DIM = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+", re.ASCII)

def timestamp():
    return datetime.now(timezone.utc).isoformat()

def compile_read(op):
    """No free-form commands; rejects unknown fields and selectors."""
    if not isinstance(op, dict):
        raise ValueError("operation must be an object")
    kind = op.get("op")
    if not isinstance(kind, str):
        raise ValueError("operation name must be a string")
    fixed = {"players": "list", "ticks": "tick query", "gametime": "time query gametime"}
    if kind in fixed and set(op) == {"op"}:
        return fixed[kind]
    if kind in ("block_nbt", "entity_nbt", "block_matches"):
        keys = {"op", "dimension", "pos"} if kind != "entity_nbt" else {"op", "dimension", "uuid"}
        if kind == "block_matches":
            keys.add("block")
        if set(op) != keys:
            raise ValueError("unexpected or missing arguments")
        dim = op["dimension"]
        if not isinstance(dim, str) or len(dim) > 128 or not DIM.fullmatch(dim):
            raise ValueError("invalid dimension")
        prefix = "execute in " + dim + " run "
        if kind == "entity_nbt":
            if not isinstance(op["uuid"], str):
                raise ValueError("invalid entity UUID")
            return prefix + "data get entity " + str(uuid.UUID(op["uuid"]))
        pos = op["pos"]
        if not isinstance(pos, list) or len(pos) != 3 or any(type(v) is not int or abs(v) > 30_000_000 for v in pos):
            raise ValueError("invalid position (absolute integers required)")
        xyz = " ".join(map(str, pos))
        if kind == "block_matches":
            block = op["block"]
            if not isinstance(block, str) or len(block) > 128 or not DIM.fullmatch(block):
                raise ValueError("invalid block id")
            return prefix + "execute if block " + xyz + " " + block
        return prefix + "data get block " + xyz
    raise ValueError("unsupported read operation")

def packet(req, kind, payload):
    body = struct.pack("<ii", req, kind) + payload + b"\0\0"
    return struct.pack("<i", len(body)) + body

def read_exact(sock, n, deadline):
    parts = bytearray()
    while len(parts) < n:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("RCON deadline exceeded")
        sock.settimeout(remaining)
        chunk = sock.recv(n - len(parts))
        if not chunk:
            raise ConnectionError("RCON closed before complete response")
        parts.extend(chunk)
    return bytes(parts)

def read_packet(sock, deadline):
    size = struct.unpack("<i", read_exact(sock, 4, deadline))[0]
    if not 10 <= size <= 65536:
        raise ValueError("invalid RCON frame length")
    body = read_exact(sock, size, deadline)
    if body[-2:] != b"\0\0":
        raise ValueError("invalid RCON terminator")
    req, kind = struct.unpack("<ii", body[:8])
    return req, kind, body[8:-2]

def query(op, password, port=25575, timeout=5):
    command = compile_read(op)
    if not isinstance(password, str) or not password or "\0" in password or len(password.encode()) > 512:
        raise ValueError("invalid RCON password")
    if not 1 <= port <= 65535 or not 0.1 <= timeout <= 60:
        raise ValueError("invalid port or timeout")
    deadline = time.monotonic() + timeout
    # Fixed loopback address; never accepts an external host or arbitrary commands.
    with socket.create_connection(("127.0.0.1", port), timeout=timeout) as sock:
        sock.sendall(packet(1, 3, password.encode()))
        while True:
            req, typ, body = read_packet(sock, deadline)
            if req == -1:
                raise PermissionError("RCON authentication failed")
            if req == 1 and typ == 2:
                break
            if (req, typ, body) != (1, 0, b""):
                raise ValueError("unexpected authentication frame")
        # Minecraft responds to the invalid request type with an independent ID.
        # This is a framing sentinel, not a Minecraft game command.
        sock.sendall(packet(2, 2, command.encode()))
        sock.sendall(packet(3, 200, b""))
        response = bytearray()
        frames = 0
        while True:
            req, typ, body = read_packet(sock, deadline)
            if typ != 0:
                raise ValueError("unexpected RCON response type")
            if req == 3:
                if frames == 0 or body != b"Unknown request c8":
                    raise ValueError("missing command reply or unsupported sentinel")
                return response.decode("utf-8", errors="replace")
            if req != 2:
                raise ValueError("unexpected RCON response ID")
            frames += 1
            response.extend(body)
            if len(response) > MAX_RESPONSE or frames > 1024:
                raise ValueError("RCON response limit exceeded")

def collect(operations, password, port=25575, repeat=1, interval=0.25, timeout=5):
    if not isinstance(operations, list) or not 1 <= len(operations) <= 20 or not 1 <= repeat <= 10 or not 0 <= interval <= 10:
        raise ValueError("plan exceeds sampling limits")
    # Validate the full plan before connecting.
    for op in operations:
        compile_read(op)
    measurements = []
    for i in range(repeat):
        for op in operations:
            row = {"sample": i + 1, "at": timestamp(), "operation": op}
            start = time.monotonic()
            try:
                row.update(transport="received", raw_response=query(op, password, port, timeout))
            except (OSError, ValueError) as exc:
                row.update(transport="error", error_type=type(exc).__name__)
            row["elapsed_ms"] = round((time.monotonic() - start) * 1000, 2)
            measurements.append(row)
        if i + 1 < repeat:
            time.sleep(interval)
    return {"schema": 1, "mode": "read_only", "measurements": measurements,
            "limitations": ["Raw responses are not proof that commands succeeded.",
                            "Repeated observations of one server are not independent trials.",
                            "Latency includes transport and command execution, not server MSPT."]}

def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()

def scan_mods(folder):
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("mods folder must exist")
    result, ids = [], {}
    for path in sorted(folder.glob("*.jar")):
        row = {"file": path.name}
        try:
            if path.is_symlink() or not path.is_file():
                raise ValueError("non-regular JAR")
            row["sha256"] = sha256(path)
            with zipfile.ZipFile(path) as z:
                names = [n for n in z.infolist() if n.filename == "fabric.mod.json"]
                if len(names) > 1:
                    raise ValueError("duplicate manifest")
                if not names:
                    row["status"] = "non_fabric_or_unknown"
                else:
                    info = names[0]
                    if info.file_size > MAX_METADATA:
                        raise ValueError("manifest too large")
                    with z.open(info) as f:
                        raw = f.read(MAX_METADATA + 1)
                    if len(raw) > MAX_METADATA:
                        raise ValueError("manifest too large")
                    meta = json.loads(raw)
                    if not isinstance(meta, dict) or not isinstance(meta.get("id"), str):
                        raise ValueError("invalid manifest")
                    row.update(status="fabric_manifest", id=meta["id"], version=meta.get("version"),
                               depends=meta.get("depends", {}), breaks=meta.get("breaks", {}),
                               nested_jars=meta.get("jars", []), provides=meta.get("provides", []))
                    ids.setdefault(row["id"], []).append(path.name)
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
            row.update(status="unreadable", error_type=type(exc).__name__)
        result.append(row)
    return {"schema": 1, "jars": result, "duplicate_declared_ids": {k:v for k,v in ids.items() if len(v)>1},
            "limitations": ["Static top-level Fabric metadata only; no version resolution, nested JAR scanning or runtime proof."]}

def trial_summary(trials):
    """Summarize explicit independent trial records, never infer cause."""
    if not isinstance(trials, list):
        raise ValueError("trials must be a list")
    groups = {}
    seen = set()
    for row in trials:
        if not isinstance(row, dict) or set(row) != {"trial_id", "condition", "seed", "outcome"}:
            raise ValueError("invalid trial record")
        ident, cond, seed, outcome = (row[k] for k in ("trial_id", "condition", "seed", "outcome"))
        if not isinstance(ident, str) or not ident or ident in seen or not isinstance(cond, str) or not cond or type(seed) is not int or outcome not in ("observed", "not_observed", "invalid"):
            raise ValueError("invalid or duplicate trial")
        seen.add(ident)
        g = groups.setdefault(cond, {"observed":0, "not_observed":0, "invalid":0, "seeds":set()})
        g[outcome] += 1
        if outcome != "invalid":
            g["seeds"].add(seed)
    for g in groups.values():
        n = g["observed"] + g["not_observed"]
        g["seeds"] = sorted(g["seeds"])
        g["valid"] = n
        g["label"] = ("insufficient" if n < 3 or len(g["seeds"]) < 2 else
                      "observed_all" if g["observed"] == n else
                      "not_observed_in_trials" if not g["observed"] else "intermittent")
    return {"schema":1, "conditions":groups,
            "limitations":["Trial independence and matching environments must be verified externally.",
                           "Descriptive results only; no causal claim or statistical significance."]}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    s = sub.add_parser("scan"); s.add_argument("mods", type=Path)
    t = sub.add_parser("trials"); t.add_argument("records", type=Path)
    q = sub.add_parser("collect"); q.add_argument("plan", type=Path)
    q.add_argument("--port", type=int, default=25575)
    q.add_argument("--repeat", type=int, default=1)
    args = p.parse_args()
    if args.action == "scan":
        result = scan_mods(args.mods)
    elif args.action == "trials":
        result = trial_summary(json.loads(args.records.read_text(encoding="utf-8")))
    else:
        password = os.environ.get("MC_DEBUG_RCON_PASSWORD")
        if not password:
            p.error("set MC_DEBUG_RCON_PASSWORD")
        result = collect(json.loads(args.plan.read_text(encoding="utf-8")), password, args.port, args.repeat)
    print(json.dumps(result, ensure_ascii=True, indent=2))

if __name__ == "__main__":
    main()

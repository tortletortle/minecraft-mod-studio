"""H0 research fixture builder; no SDK, no game, no adapter validation."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile
import zlib


def canonical(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2,
                       allow_nan=False) + "\n").encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(path):
    if not isinstance(path, str) or len(path) > 240:
        raise ValueError("invalid archive path")
    parts = path.split("/")
    if any(not re.fullmatch(r"[a-zA-Z0-9_.-]+", p) or p in (".", "..")
           or p.endswith(".") or re.match(r"(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)", p)
           for p in parts):
        raise ValueError("unsafe archive path: " + path)
    return path


def png(spec):
    w, h, rgba = spec["width"], spec["height"], spec["rgba"]
    if (type(w) is not int or type(h) is not int or not 1 <= w <= 64
            or not 1 <= h <= 64 or len(rgba) != 4
            or any(type(v) is not int or not 0 <= v <= 255 for v in rgba)):
        raise ValueError("invalid synthetic texture")
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data)))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress((b"\0" + bytes(rgba) * w) * h, level=0))
            + chunk(b"IEND", b""))


def archive_files(record):
    files, seen = {}, set()
    def add(path, payload):
        path = safe_path(path)
        if path.casefold() in seen:
            raise ValueError("duplicate archive path: " + path)
        seen.add(path.casefold())
        files[path] = payload
    for entry in record["entries"]:
        add(entry["path"], canonical(entry["json"]))
    if "syntheticTexture" in record:
        t = record["syntheticTexture"]
        add(t["path"], png(t))
    return files


def build(fixture, out):
    source = fixture.read_bytes()
    data = json.loads(source)
    if data["schemaVersion"] != 1 or data["id"] != "rd001-static-content-v1":
        raise ValueError("unsupported fixture")
    archives = {}
    for a in data["archives"]:
        name = a["id"]
        if not re.fullmatch(r"[a-z0-9-]+", name) or name in archives:
            raise ValueError("invalid or duplicate archive id")
        archives[name] = archive_files(a)
    cases = data["cases"]
    if len({c["id"] for c in cases}) != len(cases):
        raise ValueError("duplicate case id")
    for c in cases:
        if not c["archives"] or any(a not in archives for a in c["archives"]):
            raise ValueError("unknown archive id")
    missing = next(c for c in cases if c["id"] == "C04-MISSING")
    files = dict(archives[missing["archives"][0]])
    del files[missing["mutation"]["remove"]]
    if "rd001-missing" in archives:
        raise ValueError("reserved archive id")
    archives["rd001-missing"] = files
    # Unsafe-path and rights mutations are metadata only: never materialize them.
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"scope": "STATIC_FIXTURE_ONLY", "fixtureSHA256": sha(source),
                "gameVerification": "NOT_RUN", "archives": {}, "cases": cases,
                "caseArchiveOverrides": {"C04-MISSING": ["rd001-missing"]}}
    for name, entries in sorted(archives.items()):
        target = out / (name + ".zip")
        with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_STORED) as z:
            for path, payload in sorted(entries.items()):
                info = zipfile.ZipInfo(path, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                z.writestr(info, payload)
        manifest["archives"][target.name] = {"sha256": sha(target.read_bytes()),
                                            "entries": {p: sha(b) for p, b in sorted(entries.items())}}
    (out / "manifest.json").write_bytes(canonical(manifest))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path(__file__).parent / "fixtures/static-content-v1.json")
    parser.add_argument("--out", required=True, type=Path, help="new, disposable output directory")
    args = parser.parse_args()
    build(args.fixture, args.out)

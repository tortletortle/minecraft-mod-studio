"""Measurement-only wrapper around an unchanged ai-debug-lab playtest.py."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

def utc():
    return datetime.now(timezone.utc).isoformat()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--assets", type=Path, required=True)
    p.add_argument("--evidence", type=Path, required=True)
    p.add_argument("--preserve-root", action="store_true")
    p.add_argument("--seed-runtime", type=Path)
    a = p.parse_args()
    repo, assets, evidence = a.repo.resolve(), a.assets.resolve(), a.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(repo / "ai-debug-lab"))
    import playtest
    original_td = tempfile.TemporaryDirectory
    root_holder = {}

    class MeasuredTempDir:
        def __init__(self, **kwargs):
            self.path = Path(tempfile.mkdtemp(**kwargs))
            root_holder["path"] = self.path
            if a.seed_runtime:
                for name in (".fabric", "libraries", "versions"):
                    src = a.seed_runtime.resolve() / name
                    if src.exists():
                        shutil.copytree(src, self.path / name, dirs_exist_ok=True)
            (evidence / "runtime_seed.json").write_text(json.dumps({
                "seed_runtime": str(a.seed_runtime.resolve()) if a.seed_runtime else None,
                "preserve_root": a.preserve_root, "created_utc": utc(),
                "root": str(self.path),
            }, indent=2), encoding="utf-8")
        def __enter__(self):
            return str(self.path)
        def __exit__(self, exc_type, exc, tb):
            if a.preserve_root:
                (evidence / "preserved_root.txt").write_text(str(self.path), encoding="utf-8")
            else:
                shutil.rmtree(self.path, ignore_errors=True)
            return False

    playtest.tempfile.TemporaryDirectory = MeasuredTempDir
    original_init, original_launch, original_close = playtest.Playtest.__init__, playtest.Playtest.launch, playtest.Playtest.close

    def measured_init(self, asset_dir, root, out):
        original_init(self, asset_dir, root, out)
        (evidence / "instance.json").write_text(json.dumps({
            "root": str(self.root), "game_port": self.game, "rcon_port": self.rcon,
            "inner_evidence": str(Path(out).resolve()),
            "created_utc": utc(), "created_monotonic": time.monotonic(),
            "asset_hashes": json.loads((assets / "hashes.json").read_text()),
        }, indent=2), encoding="utf-8")

    def measured_launch(self):
        before = time.monotonic()
        original_launch(self)
        (evidence / "process.json").write_text(json.dumps({
            "pid": self.proc.pid, "launch_monotonic": before, "launch_utc": utc(),
            "cwd": str(self.root), "command": self.proc.args,
        }, indent=2), encoding="utf-8")

    def measured_close(self):
        proc = self.proc
        try:
            original_close(self)
        finally:
            for name in ("server.log", "startup.json", "session.json", "actions.jsonl"):
                src, dst = self.evidence / name, evidence / name
                if src.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(src, dst)
        (evidence / "close.json").write_text(json.dumps({
                "closed_utc": utc(), "closed_monotonic": time.monotonic(),
            "java_returncode": proc.returncode if proc is not None else None,
            "root": str(root_holder.get("path")) if root_holder.get("path") else None,
            }, indent=2), encoding="utf-8")

    playtest.Playtest.__init__ = measured_init
    playtest.Playtest.launch = measured_launch
    playtest.Playtest.close = measured_close
    sys.argv = [str(repo / "ai-debug-lab/playtest.py"), "serve", "--assets", str(assets),
                "--evidence", str(evidence), "--accept-eula"]
    playtest.main()
    (evidence / "wrapper-exit.json").write_text(json.dumps({"exited_utc": utc(), "status": "returned"}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SAMPLE = ROOT / "examples" / "void_scout"


def logic_configuration() -> tuple[dict, dict]:
    graph = {
        "version": 1,
        "entry": "event",
        "variables": [],
        "nodes": [
            {"id": "event", "op": "event", "event": "use", "next": "message", "x": 0, "y": 0},
            {"id": "message", "op": "message", "text": "Behavior graph executed",
             "next": "done", "x": 1, "y": 0},
            {"id": "done", "op": "end", "success": True, "x": 2, "y": 0},
        ],
    }
    machine = {
        "enabled": True,
        "initial": "idle",
        "states": [
            {"id": "idle", "animation": "idle", "loop": True},
            {"id": "walk", "animation": "walk", "loop": True},
        ],
        "transitions": [
            {"id": "tr_walk", "from": "idle", "to": "walk", "condition": "moving",
             "threshold": 0.02, "priority": 40, "cooldown": 2},
            {"id": "tr_idle", "from": "walk", "to": "idle", "condition": "stopped",
             "threshold": 0.01, "priority": 10, "cooldown": 2},
        ],
    }
    return graph, machine


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a minimal Fabric creature with behavior_graph and state_machine enabled."
    )
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    output = args.out.resolve()

    with tempfile.TemporaryDirectory(prefix="mms-v01-logic-fixture-") as temp:
        input_dir = Path(temp) / "input"
        input_dir.mkdir()
        shutil.copyfile(SAMPLE / "void_scout.bbmodel", input_dir / "void_scout.bbmodel")
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        graph, machine = logic_configuration()
        project["behavior_graph"] = graph
        project["state_machine"] = machine
        project_path = input_dir / "creature.json"
        project_path.write_text(json.dumps(project, indent=2) + "\n", encoding="utf-8")

        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + (
            os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
        )
        command = [
            sys.executable, "-m", "creature_studio.cli", "generate",
            "--project", str(project_path), "--out", str(output),
        ]
        print("$ " + " ".join(command), flush=True)
        result = subprocess.run(command, cwd=REPO_ROOT, env=env, check=False)
        if result.returncode:
            return result.returncode

    print(f"Generated behavior/state-machine fixture: {output}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from creature_studio.behavior_graph import compile_java_method


def v1_graph():
    return {
        "version": 1,
        "entry": "event",
        "variables": [{"id": "power", "name": "Power", "type": "int", "initial": 2}],
        "nodes": [
            {"id": "event", "op": "event", "event": "use", "next": "add", "x": 0, "y": 0},
            {
                "id": "add", "op": "add", "variable": "power",
                "value": {"source": "literal", "type": "int", "value": 3},
                "next": "end", "x": 1, "y": 0,
            },
            {"id": "end", "op": "end", "success": True, "x": 2, "y": 0},
        ],
    }


def v3_graph():
    return {
        "version": 3,
        "entry": "event",
        "variables": [{"id": "result", "name": "Result", "type": "int", "initial": 0}],
        "functions": [{
            "id": "double",
            "params": [{"id": "x", "type": "int"}],
            "returns": "int",
            "body": {
                "op": "multiply",
                "a": {"op": "param", "id": "x"},
                "b": {"op": "literal", "type": "int", "value": 2},
            },
        }],
        "nodes": [
            {"id": "event", "op": "event", "event": "use", "next": "call", "x": 0, "y": 0},
            {
                "id": "call", "op": "call", "fn": "double",
                "args": [{"source": "literal", "type": "int", "value": 4}],
                "variable": "result", "next": "end", "x": 1, "y": 0,
            },
            {"id": "end", "op": "end", "success": True, "x": 2, "y": 0},
        ],
    }


def main() -> int:
    javac = shutil.which("javac")
    if not javac:
        print("ERROR: javac was not found; JDK 25 is required for this verification.", file=sys.stderr)
        return 2

    v1_source = compile_java_method(v1_graph(), 0)
    v3_source = compile_java_method(v3_graph(), 3)
    for label, source in (("V1", v1_source), ("V3", v3_source)):
        if "\\n" in source:
            raise AssertionError(f"{label} Java output contains a literal backslash-n sequence")
        if "\n" not in source:
            raise AssertionError(f"{label} Java output is not multi-line")

    java_source = f"""public final class BehaviorGraphCompileFixture {{
    static final class Context {{
        boolean sneaking() {{ return false; }}
        int stackCount() {{ return 1; }}
        void message(String value) {{ }}
        void heal(int amount) {{ }}
        boolean lightning(int amount) {{ return true; }}
    }}

    static int clamp(long value) {{
        return (int) Math.max(-1000000L, Math.min(1000000L, value));
    }}

{v1_source}
{v3_source}
}}
"""
    with tempfile.TemporaryDirectory(prefix="mms-behavior-javac-") as temp:
        root = Path(temp)
        source_file = root / "BehaviorGraphCompileFixture.java"
        classes = root / "classes"
        classes.mkdir()
        source_file.write_text(java_source, encoding="utf-8")
        version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
        print((version.stdout or version.stderr).strip())
        result = subprocess.run(
            [javac, "--release", "25", "-d", str(classes), str(source_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            return result.returncode
    print("PASS: compile_java_method V1 output compiled by javac --release 25")
    print("PASS: compile_java_method V3 output compiled by javac --release 25")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

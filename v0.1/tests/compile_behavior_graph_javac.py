from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from creature_studio.behavior_graph import compile_java_method
from test_behavior_graph import simple_graph


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
            {"id": "call", "op": "call", "fn": "double",
             "args": [{"source": "literal", "type": "int", "value": 4}],
             "variable": "result", "next": "end", "x": 1, "y": 0},
            {"id": "end", "op": "end", "success": True, "x": 2, "y": 0},
        ],
    }


def main():
    methods = compile_java_method(simple_graph(), 0) + compile_java_method(v3_graph(), 1)
    if "\\n" in methods:
        raise SystemExit("Generated Java contains a literal backslash-n sequence")
    if "static boolean run0(Context ctx) {\n" not in methods:
        raise SystemExit("Generated Java is missing real multiline V1 method structure")
    source = """final class Context {
    boolean sneaking() { return false; }
    int stackCount() { return 1; }
    void message(String value) {}
    void heal(int amount) {}
    boolean lightning(int amount) { return true; }
}
final class GeneratedBehavior {
    static int clamp(long value) { return (int) value; }
""" + methods + "\n}"
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        java_file = root / "GeneratedBehavior.java"
        java_file.write_text(source, encoding="utf-8")
        result = subprocess.run(
            ["javac", "--release", "25", "-d", str(root), str(java_file)],
            text=True, capture_output=True,
        )
        if result.returncode:
            print(result.stdout)
            print(result.stderr)
            raise SystemExit(result.returncode)
    print("PASS: javac --release 25 compiled generated V1 and V3 behavior methods")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent


def find_javac() -> str | None:
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        candidate = Path(java_home) / "bin" / ("javac.exe" if os.name == "nt" else "javac")
        if candidate.is_file():
            return str(candidate)
    return shutil.which("javac")


def run(label: str, command: list[str], env: dict[str, str]) -> int:
    print(f"\n[{label}] $ {shlex.join(command)}", flush=True)
    result = subprocess.run(command, cwd=REPO_ROOT, env=env, check=False)
    if result.returncode:
        print(f"[{label}] FAIL (exit {result.returncode})", file=sys.stderr)
        return result.returncode
    print(f"[{label}] PASS", flush=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Unified Minecraft Mod Studio V0.1 local checks")
    parser.add_argument(
        "--require-javac",
        action="store_true",
        help="Fail unless JDK 25 javac is available and the generated V1/V3 methods compile.",
    )
    args = parser.parse_args()

    env = os.environ.copy()
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing if existing else "")

    checks = [
        ("Python syntax compilation", [
            sys.executable, "-m", "compileall", "-q",
            "v0.1/creature_studio", "v0.1/tests", "v0.1/test.py",
        ]),
        ("V0.1 unit tests", [
            sys.executable, "-m", "unittest", "discover", "-s", "v0.1/tests", "-v",
        ]),
    ]
    for label, command in checks:
        code = run(label, command, env)
        if code:
            return code

    javac = find_javac()
    version_text = ""
    if javac:
        version = subprocess.run([javac, "-version"], capture_output=True, text=True, check=False)
        version_text = (version.stdout or version.stderr).strip()
    match = re.search(r"\b(\d+)", version_text)
    if not javac or not match or int(match.group(1)) < 25:
        message = "JDK 25 javac unavailable"
        if version_text:
            message += f" (found {version_text})"
        if args.require_javac:
            print(f"ERROR: {message}; --require-javac was specified.", file=sys.stderr)
            return 2
        print(f"\n[Behavior graph javac] SKIP: {message}.", flush=True)
        return 0

    return run(
        "Behavior graph javac",
        [sys.executable, "v0.1/tests/compile_behavior_graph.py"],
        env,
    )


if __name__ == "__main__":
    raise SystemExit(main())

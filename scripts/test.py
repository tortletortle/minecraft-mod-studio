#!/usr/bin/env python3
"""Unified local checks for Minecraft Mod Studio.

Levels:
  static  - Python/YAML/inline-JavaScript syntax and workflow policy checks.
  browser - Playwright browser export and archive parser acceptance.
  build   - all lower levels, material fixture checks, and real Fabric builds.
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS: list[tuple[str, str, str]] = []


def record(name: str, status: str, detail: str = "") -> None:
    RESULTS.append((name, status, detail))
    suffix = f" — {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}", flush=True)


def run_command(name: str, command: list[str], cwd: Path = ROOT) -> bool:
    print(f"\n$ {shlex.join(command)}", flush=True)
    try:
        completed = subprocess.run(command, cwd=cwd, check=False)
    except OSError as exc:
        record(name, "FAIL", str(exc))
        return False
    status = "PASS" if completed.returncode == 0 else "FAIL"
    record(name, status, f"exit code {completed.returncode}")
    return completed.returncode == 0


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


def node_check() -> tuple[bool, str]:
    executable = shutil.which("node")
    if not executable:
        return False, "Node.js 22.x is not on PATH"
    try:
        result = subprocess.run(
            [executable, "--version"], capture_output=True, text=True, check=False
        )
    except OSError as exc:
        return False, f"Could not run Node.js: {exc}"
    match = re.search(r"v?(\d+)", result.stdout.strip())
    if result.returncode != 0 or not match:
        return False, "Could not determine the Node.js version"
    version = result.stdout.strip()
    if int(match.group(1)) < 22:
        return False, f"Node.js 22.x or newer is required; found {version}"
    return True, version


def chromium_check() -> tuple[bool, str]:
    if not has_module("playwright"):
        return False, "Python package 'playwright' is missing; install requirements-dev.txt"
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            executable = Path(playwright.chromium.executable_path)
        if not executable.is_file():
            return False, "Playwright Chromium is missing; run: python -m playwright install chromium"
    except Exception as exc:
        return False, f"Playwright/Chromium could not be initialized: {exc}"
    return True, str(executable)


def load_browser_export_module():
    path = ROOT / "tests" / "acceptance" / "test_browser_export.py"
    spec = importlib.util.spec_from_file_location("mms_browser_export_test", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_static() -> bool:
    start = len(RESULTS)
    print("\n=== STATIC CHECKS ===", flush=True)

    if sys.version_info < (3, 9):
        record("Python syntax", "NOT RUN", "Python 3.9 or newer is required")
    else:
        try:
            python_files = sorted((ROOT / "tests").rglob("*.py"))
            python_files.append(Path(__file__).resolve())
            if not python_files:
                raise RuntimeError("No Python test files were found")
            for path in python_files:
                compile(path.read_text(encoding="utf-8-sig"), str(path), "exec")
            record("Python syntax", "PASS", f"{len(python_files)} files compiled in memory")
        except Exception as exc:
            record("Python syntax", "FAIL", str(exc))

    if not has_module("yaml"):
        detail = "PyYAML is missing; install requirements-dev.txt"
        record("Workflow YAML syntax", "NOT RUN", detail)
        record("Workflow EULA/trigger policy", "NOT RUN", detail)
    else:
        import yaml

        workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        workflows += sorted((ROOT / ".github" / "workflows").glob("*.yaml"))
        try:
            for path in workflows:
                yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
            if not workflows:
                raise RuntimeError("No GitHub Actions workflow files were found")
            record("Workflow YAML syntax", "PASS", f"{len(workflows)} workflow files parsed")
        except Exception as exc:
            record("Workflow YAML syntax", "FAIL", str(exc))
        run_command(
            "Workflow EULA/trigger policy",
            [sys.executable, str(ROOT / "tests" / "acceptance" / "test_workflow_policy.py")],
        )

    node_ok, node_detail = node_check()
    if not node_ok or not has_module("playwright"):
        missing = node_detail if not node_ok else "Python package 'playwright' is missing"
        record("Inline JavaScript syntax", "NOT RUN", missing)
    else:
        try:
            source = ROOT / "Minecraft_Mod_Studio_V19.html"
            if not source.is_file():
                raise FileNotFoundError(f"Maintained HTML source not found: {source}")
            checked = load_browser_export_module().check_inline_javascript(
                source.read_text(encoding="utf-8-sig")
            )
            record("Inline JavaScript syntax", "PASS", f"{checked} inline script blocks checked with Node.js {node_detail}")
        except Exception as exc:
            record("Inline JavaScript syntax", "FAIL", str(exc))

    return all(status == "PASS" for _, status, _ in RESULTS[start:])


def run_browser(work_dir: Path) -> tuple[bool, Path | None]:
    start = len(RESULTS)
    print("\n=== BROWSER ACCEPTANCE ===", flush=True)

    missing: list[str] = []
    node_ok, node_detail = node_check()
    if not node_ok:
        missing.append(node_detail)
    if not has_module("playwright"):
        missing.append("Python package 'playwright' is missing")
    chromium_ok, chromium_detail = chromium_check()
    if not chromium_ok:
        missing.append(chromium_detail)

    if missing:
        detail = "; ".join(dict.fromkeys(missing))
        record("Browser export acceptance", "NOT RUN", detail)
        record("ZIP/JAR archive security acceptance", "NOT RUN", detail)
        return False, None

    export_dir = work_dir / "export"
    browser_ok = run_command(
        "Browser export acceptance",
        [
            sys.executable,
            str(ROOT / "tests" / "acceptance" / "test_browser_export.py"),
            "--export-dir",
            str(export_dir),
        ],
    )
    archive_ok = run_command(
        "ZIP/JAR archive security acceptance",
        [sys.executable, str(ROOT / "tests" / "resources" / "archive_security.py")],
        cwd=work_dir,
    )
    if browser_ok and archive_ok:
        record("Browser prerequisites", "PASS", f"Node.js {node_detail}; Chromium available")
    return browser_ok and archive_ok and all(
        status != "FAIL" for _, status, _ in RESULTS[start:]
    ), export_dir if browser_ok else None


def java_major(command: str, pattern: str) -> tuple[int | None, str]:
    executable = shutil.which(command)
    if not executable:
        return None, f"{command} is not on PATH"
    try:
        result = subprocess.run([executable, "-version"], capture_output=True, text=True, check=False)
    except OSError as exc:
        return None, f"Could not run {command}: {exc}"
    output = result.stdout + result.stderr
    match = re.search(pattern, output)
    if result.returncode != 0 or not match:
        return None, f"Could not determine {command} version"
    return int(match.group(1)), match.group(0)


def full_build_prerequisites() -> list[str]:
    missing: list[str] = []
    if not has_module("PIL"):
        missing.append("Python package 'Pillow' is missing")
    java_version, java_detail = java_major("java", r'version "(\d+)')
    javac_version, javac_detail = java_major("javac", r"javac\s+(\d+)")
    if java_version != 25:
        missing.append(f"JDK 25 java required ({java_detail})")
    if javac_version != 25:
        missing.append(f"JDK 25 javac required ({javac_detail})")

    gradle = shutil.which("gradle")
    if not gradle:
        missing.append("Gradle 9.5.1 is not on PATH")
    else:
        try:
            result = subprocess.run([gradle, "--version"], capture_output=True, text=True, check=False)
            output = result.stdout + result.stderr
            match = re.search(r"Gradle\s+([0-9][0-9A-Za-z.+-]*)", output)
            if result.returncode != 0 or not match or match.group(1) != "9.5.1":
                found = match.group(1) if match else "unknown"
                missing.appendBUILD_TEST_NAMES = (
    "Material fixture generation and Java rig assertions",
    "Default generated Fabric project build",
    "Material fixture Fabric project build",
    "Resource library acceptance and imported-resource Fabric build",
)


def record_build_not_run(reason: str) -> None:
    for name in BUILD_TEST_NAMES:
        record(name, "NOT RUN", reason)


def run_full_build(work_dir: Path, export_dir: Path) -> bool:
    print("\n=== FULL FABRIC BUILD ===", flush=True)
    missing = full_build_prerequisites()
    if missing:
        detail = "; ".join(missing)
        record("Full build prerequisites", "NOT RUN", detail)
        record_build_not_run("Missing full-build environment: " + detail)
        return False
    record("Full build prerequisites", "PASS", "Pillow; JDK 25; Gradle 9.5.1")

    material_dir = work_dir / "material"
    material_ok = run_command(
        BUILD_TEST_NAMES[0],
        [
            sys.executable,
            str(ROOT / "tests" / "materials" / "material_fixture.py"),
            "--html",
            str(ROOT / "Minecraft_Mod_Studio_V19.html"),
            "--baseline",
            str(export_dir / "studio-project.json"),
            "--out",
            str(material_dir),
        ],
    )
    default_ok = run_command(
        BUILD_TEST_NAMES[1],
        [sys.executable, str(export_dir / "studio_build.py"), "build"],
        cwd=export_dir,
    )
    if material_ok:
        material_build_ok = run_command(
            BUILD_TEST_NAMES[2],
            [sys.executable, str(material_dir / "project" / "studio_build.py"), "build"],
            cwd=material_dir / "project",
        )
    else:
        record(BUILD_TEST_NAMES[2], "NOT RUN", "Material fixture generation did not pass")
        material_build_ok = False

    resource_ok = run_command(
        BUILD_TEST_NAMES[3],
        [sys.executable, str(ROOT / "tests" / "resources" / "resource_library_acceptance.py")],
        cwd=work_dir,
    )
    return material_ok and default_ok and material_build_ok and resource_ok


ir,
        ),
    ]

    for name, command, cwd in steps:
        if not run_command(name, command, cwd=cwd):
            return False
    return True


@contextmanager
def workspace(path: Path | None):
    if path is not None:
        target = path.resolve()
        target.mkdir(parents=True, exist_ok=True)
        if any(target.iterdir()):
            raise SystemExit(f"--work-dir must be empty: {target}")
        print(f"Keeping generated test artifacts in: {target}", flush=True)
        yield target
    else:
        with tempfile.TemporaryDirectory(prefix="mms-local-tests-") as temporary:
            yield Path(temporary)


def summary() -> int:
    passed = sum(status == "PASS" for _, status, _ in RESULTS)
    failed = sum(status == "FAIL" for _, status, _ in RESULTS)
    not_run = sum(status == "NOT RUN" for _, status, _ in RESULTS)
    print(f"\nSUMMARY: PASS={passed} FAIL={failed} NOT RUN={not_run}", flush=True)
    if failed:
        return 1
    if not_run:
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("level", choices=("static", "browser", "build"))
    parser.add_argument(
        "--work-dir",
        type=Path,
        help="Optional empty directory for generated projects and test evidence; kept after the run",
    )
    args = parser.parse_args()

    with workspace(args.work_dir) as work_dir:
        if args.level == "static":
            run_static()
        elif args.level == "browser":
            run_browser(work_dir)
        else:
            static_ok = run_static()
            browser_ok, export_dir = run_browser(work_dir)
            if static_ok and browser_ok and export_dir is not None:
                run_full_build(work_dir, export_dir)
            else:
                missing = full_build_prerequisites()
                if missing:
                    record("Full build prerequisites", "NOT RUN", "; ".join(missing))
                else:
                    record("Full build prerequisites", "PASS", "Pillow; JDK 25; Gradle 9.5.1")
                reasons = ["Static checks and browser acceptance must both pass first"]
                reasons.extend(missing)
                record_build_not_run("; ".join(reasons))
    return summary()


if __name__ == "__main__":
    raise SystemExit(main())

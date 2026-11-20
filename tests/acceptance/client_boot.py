#!/usr/bin/env python3
"""Run a test-only development client overlay in a disposable Linux directory.
Requires a successful unchanged export build, Xvfb, Gradle and JDK 25.
Never writes eula.txt or starts a world. Does not test the packaged JAR in production.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
MARKER = re.compile(r"(?m)\bMMS_CLIENT_PROBE_PASS title_frames=(\d+) items=5 blocks=1 entities=1 texture=1 poses=4\s*$")

def load_doctor(project):
    spec = importlib.util.spec_from_file_location("studio_build", project / "studio_build.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def stop(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=15)
        except ProcessLookupError:
            pass

def marker(log):
    matches = MARKER.findall(log)
    return len(matches) == 1 and int(matches[0]) >= 10

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    a = parser.parse_args()
    source, work = a.project.resolve(), a.work.resolve()
    if work.exists() or work == source or work.is_relative_to(source) or source.is_relative_to(work) or a.timeout <= 0:
        raise SystemExit("Provide a new, separate work directory and a positive timeout")
    work.mkdir(parents=True)
    evidence = work / "evidence"
    evidence.mkdir()
    result = {"status": "NOT_RUN", "scope": "instrumented development client title screen, registrations, texture lookup, actual ModelPart pose sampling; no world, production JAR runtime or rendered mob", "worldOpened": False, "eulaWritten": False}
    dest = work / "project"
    proc = None
    rc = 1
    try:
        doctor = load_doctor(source)
        report, meta, digest = doctor.source_check(source)
        receipt = json.loads((source / "studio-build-result.json").read_text())
        if meta["id"] != "stormshard_mod" or receipt.get("status") != "BUILD_VERIFIED" or receipt.get("sourceSha256") != digest:
            raise RuntimeError("Verified default fixture build required")
        jar = source / "build/libs" / (meta["id"] + "-" + meta["version"] + ".jar")
        jar_digest = doctor.check_jar(jar, report, meta)["sha256"]
        if jar_digest != receipt["jar"]["sha256"]:
            raise RuntimeError("Baseline JAR integrity mismatch")
        result.update(sourceSha256=digest, baselineJarSha256=jar_digest)
        # Copy only the manifest-controlled original export files. Do not copy a run directory or cache.
        manifest = json.loads((source / "studio-build-manifest.json").read_text())
        for name in [*manifest["files"], "studio-build-manifest.json"]:
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / name, target)
        probe = HERE / "ClientBootProbe.java"
        target = dest / "src/client/java/studio/acceptance/ClientBootProbe.java"
        target.parent.mkdir(parents=True)
        shutil.copyfile(probe, target)
        test_meta = dest / "src/main/resources/fabric.mod.json"
        # Explicit, test-only overlay. The release JAR and source manifest remain unchanged.
        meta["entrypoints"].setdefault("client", []).append("studio.acceptance.ClientBootProbe")
        test_meta.write_text(json.dumps(meta, indent=2) + "\n")
        result["probeSha256"] = hashlib.sha256(probe.read_bytes()).hexdigest()
        if not os.environ.get("DISPLAY") or not shutil.which("gradle"):
            raise RuntimeError("DISPLAY and Gradle are required; use xvfb-run")
        log = evidence / "client.log"
        cmd = ["gradle", "--no-daemon", "--console=plain", "runClient"]
        result["command"] = cmd
        with log.open("wb") as out:
            proc = subprocess.Popen(cmd, cwd=dest, stdin=subprocess.DEVNULL, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
            deadline = time.monotonic() + a.timeout
            captured = False
            while proc.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Client did not exit successfully before deadline")
                text = log.read_text(errors="replace")
                if marker(text) and not captured:
                    captured = True
                    if shutil.which("scrot"):
                        shot = subprocess.run(["scrot", str(evidence / "title-screen.png")], capture_output=True, timeout=10)
                        result["screenshotCaptured"] = shot.returncode == 0 and (evidence / "title-screen.png").is_file()
                time.sleep(.2)
            text = log.read_text(errors="replace")
            result["gradleExit"] = proc.returncode
            result["initMarker"] = "STUDIO_INIT_V1 stormshard_mod" in text
            result["probeMarker"] = marker(text)
            if proc.returncode or not result["initMarker"] or not result["probeMarker"] or "MMS_CLIENT_CHECK_FAILED" in text:
                raise RuntimeError("Required runtime checks or clean Gradle exit missing; inspect client.log")
        if doctor.source_check(source)[2] != digest or doctor.check_jar(jar, report, json.loads((source/"src/main/resources/fabric.mod.json").read_text()))["sha256"] != jar_digest:
            raise RuntimeError("Baseline modified")
        if list(dest.rglob("eula.txt")) or (dest / "run/saves").exists() and any((dest / "run/saves").iterdir()):
            raise RuntimeError("Unexpected EULA or world data in isolated run")
        result["status"] = "DEV_CLIENT_BOOT_VERIFIED"
        rc = 0
    except Exception as exc:
        result.update(status="CLIENT_BOOT_FAILED", message=repr(exc))
    finally:
        if proc is not None:
            stop(proc)
        for name in ("logs", "crash-reports"):
            path = dest / "run" / name
            if path.is_dir():
                shutil.copytree(path, evidence / name, dirs_exist_ok=True)
        (evidence / "result.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2))
    return rc

if __name__ == "__main__":
    sys.exit(main())

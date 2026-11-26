#!/usr/bin/env python3
"""Prepare an isolated, disposable V0.1 GameTest source set after explicit EULA opt-in."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--accept-eula", action="store_true")
    args = parser.parse_args()

    if not args.accept_eula:
        parser.error("Review https://aka.ms/MinecraftEULA before passing --accept-eula")

    source = args.project.resolve()
    destination = args.work.resolve()
    if not source.is_dir() or destination.exists():
        parser.error("Source project must exist and destination must be a new directory")
    if destination.is_relative_to(source) or source.is_relative_to(destination):
        parser.error("The isolated test directory must be independent of the generated project")

    shutil.copytree(source, destination)
    build_file = destination / "build.gradle"
    build_file.write_text(
        build_file.read_text(encoding="utf-8")
        + '''
fabricApi {
    configureTests {
        createSourceSet = true
        modId = "mms_v01_creature_test"
        enableGameTests = true
        enableClientGameTests = true
        eula = true
    }
}
''',
        encoding="utf-8"
    )

    package = destination / "src/gametest/java/studio/acceptance"
    package.mkdir(parents=True, exist_ok=True)
    test_root = Path(__file__).resolve().parent
    for name in ("WorldGameTests.java", "ClientWorldTest.java"):
        shutil.copyfile(test_root / name, package / name)

    resources = destination / "src/gametest/resources"
    resources.mkdir(parents=True, exist_ok=True)
    test_mod = {
        "schemaVersion": 1,
        "id": "mms_v01_creature_test",
        "version": "1.0.0",
        "name": "Mod Studio V0.1 isolated creature acceptance tests",
        "environment": "*",
        "entrypoints": {
            "fabric-gametest": ["studio.acceptance.WorldGameTests"],
            "fabric-client-gametest": ["studio.acceptance.ClientWorldTest"]
        },
        "depends": {"voidscout": "*"}
    }
    (resources / "fabric.mod.json").write_text(json.dumps(test_mod, indent=2) + "\n", encoding="utf-8")

    # This EULA file exists only in the disposable copied GameTest run directory.
    server_run = destination / "build/run/gameTest"
    server_run.mkdir(parents=True, exist_ok=True)
    (server_run / "eula.txt").write_text("eula=true\n", encoding="utf-8")

    receipt = {
        "eulaOptIn": True,
        "scope": "Disposable GameTest copy only; generated production project and JAR are not modified.",
        "sourceProject": str(source),
        "testProject": str(destination)
    }
    (destination / "v01-world-test-consent.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print("Prepared isolated V0.1 GameTest project. Production generated project was not modified.")


if __name__ == "__main__":
    main()

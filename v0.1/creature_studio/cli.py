from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from .blockbench import export_bbmodel, import_bbmodel
from .generator import GenerationError, generate
from .schema import ProjectValidationError, validate_project


def _signature(model: dict) -> dict:
    return {
        "bones": [
            {
                "uuid": bone["uuid"],
                "name": bone["name"],
                "parent": bone["parent"],
                "origin": bone["origin"],
                "pivot": bone["pivot"],
                "cubes": [
                    {
                        "uuid": cube["uuid"],
                        "from": cube["from"],
                        "to": cube["to"],
                        "localFrom": cube["localFrom"],
                        "size": cube["size"],
                        "uv": cube["uv"]
                    }
                    for cube in bone["cubes"]
                ]
            }
            for bone in model["bones"]
        ],
        "textureSize": model["textureSize"],
        "textureSha256": hashlib.sha256(bytes.fromhex(model["texture"]["pngBase64"]) if False else __import__("base64").b64decode(model["texture"]["pngBase64"])).hexdigest(),
        "animations": model["animations"]
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Minecraft Mod Studio V0.1 creature compiler")
    commands = parser.add_subparsers(dest="command", required=True)

    validate_cmd = commands.add_parser("validate", help="Validate a versioned creature project")
    validate_cmd.add_argument("--project", required=True, type=Path)

    generate_cmd = commands.add_parser("generate", help="Generate a Fabric Gradle project")
    generate_cmd.add_argument("--project", required=True, type=Path)
    generate_cmd.add_argument("--out", required=True, type=Path)

    roundtrip_cmd = commands.add_parser("roundtrip", help="Import and export a Blockbench .bbmodel")
    roundtrip_cmd.add_argument("--model", required=True, type=Path)
    roundtrip_cmd.add_argument("--out", required=True, type=Path)

    args = parser.parse_args()
    try:
        if args.command == "validate":
            project = json.loads(args.project.read_text(encoding="utf-8"))
            validate_project(project, args.project.resolve())
            print(json.dumps({"status": "VALID", "schemaVersion": project["schemaVersion"]}, indent=2))
        elif args.command == "generate":
            report = generate(args.project, args.out)
            print(json.dumps(report, indent=2))
        elif args.command == "roundtrip":
            original = import_bbmodel(args.model)
            export_bbmodel(original, args.out)
            restored = import_bbmodel(args.out)
            before, after = _signature(original), _signature(restored)
            if before != after:
                raise GenerationError("Blockbench round-trip changed supported geometry, hierarchy, UV or texture data")
            report = {
                "status": "ROUNDTRIP_VERIFIED",
                "source": str(args.model),
                "output": str(args.out),
                "bones": len(restored["bones"]),
                "cubes": sum(len(bone["cubes"]) for bone in restored["bones"]),
                "textureSize": restored["textureSize"],
                "geometryHierarchyUvTexture": "PRESERVED",
                "runtimeAnimationCompilation": "NOT_IN_V0_1"
            }
            print(json.dumps(report, indent=2))
        return 0
    except (OSError, json.JSONDecodeError, ProjectValidationError, GenerationError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

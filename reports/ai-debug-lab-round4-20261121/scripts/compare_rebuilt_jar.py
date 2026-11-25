"""Read-only audit of the corruption/rebuild experiment, including generated JAR metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jar(cache: Path, key: str, relative: str) -> dict:
    entry = cache / key
    jar = entry / relative
    if not jar.resolve().is_relative_to(entry.resolve()):
        raise ValueError("JAR path is outside the isolated cache entry")
    manifest_marker = read_json(entry / "cache-manifest.json")["files"][relative]
    with jar.open("rb") as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    with ZipFile(jar) as archive:
        members = {
            member.filename: {
                "zip_local_timestamp": list(member.date_time),
                "sha256_uncompressed": hashlib.sha256(archive.read(member)).hexdigest(),
                "crc32": f"{member.CRC:08x}",
                "size_uncompressed": member.file_size,
            }
            for member in archive.infolist()
        }
    return {
        "sha256": digest,
        "size": jar.stat().st_size,
        "manifest_sha256": manifest_marker["sha256"],
        "manifest_size": manifest_marker["size"],
        "members": members,
    }


def confirmed_launcher(report: dict) -> bool:
    return (
        report.get("outcome") == "passed"
        and bool(report.get("log_markers", {}).get("done"))
        and report.get("recipe_output") == "minecraft:emerald"
    )


def compare(raw: Path) -> dict:
    evidence = raw / "evidence"
    edit = read_json(evidence / "corrupt-edit.json")
    recovery = read_json(evidence / "corrupt-recovery" / "result.json")
    recheck = read_json(evidence / "corrupt-verified-hit" / "result.json")
    audit = read_json(evidence / "corrupt-recovery-cache-audit.json")
    restore = recovery["cache"]["restore"]
    publish = recovery["cache"]["publish"]
    key = recovery["cache"]["cache_key"]
    relative = edit["relative_file"]
    original = read_jar(raw / "cache" / "pair-1", key, relative)
    rebuilt = read_jar(raw / "cache" / "corrupt", key, relative)

    def member_hashes(report: dict) -> dict:
        return {name: value["sha256_uncompressed"] for name, value in report["members"].items()}

    def same_manifest(report: dict) -> bool:
        return report["sha256"] == report["manifest_sha256"] and report["size"] == report["manifest_size"]

    checks = {
        "deliberate_same_length_sha256_change": (
            edit["same_length"] and original["size"] == edit["size"]
            and original["sha256"] == edit["before_sha256"] != edit["after_sha256"]
        ),
        "invalid_cache_removed_because_hash_mismatched": (
            restore["status"] == "miss" and restore["reason"] == "invalid_cache_removed"
            and restore["detail"] == "file_inventory_or_hash_mismatch"
        ),
        "minecraft_started_and_republished": confirmed_launcher(recovery) and publish["status"] == "stored",
        "new_manifest_verified_without_leftover_staging": (
            audit["passed"] and not audit["staging_or_extra"]
            and same_manifest(original) and same_manifest(rebuilt)
            and rebuilt["sha256"] == edit["rebuilt_sha256"] != edit["after_sha256"]
        ),
        "rechecked_hit_ready": (
            confirmed_launcher(recheck) and recheck["cache"]["restore"]["status"] == "hit"
            and recheck["cache"]["publish"]["status"] == "not_needed"
        ),
    }
    return {
        "purpose": "Evaluate the runtime recovery independently of an erroneous exact original-JAR hash assertion",
        "cache_key": key,
        "relative_file": relative,
        "injected_sha256": edit["after_sha256"],
        "original": original,
        "rebuilt": rebuilt,
        "rebuilt_container_sha256_matches_original": rebuilt["sha256"] == original["sha256"],
        "uncompressed_zip_member_hashes_identical": member_hashes(original) == member_hashes(rebuilt),
        "zip_member_metadata_differs": original["members"] != rebuilt["members"],
        "checks": checks,
        "cache_corruption_recovery_passed": all(checks.values()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("raw", type=Path, help="Existing isolated run output with evidence/ and cache/")
    parser.add_argument("--output", type=Path, help="New JSON file; existing files are never overwritten")
    args = parser.parse_args()
    result = compare(args.raw)
    encoded = json.dumps(result, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(encoded)
    print(encoded, end="")
    return 0 if result["cache_corruption_recovery_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
"""Verify the committed report snapshot and basic path redaction."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "evidence-sha256.json"
PRIVATE_HOME = re.compile(rb"(?i)[A-Z]:[\/]+Users[\/]+[^\/\s]+")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))
    mismatches: list[str] = []
    private_path_files: list[str] = []
    for relative, expected_hash in expected.items():
        path = ROOT / relative
        if not path.is_file():
            mismatches.append(relative)
            continue
        if sha256(path) != expected_hash:
            mismatches.append(relative)
        data = path.read_bytes()
        if PRIVATE_HOME.search(data):
            private_path_files.append(relative)

    result = {
        "hash_manifest_entries": len(expected),
        "missing_or_hash_mismatch": mismatches,
        "unredacted_user_path_files": private_path_files,
        "passed": not mismatches and not private_path_files,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())

"""Package and verify the round 4 Windows evidence snapshot (Python 3.12+)."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


EVIDENCE_DIR = "evidence"
MANIFEST = "evidence-sha256.json"
TEXT_EXTENSIONS = {".json", ".jsonl", ".log", ".txt"}
PRIVATE_COMPONENTS = {
    ".fabric", "eula", "eula.txt", "libraries", "mods", "ops.json", "saves",
    "server.properties", "usercache.json", "versions", "whitelist.json", "world",
}
PRIVATE_HOME = re.compile(r"(?i)(?<![a-z0-9])[a-z]:[\\/]+Users[\\/]+[^\\/\s\"'<>;|:\[\]{}(),]+")
HS_PERF_DATA = re.compile(r"(?i)hsperfdata_[^\\/\s\"'<>;,]+")
PRIVATE_IP4 = re.compile(
    r"(?<![\w.])(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|"
    r"172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}|"
    r"(?:192\.168|169\.254)\.\d{1,3}\.\d{1,3})(?![\w.])"
)
SENSITIVE_VALUE = re.compile(
    r"(?im)(?:^|[\s{,])\"?(?:rcon[._-]?password|password|api[_-]?key|"
    r"access[_-]?token|secret|authorization)\"?\s*[:=]\s*\"?"
    r"(?!<REDACTED>|(?:false|true|null)\b)[^\"\s,}\]]+"
    r"|\b(?:gh[pousr]_[a-z0-9]{20,}|github_pat_[a-z0-9_]{20,})\b"
    r"|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"
    r"|https?://[^\s/\"':]+:[^\s/\"'@]+@"
)
HEX_SHA256 = re.compile(r"[0-9a-f]{64}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def lf_bytes(data: bytes) -> bytes:
    # Git can check out the same text with CRLF on Windows.
    return data.replace(b"\r\n", b"\n")


def path_is_link(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def relative_files(root: Path) -> dict[str, Path]:
    if path_is_link(root) or not root.is_dir():
        raise ValueError("evidence must be a regular directory")
    result: dict[str, Path] = {}
    for current, subdirectories, names in os.walk(root, followlinks=False):
        directory = Path(current)
        for name in subdirectories:
            if path_is_link(directory / name):
                raise ValueError("evidence contains a linked directory")
        for name in names:
            item = directory / name
            relative = item.relative_to(root).as_posix()
            if path_is_link(item) or not item.is_file():
                raise ValueError(f"evidence is not a regular file: {relative}")
            if item.suffix.lower() not in TEXT_EXTENSIONS:
                raise ValueError(f"unexpected evidence file type: {relative}")
            if any(
                component.casefold() in PRIVATE_COMPONENTS
                or component.casefold().startswith(("mms-ai-world-", "world_"))
                for component in item.relative_to(root).parts
            ):
                raise ValueError("runtime or personal files are outside the evidence scope")
            if PRIVATE_HOME.search(relative) or HS_PERF_DATA.search(relative):
                raise ValueError("private path fragment in an evidence filename")
            result[relative] = item
    if not result:
        raise ValueError("evidence directory is empty")
    return dict(sorted(result.items()))


def decode_log_line(line: bytes) -> str:
    try:
        return line.decode("utf-8-sig")
    except UnicodeDecodeError:
        return line.decode("gb18030")


def redact(data: bytes, relative: str) -> str:
    try:
        text = lf_bytes(data).decode("utf-8-sig")
    except UnicodeDecodeError:
        if not relative.endswith("/server.log"):
            raise
        # Localized Windows Fabric installer output may use code page 936.
        # The original bytes remain local; preserve the Chinese text in UTF-8.
        text = "\n".join(decode_log_line(line) for line in lf_bytes(data).split(b"\n"))
    text = PRIVATE_HOME.sub("<USER_HOME>", text)
    text = HS_PERF_DATA.sub("hsperfdata_<USER>", text)
    return PRIVATE_IP4.sub("<PRIVATE_IPV4>", text)


def privacy_findings(text: str) -> list[str]:
    findings = []
    if PRIVATE_HOME.search(text):
        findings.append("user-home-path")
    if HS_PERF_DATA.search(text.replace("hsperfdata_<USER>", "")):
        findings.append("java-temp-name")
    if PRIVATE_IP4.search(text):
        findings.append("private-ipv4-address")
    if SENSITIVE_VALUE.search(text):
        findings.append("possible-credential")
    return findings


def package(source: Path, report: Path) -> None:
    if path_is_link(source):
        raise ValueError("source evidence directory is a link")
    source = source.resolve()
    destination = report / EVIDENCE_DIR
    if source == report or source.is_relative_to(report) or report.is_relative_to(source):
        raise ValueError("use a separate local evidence directory")
    if destination.exists() or path_is_link(destination) or (report / MANIFEST).exists():
        raise ValueError("report already contains an evidence package")
    source_files = relative_files(source)
    report.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mms-report-package-", dir=report) as temporary:
        staged = Path(temporary) / EVIDENCE_DIR
        staged.mkdir()
        hashes = {}
        for relative, original in source_files.items():
            raw = original.read_bytes()
            clean = redact(raw, relative)
            findings = privacy_findings(clean)
            if findings:
                raise ValueError(f"privacy check failed in {relative}: {', '.join(findings)}")
            packaged = clean.encode("utf-8")
            output = staged / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(packaged)
            hashes[relative] = {
                "raw_local_sha256": sha256(raw),
                "packaged_sha256_lf": sha256(packaged),
                "bytes_changed_in_packaging": raw != packaged,
            }
        manifest = {
            "schema_version": 1,
            "hash_scope": "Paths relative to evidence/. Packaged hashes use LF line endings.",
            "files": hashes,
        }
        # Publish only after the whole source has passed privacy checks.
        pending = Path(temporary) / MANIFEST
        pending.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
        staged.rename(destination)
        pending.replace(report / MANIFEST)


def verify(report: Path) -> dict:
    manifest = json.loads((report / MANIFEST).read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported evidence manifest schema")
    expected = manifest.get("files")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("invalid or empty evidence manifest")
    actual = relative_files(report / EVIDENCE_DIR)
    missing = sorted(set(expected) - set(actual))
    additional = sorted(set(actual) - set(expected))
    mismatches = []
    private = {}
    for relative, path in actual.items():
        data = lf_bytes(path.read_bytes())
        receipt = expected.get(relative)
        if relative in expected and (
            not isinstance(receipt, dict)
            or HEX_SHA256.fullmatch(str(receipt.get("raw_local_sha256", ""))) is None
            or receipt.get("packaged_sha256_lf") != sha256(data)
        ):
            mismatches.append(relative)
        try:
            findings = privacy_findings(data.decode("utf-8"))
        except UnicodeDecodeError:
            findings = ["not-utf8-text"]
        if findings:
            private[relative] = findings
    return {
        "manifest_entries": len(expected),
        "missing": missing,
        "unlisted": additional,
        "hash_mismatch": mismatches,
        "privacy_findings": private,
        "passed": not (missing or additional or mismatches or private),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, metavar="RAW_EVIDENCE_DIR")
    parser.add_argument("--report-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    report = args.report_dir.resolve()
    try:
        if args.package is not None:
            package(args.package, report)
        result = verify(report)
    except (OSError, ValueError) as exc:
        result = {"passed": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

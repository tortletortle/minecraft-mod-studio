#!/usr/bin/env python3
"""Cross-check a UMPD report against a pinned local Modrinth corpus manifest."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


def digest_file(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_manifest_filename(value: str) -> bool:
    return bool(value) and value not in {".", ".."} and "/" not in value and "\\" not in value


def report_basename(value: str) -> str:
    normalized = value.replace("\\", "/")
    parts = PurePosixPath(normalized).parts
    if ".." in parts:
        return ""
    return PureWindowsPath(normalized).name if "\\" in value else PurePosixPath(normalized).name


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", type=Path, required=True, help="Local corpus root containing jars/ and manifest CSV")
    parser.add_argument("--minecraft-version", default="26.2")
    parser.add_argument("--loader", default="fabric")
    parser.add_argument("--manifest", type=Path, help="Override the local pinned manifest")
    parser.add_argument("--report", type=Path, help="Scanner JSON report; defaults under corpus/reports")
    parser.add_argument("--output-dir", type=Path, help="Cross-check outputs; defaults under corpus/reports/crosscheck")
    args = parser.parse_args()

    corpus_dir = args.corpus_dir.expanduser().resolve()
    jar_dir = corpus_dir / "jars"
    if not jar_dir.is_dir() or jar_dir.is_symlink():
        parser.error(f"JAR directory is missing or is a symlink: {jar_dir}")

    manifest_path = args.manifest
    if manifest_path is None:
        pinned = corpus_dir / f"manifest-{args.minecraft_version}-{args.loader}.csv"
        manifest_path = pinned if pinned.is_file() else corpus_dir / "manifest.csv"
    manifest_path = manifest_path.expanduser().resolve()
    if not manifest_path.is_file():
        parser.error(f"Manifest not found: {manifest_path}")

    report_path = args.report or (corpus_dir / "reports" / f"umpd-{args.minecraft_version}-{args.loader}.json")
    report_path = report_path.expanduser().resolve()
    if not report_path.is_file():
        parser.error(f"Scanner report not found: {report_path}")

    output_dir = args.output_dir or (corpus_dir / "reports" / "crosscheck")
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        report: dict[str, Any] = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        parser.error(f"Cannot read scanner report: {exc}")
    if report.get("reportVersion") != 1 or not isinstance(report.get("artifacts"), list):
        parser.error("Unsupported UMPD report contract; expected reportVersion=1 and an artifacts array")

    rows = load_manifest(manifest_path)
    report_input = str(report.get("inputDirectory", ""))
    try:
        report_input_matches = bool(report_input) and Path(report_input).expanduser().resolve() == jar_dir.resolve()
    except OSError:
        report_input_matches = False

    report_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for artifact in report["artifacts"]:
        if not isinstance(artifact, dict):
            continue
        name = report_basename(str(artifact.get("file", "")))
        if name:
            report_by_name[name].append(artifact)

    seen_manifest_names: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    protocol_artifact_hits: Counter[str] = Counter()
    protocol_evidence_hits: Counter[str] = Counter()
    protocol_callsite_artifacts: Counter[str] = Counter()
    loader_counts: Counter[str] = Counter()
    category_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    downloaded_rows = 0
    matched_rows = 0
    missing_rows = 0
    integrity_errors = 0
    scan_failures = 0
    manual_pending = 0

    for row in rows:
        manifest_status = (row.get("scanner_status") or "PENDING").strip()
        if manifest_status != "DOWNLOADED":
            status_counts[f"MANIFEST_{manifest_status}"] += 1
            continue
        downloaded_rows += 1
        local_name = (row.get("local_file_name") or "").strip()
        expected_sha = (row.get("sha256") or "").strip().lower()
        expected_size = (row.get("size_bytes") or "").strip()
        expected_sha512 = (row.get("sha512") or "").strip().lower()
        category = (row.get("category") or "unknown").strip()
        manual_status = (row.get("manual_audit_status") or "PENDING").strip()
        if manual_status == "PENDING":
            manual_pending += 1

        result: dict[str, Any] = {
            "project_name": row.get("project_name", ""),
            "modrinth_slug": row.get("modrinth_slug", ""),
            "category": category,
            "selected_minecraft_version": row.get("selected_minecraft_version", ""),
            "loader_target": row.get("loader_target", ""),
            "modrinth_version_id": row.get("modrinth_version_id", ""),
            "local_file_name": local_name,
            "expected_sha256": expected_sha,
            "local_sha256": "",
            "report_sha256": "",
            "size_bytes": "",
            "crosscheck_status": "PENDING",
            "scanner_status": "MISSING_FROM_REPORT",
            "protocols": "",
            "evidence_levels": "",
            "callsite_protocols": "",
            "mod_ids": "",
            "nested_jar_archives_scanned": 0,
            "warning_count": 0,
            "warning_overflow": 0,
            "manual_audit_status": manual_status,
        }

        if not safe_manifest_filename(local_name):
            result["crosscheck_status"] = "INVALID_MANIFEST_FILE_NAME"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        seen_manifest_names[local_name] += 1
        if seen_manifest_names[local_name] > 1:
            result["crosscheck_status"] = "DUPLICATE_MANIFEST_FILE_NAME"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue

        local_path = jar_dir / local_name
        if local_path.is_symlink() or not local_path.is_file():
            result["crosscheck_status"] = "LOCAL_FILE_MISSING_OR_SYMLINK"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        resolved_local = local_path.resolve()
        if resolved_local.parent != jar_dir.resolve():
            result["crosscheck_status"] = "LOCAL_PATH_ESCAPES_JAR_DIRECTORY"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue

        actual_size = local_path.stat().st_size
        actual_sha = digest_file(local_path, "sha256")
        result["size_bytes"] = actual_size
        result["local_sha256"] = actual_sha
        if not expected_sha:
            result["crosscheck_status"] = "MANIFEST_SHA256_MISSING"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        if actual_sha != expected_sha:
            result["crosscheck_status"] = "LOCAL_HASH_MISMATCH"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        if expected_size:
            try:
                parsed_expected_size = int(expected_size)
            except ValueError:
                result["crosscheck_status"] = "MANIFEST_SIZE_INVALID"
                integrity_errors += 1
                output_rows.append(result)
                status_counts[result["crosscheck_status"]] += 1
                continue
            if actual_size != parsed_expected_size:
                result["crosscheck_status"] = "LOCAL_SIZE_MISMATCH"
                integrity_errors += 1
                output_rows.append(result)
                status_counts[result["crosscheck_status"]] += 1
                continue
        if expected_sha512 and digest_file(local_path, "sha512") != expected_sha512:
            result["crosscheck_status"] = "LOCAL_SHA512_MISMATCH"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue

        matches = report_by_name.get(local_name, [])
        if not matches:
            result["crosscheck_status"] = "MISSING_FROM_REPORT"
            missing_rows += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        if len(matches) != 1:
            result["crosscheck_status"] = "AMBIGUOUS_REPORT_FILE_NAME"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue

        artifact = matches[0]
        result["scanner_status"] = artifact.get("status", "UNKNOWN")
        report_sha = str(artifact.get("sha256", "")).lower()
        result["report_sha256"] = report_sha
        if report_sha != expected_sha:
            result["crosscheck_status"] = "REPORT_HASH_MISMATCH"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        report_size = artifact.get("sizeBytes")
        if report_size is not None and int(report_size) != actual_size:
            result["crosscheck_status"] = "REPORT_SIZE_MISMATCH"
            integrity_errors += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue
        if artifact.get("status") != "SCANNED":
            result["crosscheck_status"] = "SCANNER_FAILED"
            scan_failures += 1
            output_rows.append(result)
            status_counts[result["crosscheck_status"]] += 1
            continue

        protocols = sorted(set(artifact.get("protocols") or []))
        evidence = artifact.get("protocolEvidence") or []
        evidence_levels = sorted({str(item.get("evidenceLevel")) for item in evidence if isinstance(item, dict) and item.get("evidenceLevel")})
        callsite_protocols = sorted({str(item.get("protocol")) for item in evidence if isinstance(item, dict) and item.get("evidenceLevel") == "BYTECODE_CALL_SITE" and item.get("protocol")})
        warnings = artifact.get("warnings") or []
        result.update({
            "crosscheck_status": "MATCHED",
            "protocols": ";".join(protocols),
            "evidence_levels": ";".join(evidence_levels),
            "callsite_protocols": ";".join(callsite_protocols),
            "mod_ids": ";".join(str(value) for value in artifact.get("modIds", []) if value is not None),
            "nested_jar_archives_scanned": artifact.get("nestedJarArchivesScanned", 0),
            "warning_count": len(warnings),
            "warning_overflow": artifact.get("warningOverflow", 0),
        })
        matched_rows += 1
        status_counts["MATCHED"] += 1
        loader_counts[str(artifact.get("loader", "UNKNOWN"))] += 1
        category_counts[category] += 1
        for protocol in protocols:
            protocol_artifact_hits[protocol] += 1
        for item in evidence:
            if isinstance(item, dict) and item.get("protocol"):
                protocol_evidence_hits[str(item["protocol"])] += 1
                if item.get("evidenceLevel") == "BYTECODE_CALL_SITE":
                    protocol_callsite_artifacts[str(item["protocol"])] += 1
        output_rows.append(result)

    manifest_names = {name for name, count in seen_manifest_names.items() if count == 1}
    unexpected_report_files = sorted(name for name in report_by_name if name not in manifest_names)
    fields = list(output_rows[0].keys()) if output_rows else [
        "project_name", "modrinth_slug", "category", "selected_minecraft_version", "loader_target",
        "modrinth_version_id", "local_file_name", "expected_sha256", "local_sha256", "report_sha256",
        "size_bytes", "crosscheck_status", "scanner_status", "protocols", "evidence_levels",
        "callsite_protocols", "mod_ids", "nested_jar_archives_scanned", "warning_count",
        "warning_overflow", "manual_audit_status"
    ]
    csv_path = output_dir / "cohort-crosscheck.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "reportVersion": report.get("reportVersion"),
        "scanner": report.get("scanner"),
        "createdAt": report.get("createdAt"),
        "manifest": str(manifest_path),
        "report": str(report_path),
        "reportInputDirectory": report_input,
        "reportInputDirectoryMatchesCorpusJars": report_input_matches,
        "minecraftVersion": args.minecraft_version,
        "loader": args.loader,
        "manifestDownloadedArtifacts": downloaded_rows,
        "matchedArtifacts": matched_rows,
        "missingFromReport": missing_rows,
        "integrityErrors": integrity_errors,
        "scannerFailures": scan_failures,
        "unexpectedReportArtifacts": unexpected_report_files,
        "manualAuditPending": manual_pending,
        "statusCounts": dict(sorted(status_counts.items())),
        "loaderCounts": dict(sorted(loader_counts.items())),
        "categoryCounts": dict(sorted(category_counts.items())),
        "protocolArtifactHits": dict(sorted(protocol_artifact_hits.items())),
        "protocolEvidenceRecords": dict(sorted(protocol_evidence_hits.items())),
        "protocolArtifactsWithDirectCallSites": dict(sorted(protocol_callsite_artifacts.items())),
        "reportSummary": report.get("summary", {}),
        "classMapping": report.get("classMapping", {}),
        "metricsWarning": "These are scanner observations only. Precision/recall require independent manual ground-truth labels and are not computed here.",
    }
    json_path = output_dir / "cohort-summary.json"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = [
        f"# UMPD cohort cross-check: {args.minecraft_version} / {args.loader}",
        "",
        f"- Manifest downloaded artifacts: {downloaded_rows}",
        f"- Matched report artifacts: {matched_rows}",
        f"- Missing from report: {missing_rows}",
        f"- Integrity errors: {integrity_errors}",
        f"- Scanner failures: {scan_failures}",
        f"- Unexpected report artifacts: {len(unexpected_report_files)}",
        f"- Manual audits still pending: {manual_pending}",
        f"- Report input directory matches corpus jars/: {report_input_matches}",
        "",
        "## Protocol observations (not precision/recall)",
        "",
        "| Protocol | Artifacts with signal | Evidence records | Artifacts with direct call sites |",
        "|---|---:|---:|---:|",
    ]
    for protocol in sorted(set(protocol_artifact_hits) | set(protocol_evidence_hits) | set(protocol_callsite_artifacts)):
        md.append(f"| {protocol} | {protocol_artifact_hits[protocol]} | {protocol_evidence_hits[protocol]} | {protocol_callsite_artifacts[protocol]} |")
    md.extend(["", "## Cross-check statuses", "", "| Status | Count |", "|---|---:|"])
    for status, count in sorted(status_counts.items()):
        md.append(f"| {status} | {count} |")
    md.extend([
        "",
        "These counts describe scanner output only. Do not interpret a protocol hit as confirmed usage until an independent manual audit labels the evidence.",
        "",
    ])
    md_path = output_dir / "cohort-summary.md"
    md_path.write_text("\n".join(md), encoding="utf-8")

    print(f"Cross-check CSV: {csv_path}")
    print(f"Summary JSON: {json_path}")
    print(f"Summary Markdown: {md_path}")
    print(f"Matched {matched_rows}/{downloaded_rows}; integrity errors={integrity_errors}; scan failures={scan_failures}.")
    return 1 if missing_rows or integrity_errors or scan_failures or not report_input_matches else 0


if __name__ == "__main__":
    raise SystemExit(main())

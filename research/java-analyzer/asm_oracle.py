#!/usr/bin/env python3
"""Differentially compare the bounded Python parser with a pinned ASM oracle.

The JAR is validated by analyze_jar first. Class bytes are streamed to a Java
process over stdin; no archive entry is extracted and no input class is loaded.
"""
from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
import zipfile
from collections import Counter
from pathlib import Path

from analyze_jar import AnalysisError, analyze_jar, parse_class

ASM_VERSION = "9.11.1"


def invocation_key(item: dict) -> tuple:
    return (
        item["callerMethod"],
        item["callerDescriptor"],
        item["opcode"],
        item["owner"],
        item["name"],
        item["descriptor"],
        bool(item.get("isInterface", item.get("kind") == "interface_method")),
    )


def method_key(item: dict) -> tuple:
    return item["name"], item["descriptor"], item["access"]


def _frame(path: str, class_bytes: bytes) -> bytes:
    encoded = path.encode("utf-8")
    if not encoded or len(encoded) > 4096:
        raise AnalysisError(f"invalid class path length: {path[:120]}")
    if not class_bytes or len(class_bytes) > 16 * 1024 * 1024:
        raise AnalysisError(f"class entry exceeds oracle limit: {path}")
    return struct.pack(">H", len(encoded)) + encoded + struct.pack(">I", len(class_bytes)) + class_bytes


def compare_jar(jar_path: Path, classpath: str, java: str = "java", timeout: int = 120) -> dict:
    jar_path = Path(jar_path)
    baseline = analyze_jar(jar_path)
    frames = bytearray()
    python_classes = {}
    class_paths = []

    with zipfile.ZipFile(jar_path, "r") as archive:
        for info in archive.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".class"):
                continue
            class_paths.append(info.filename)
            raw = archive.read(info)
            frames.extend(_frame(info.filename, raw))
            try:
                python_classes[info.filename] = parse_class(raw)
            except AnalysisError as exc:
                python_classes[info.filename] = {"error": str(exc)}

    command = [java, "-cp", classpath, "AsmOracle"]
    try:
        completed = subprocess.run(
            command, input=bytes(frames), capture_output=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise AnalysisError(f"ASM oracle timed out after {timeout}s") from exc
    except OSError as exc:
        raise AnalysisError(f"cannot start ASM oracle: {exc}") from exc

    if completed.returncode != 0:
        raise AnalysisError(
            "ASM oracle failed: " + completed.stderr.decode("utf-8", "replace")[-2000:]
        )

    lines = [line for line in completed.stdout.decode("utf-8", "replace").splitlines() if line.strip()]
    if len(lines) != len(class_paths):
        raise AnalysisError(
            f"oracle frame mismatch: sent {len(class_paths)} classes, received {len(lines)} records"
        )

    records = []
    totals = Counter()
    method_tp = method_fp = method_fn = 0
    invocation_tp = invocation_fp = invocation_fn = 0

    for path, line in zip(class_paths, lines):
        try:
            asm = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AnalysisError(f"invalid oracle JSON for {path}: {exc}") from exc

        python = python_classes[path]
        record = {"path": path, "asm": asm}
        if "error" in asm:
            totals["asmParseFailures"] += 1
            record["status"] = "ASM_PARSE_FAILED"
            record["python"] = {"error": python.get("error")} if "error" in python else {
                "className": python["name"]
            }
            records.append(record)
            continue
        if "error" in python:
            totals["pythonParseFailures"] += 1
            record["status"] = "PYTHON_PARSE_FAILED"
            record["python"] = python
            records.append(record)
            continue

        totals["classesParsedByBoth"] += 1
        class_identity_equal = (
            python["name"] == asm["className"]
            and python["majorVersion"] == asm["majorVersion"]
            and python["superclass"] == asm["superName"]
            and python["interfaces"] == asm["interfaces"]
        )
        if class_identity_equal:
            totals["classIdentityMatches"] += 1
        else:
            totals["classIdentityMismatches"] += 1

        py_methods = Counter(method_key(item) for item in python["methods"])
        asm_methods = Counter(method_key(item) for item in asm["methods"])
        common_methods = py_methods & asm_methods
        method_tp += sum(common_methods.values())
        method_fp += sum((asm_methods - py_methods).values())
        method_fn += sum((py_methods - asm_methods).values())
        method_equal = py_methods == asm_methods
        if method_equal:
            totals["methodSignatureMatches"] += 1
        else:
            totals["methodSignatureMismatches"] += 1

        py_invocations = Counter(invocation_key(item) for item in python["invocations"])
        asm_invocations = Counter(invocation_key(item) for item in asm["invocations"])
        invocation_truncated = bool(
            python.get("invocationsTruncated") or asm.get("invocationsTruncated")
        )
        invocation_equal = None
        if invocation_truncated:
            totals["invocationComparisonsSkipped"] += 1
        else:
            common_invocations = py_invocations & asm_invocations
            invocation_tp += sum(common_invocations.values())
            invocation_fp += sum((asm_invocations - py_invocations).values())
            invocation_fn += sum((py_invocations - asm_invocations).values())
            invocation_equal = py_invocations == asm_invocations
            if invocation_equal:
                totals["invocationMatches"] += 1
            else:
                totals["invocationMismatches"] += 1

        invokedynamic_equal = python["invokedynamicCount"] == asm["invokedynamicCount"]
        if invokedynamic_equal:
            totals["invokedynamicMatches"] += 1
        else:
            totals["invokedynamicMismatches"] += 1

        record.update({
            "status": "COMPARED",
            "classIdentityEqual": class_identity_equal,
            "methodSignaturesEqual": method_equal,
            "invocationsEqual": invocation_equal,
            "invocationsTruncated": invocation_truncated,
            "pythonInvokedynamicCount": python["invokedynamicCount"],
            "asmInvokedynamicCount": asm["invokedynamicCount"],
            "invokedynamicEqual": invokedynamic_equal,
            "asmMixinTargets": asm.get("mixinTargetClasses", []),
            "python": {
                "className": python["name"],
                "majorVersion": python["majorVersion"],
                "superclass": python["superclass"],
                "interfaces": python["interfaces"],
            },
        })
        records.append(record)

    asm_by_name = {
        item["asm"]["className"]: item
        for item in records
        if isinstance(item.get("asm"), dict) and not item["asm"].get("error")
    }
    mixin_results = []
    for config in baseline.get("mixins", []):
        enriched = dict(config)
        discovered_targets = set()
        unresolved_classes = []
        class_evidence = []
        for mixin_class in config.get("mixinClasses", []):
            internal_name = mixin_class.replace(".", "/")
            observed = asm_by_name.get(internal_name)
            if observed is None:
                unresolved_classes.append(mixin_class)
                class_evidence.append({
                    "mixinClass": mixin_class,
                    "annotationPresent": None,
                    "targetClasses": [],
                    "status": "CLASS_NOT_FOUND_IN_ANALYSIS",
                })
                continue
            asm_class = observed["asm"]
            if not asm_class.get("isMixin"):
                unresolved_classes.append(mixin_class)
                class_evidence.append({
                    "mixinClass": mixin_class,
                    "classEntryPath": observed["path"],
                    "annotationPresent": False,
                    "targetClasses": [],
                    "status": "MIXIN_ANNOTATION_NOT_FOUND",
                })
                continue
            targets = asm_class.get("mixinTargetClasses", [])
            discovered_targets.update(targets)
            class_evidence.append({
                "mixinClass": mixin_class,
                "classEntryPath": observed["path"],
                "annotationPresent": True,
                "targetClasses": targets,
                "status": "TARGETS_FOUND" if targets else "ANNOTATION_HAS_NO_TARGETS",
            })
        if unresolved_classes:
            target_status = "PARTIAL" if discovered_targets else "UNRESOLVED"
        elif discovered_targets:
            target_status = "COMPLETE"
        else:
            target_status = "NO_TARGETS_FOUND"
        enriched["targetClasses"] = sorted(discovered_targets)
        enriched["targetDiscoveryStatus"] = target_status
        enriched["unresolvedMixinClasses"] = unresolved_classes
        enriched["mixinClassEvidence"] = class_evidence
        mixin_results.append(enriched)

    compared = totals["classesParsedByBoth"]
    method_precision = method_tp / (method_tp + method_fp) if method_tp + method_fp else 1.0
    method_recall = method_tp / (method_tp + method_fn) if method_tp + method_fn else 1.0
    invocation_precision = (
        invocation_tp / (invocation_tp + invocation_fp) if invocation_tp + invocation_fp else 1.0
    )
    invocation_recall = (
        invocation_tp / (invocation_tp + invocation_fn) if invocation_tp + invocation_fn else 1.0
    )
    passed = (
        totals["asmParseFailures"] == 0
        and totals["pythonParseFailures"] == 0
        and totals["classIdentityMismatches"] == 0
        and totals["methodSignatureMismatches"] == 0
        and totals["invocationMismatches"] == 0
        and totals["invokedynamicMismatches"] == 0
        and totals["invocationComparisonsSkipped"] == 0
        and compared == len(class_paths)
    )

    return {
        "oracle": {"name": "OW2 ASM", "version": ASM_VERSION},
        "input": baseline["input"],
        "summary": {
            "classEntries": len(class_paths),
            "classesParsedByBoth": compared,
            **dict(totals),
            "methodSignaturePrecision": method_precision,
            "methodSignatureRecall": method_recall,
            "invocationPrecision": invocation_precision,
            "invocationRecall": invocation_recall,
            "passed": passed,
            "mixinConfigsAnalyzed": len(mixin_results),
            "mixinConfigsWithTargets": sum(1 for item in mixin_results if item["targetClasses"]),
        },
        "mixins": mixin_results,
        "classes": records,
        "limitations": [
            "ASM is used as an independent class-file parser, not as proof of JVM verification or runtime behavior.",
            "No class from the input JAR is defined, initialized, loaded through a class loader, or executed.",
            "Invocation comparison is skipped for classes whose 500-sample cap is exceeded.",
            "ASM Mixin target extraction reads the CLASS-retained @Mixin annotation; it does not evaluate Mixin plugins or refmap remapping.",
        ],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("jar", type=Path)
    parser.add_argument("--classpath", required=True, help="ASM jar plus compiled AsmOracle classes")
    parser.add_argument("--java", default="java")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("-o", "--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = compare_jar(args.jar, args.classpath, args.java, args.timeout)
    except (AnalysisError, OSError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

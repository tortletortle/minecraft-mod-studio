"""Build a provenance-first ModIR evidence graph from analyzer reports.

This module never generates target code and never assigns a migration percentage.
"""
from __future__ import annotations

import re
from typing import Any


def build_modir(static_report: dict[str, Any], asm_report: dict[str, Any] | None = None) -> dict[str, Any]:
    artifact = static_report.get("input")
    if not isinstance(artifact, dict):
        raise ValueError("static report must contain an input object")
    digest = artifact.get("sha256")
    if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
        raise ValueError("static report must contain a lowercase hexadecimal SHA-256 input identity")

    if asm_report is not None:
        if not isinstance(asm_report, dict) or not isinstance(asm_report.get("input"), dict):
            raise ValueError("ASM report must contain an input identity")
        asm_digest = asm_report["input"].get("sha256")
        if asm_digest != digest:
            raise ValueError("ASM report input SHA-256 does not match static report")

    evidence: list[dict[str, Any]] = []
    sequence = 0

    def add_evidence(
        kind: str,
        entry_path: str | None,
        detail: dict[str, Any],
        verification: str = "not_run",
        class_name: str | None = None,
    ) -> str:
        nonlocal sequence
        sequence += 1
        evidence_id = f"ev-{sequence:06d}"
        source: dict[str, Any] = {"artifactSha256": digest}
        if entry_path is not None:
            source["entryPath"] = entry_path
        if class_name is not None:
            source["className"] = class_name
        evidence.append({
            "id": evidence_id,
            "kind": kind,
            "source": source,
            "origin": "direct",
            "verification": verification,
            "confidence": "high",
            "detail": detail,
        })
        return evidence_id

    metadata = static_report.get("metadata", {})
    mods = []
    descriptor_by_loader = {
        "fabric": "fabric.mod.json",
        "quilt": "quilt.mod.json",
        "forge": "META-INF/mods.toml",
        "neoforge": "META-INF/neoforge.mods.toml",
    }
    for mod in metadata.get("mods", []):
        evidence_id = add_evidence(
            "metadata",
            descriptor_by_loader.get(mod.get("loader")),
            {"fact": "mod_descriptor", "value": mod},
        )
        mods.append({**mod, "evidenceId": evidence_id})

    dependencies = []
    source_mod_id = mods[0].get("id") if mods else None
    for index, dependency in enumerate(metadata.get("dependencies", []), start=1):
        evidence_id = add_evidence(
            "metadata",
            dependency.get("source") if isinstance(dependency.get("source"), str) else None,
            {"fact": "dependency_declaration", "value": dependency},
        )
        dependencies.append({
            "id": f"dep-{index:05d}",
            "sourceModId": (
                dependency.get("declaredFor")
                if isinstance(dependency.get("declaredFor"), str)
                else source_mod_id
            ),
            "targetModId": dependency.get("id"),
            "constraint": dependency.get("constraint"),
            "relationKind": dependency.get("kind", "unknown"),
            "sourcePath": dependency.get("source"),
            "evidenceId": evidence_id,
        })

    entrypoints = []
    for index, entrypoint in enumerate(metadata.get("entrypoints", []), start=1):
        evidence_id = add_evidence(
            "metadata",
            entrypoint.get("source"),
            {"fact": "entrypoint_declaration", "value": entrypoint},
        )
        entrypoints.append({
            "id": f"entrypoint-{index:05d}",
            "loader": entrypoint.get("loader"),
            "key": entrypoint.get("key"),
            "adapter": entrypoint.get("adapter", "default"),
            "value": entrypoint.get("value"),
            "sourcePath": entrypoint.get("source"),
            "evidenceId": evidence_id,
        })

    asm_classes = {}
    if asm_report is not None:
        asm_classes = {
            item.get("path"): item
            for item in asm_report.get("classes", [])
            if item.get("path")
        }

    classes = []
    for item in static_report.get("bytecode", {}).get("classes", []):
        asm_item = asm_classes.get(item.get("path"), {})
        asm = asm_item.get("asm", {}) if isinstance(asm_item, dict) else {}
        cross_checked = (
            asm_item.get("status") == "COMPARED"
            and asm_item.get("classIdentityEqual") is True
            and asm_item.get("methodSignaturesEqual") is True
            and asm_item.get("invocationsEqual") is True
            and asm_item.get("invokedynamicEqual") is True
            and asm_item.get("invocationsTruncated") is False
        )
        evidence_id = add_evidence(
            "class_header",
            item.get("path"),
            {
                "className": item.get("name"),
                "majorVersion": item.get("majorVersion"),
                "superclass": item.get("superclass"),
                "interfaces": item.get("interfaces", []),
            },
            verification="parser_cross_checked" if cross_checked else "not_run",
            class_name=item.get("name"),
        )
        classes.append({
            "internalName": item.get("name"),
            "entryPath": item.get("path"),
            "majorVersion": item.get("majorVersion"),
            "superName": item.get("superclass"),
            "interfaces": item.get("interfaces", []),
            "methodCount": item.get("methodCount"),
            "invocationCount": item.get("invocationCount"),
            "evidenceId": evidence_id,
        })

    mixin_source = (
        asm_report.get("mixins", [])
        if asm_report is not None
        else static_report.get("mixins", [])
    )
    mixin_configs = []
    for config in mixin_source:
        config_evidence = add_evidence(
            "metadata",
            config.get("path"),
            {
                "fact": "mixin_config",
                "package": config.get("package"),
                "environment": config.get("environment"),
                "plugin": config.get("plugin"),
                "refmap": config.get("refmap"),
            },
        )
        annotation_evidence = []
        for class_fact in config.get("mixinClassEvidence", []):
            annotation_evidence.append(add_evidence(
                "annotation",
                class_fact.get("classEntryPath"),
                {
                    "mixinClass": class_fact.get("mixinClass"),
                    "annotationPresent": class_fact.get("annotationPresent"),
                    "targetClasses": class_fact.get("targetClasses", []),
                    "status": class_fact.get("status"),
                    "parser": "ASM 9.11.1",
                },
                class_name=class_fact.get("mixinClass"),
            ))
        mixin_configs.append({
            "path": config.get("path"),
            "package": config.get("package"),
            "environment": config.get("environment", "*"),
            "mixinClasses": config.get("mixinClasses", []),
            "targetClasses": config.get("targetClasses", []),
            "targetDiscoveryStatus": config.get("targetDiscoveryStatus", "NOT_ANALYZED"),
            "unresolvedMixinClasses": config.get("unresolvedMixinClasses", []),
            "plugin": config.get("plugin"),
            "refmap": config.get("refmap"),
            "evidenceId": config_evidence,
            "annotationEvidenceIds": annotation_evidence,
        })

    resources = []
    for item in static_report.get("resources", {}).get("inventory", []):
        evidence_id = add_evidence(
            "resource_path",
            item.get("path"),
            {"category": item.get("category")},
        )
        resources.append({
            "path": item.get("path"),
            "category": item.get("category"),
            "evidenceId": evidence_id,
        })

    summary = static_report.get("summary", {})
    asm_summary = asm_report.get("summary", {}) if asm_report is not None else {}
    return {
        "schemaVersion": "0.1.0",
        "artifact": {
            "sha256": digest,
            "fileName": artifact.get("fileName"),
            "sizeBytes": artifact.get("sizeBytes"),
            "format": "jar",
        },
        "sourceProfile": {
            "loaderCandidates": metadata.get("loaderCandidates", []),
            "modIds": [item.get("id") for item in mods if item.get("id")],
            "classMajorVersions": summary.get("classMajorVersions", {}),
            "analyzerVersion": static_report.get("analyzer", {}).get("version"),
            "sourceReportSchemaVersion": static_report.get("schemaVersion"),
        },
        "entities": {
            "mods": mods,
            "dependencies": dependencies,
            "entrypoints": entrypoints,
            "classes": classes,
            "mixinConfigs": mixin_configs,
            "resources": resources,
        },
        "coverage": {
            "classEntries": summary.get("classEntries", 0),
            "parsedClassEntries": len(classes),
            "resourceEntries": static_report.get("resources", {}).get("count", 0),
            "resourceInventoryTruncated": static_report.get("resources", {}).get("inventoryTruncated", False),
            "asmDifferentialRun": asm_report is not None,
            "asmDifferentialPassed": asm_summary.get("passed", False),
        },
        "evidence": evidence,
        "targetProfile": None,
        "mappings": [],
        "migrationAssessment": {
            "overallStatus": "UNASSESSED",
            "reasonCodes": [
                "TARGET_PROFILE_NOT_PINNED",
                "TARGET_CAPABILITY_MAPPING_NOT_PERFORMED",
                "RUNTIME_BEHAVIOR_NOT_VERIFIED",
            ],
        },
    }

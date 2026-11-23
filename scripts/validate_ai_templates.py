#!/usr/bin/env python3
"""Validate the MMS AI template catalog using only the Python standard library."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "docs" / "ai-templates" / "ai-templates-v1.json"
SCHEMA_PATH = ROOT / "docs" / "schemas" / "mms-ai-template-v1.schema.json"

PLACEHOLDER = re.compile(r"\\{\\{([a-z][a-z0-9_]*)\\}\\}")
FORBIDDEN_CAPABILITIES = {
    "command.execute",
    "command.dispatch",
    "world.write_unbounded",
    "code.exec",
    "shell.exec",
}


def fail(message: str) -> None:
    raise ValueError(message)


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    if catalog.get("schemaVersion") != "1.0.0":
        fail("unsupported catalog schemaVersion")
    if catalog.get("libraryId") != "mms.ai-template-library":
        fail("unexpected libraryId")
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        fail("schema must declare JSON Schema 2020-12")
    version_pattern = schema.get("properties", {}).get("templates", {}).get("items", {}).get("properties", {}).get("version", {}).get("pattern")
    if version_pattern != r"^[0-9]+\\.[0-9]+\\.[0-9]+$":
        fail("schema version pattern must validate semantic versions")

    policy = catalog.get("defaultPolicy", {})
    expected_policy = {
        "unknownCapability": "deny",
        "unknownCommand": "deny",
        "genericCommandExecution": "disabled",
        "modManifestTrust": "untrusted_descriptive_data_only",
        "mutationRequiresExplicitApproval": True,
        "mutationRequiresPreview": True,
        "mutationRequiresPostActionReadback": True,
        "stopOnStateDivergence": True,
        "claimRollbackOnlyWhenInverseExists": True,
        "separateObservedFactsFromInferences": True,
    }
    for key, expected in expected_policy.items():
        if policy.get(key) != expected:
            fail(f"defaultPolicy.{key} must be {expected!r}")

    templates = catalog.get("templates")
    if not isinstance(templates, list) or not 1 <= len(templates) <= 32:
        fail("templates must be an array with 1..32 entries")

    ids = [item.get("id") for item in templates]
    if len(ids) != len(set(ids)):
        fail("template IDs must be unique")

    for template in templates:
        tid = template.get("id", "<missing-id>")
        if template.get("mode") not in {"read_only", "plan_only", "approval_gated"}:
            fail(f"{tid}: invalid mode")
        if not template.get("triggerExamples"):
            fail(f"{tid}: at least one trigger example is required")
        if not template.get("resultContract", {}).get("requiredSections"):
            fail(f"{tid}: resultContract.requiredSections is required")
        if not template.get("guardrails"):
            fail(f"{tid}: guardrails are required")

        variables = template.get("inputVariables", [])
        variable_names = [v.get("name") for v in variables]
        if len(variable_names) != len(set(variable_names)):
            fail(f"{tid}: input variable names must be unique")

        used = set(PLACEHOLDER.findall(template.get("promptTemplate", "")))
        undeclared = used - set(variable_names)
        if undeclared:
            fail(f"{tid}: undeclared prompt placeholders: {sorted(undeclared)}")

        required = set(template.get("requiredCapabilities", []))
        optional = set(template.get("optionalCapabilities", []))
        if required & optional:
            fail(f"{tid}: required and optional capabilities overlap")
        capabilities = required | optional
        forbidden = capabilities & FORBIDDEN_CAPABILITIES
        if forbidden:
            fail(f"{tid}: forbidden capabilities: {sorted(forbidden)}")

        step_ids = [step.get("id") for step in template.get("workflow", [])]
        if len(step_ids) != len(set(step_ids)):
            fail(f"{tid}: workflow step IDs must be unique")

        for step in template.get("workflow", []):
            if step.get("operationClass") == "mutation":
                if step.get("approval") != "explicit_user_approval":
                    fail(f"{tid}/{step.get('id')}: mutation step must require explicit approval")
                if template["mode"] != "approval_gated":
                    fail(f"{tid}: mutation steps require approval_gated mode")
        if template["mode"] in {"read_only", "plan_only"}:
            if any(step.get("operationClass") == "mutation" for step in template.get("workflow", [])):
                fail(f"{tid}: {template['mode']} template cannot contain mutation steps")

    by_id = {item["id"]: item for item in templates}
    for tid in ("modification-planner", "world-builder"):
        if by_id.get(tid, {}).get("mode") != "plan_only":
            fail(f"{tid} must remain plan_only")
    if by_id.get("entity-workbench", {}).get("mode") != "approval_gated":
        fail("entity-workbench must remain approval_gated")

    print(f"PASS: {len(templates)} templates; unique IDs; prompt variables; workflow approvals; capability denylist; safety policy.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)

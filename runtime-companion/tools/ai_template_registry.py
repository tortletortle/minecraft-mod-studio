#!/usr/bin/env python3
"""Versioned AI template registry, lexical task router, and capability adapter."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


MAX_CATALOG_BYTES = 256 * 1024
TEMPLATE_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]{2,47}$")
SEMVER_PATTERN = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
PLACEHOLDER_PATTERN = re.compile(r"\{\{([a-z][a-z0-9_]*)\}\}")
FORBIDDEN_CAPABILITIES = {
    "command.execute",
    "command.dispatch",
    "world.write_unbounded",
    "code.exec",
    "shell.exec",
    "file.write_arbitrary",
    "java.exec",
}
EXPECTED_POLICY = {
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
ROOT_KEYS = {
    "schemaVersion", "libraryId", "libraryName", "product", "defaultPolicy", "templates"
}
TEMPLATE_KEYS = {
    "id", "version", "name", "category", "description", "triggerExamples",
    "routingKeywords", "mode", "inputVariables", "requiredCapabilities",
    "optionalCapabilities", "workflow", "promptTemplate", "resultContract", "guardrails",
}
INPUT_KEYS = {"name", "type", "required", "description", "default", "enum", "minimum", "maximum"}
WORKFLOW_KEYS = {"id", "operationClass", "approval", "instruction"}
MODES = {"read_only", "plan_only", "approval_gated"}
OPERATION_CLASSES = {"read", "analysis", "plan", "mutation"}
APPROVALS = {"not_required", "explicit_user_approval"}

DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "ai-templates"
    / "ai-templates-v1.json"
)

# A logical capability is available only when its exact bridge operation is
# advertised by the currently running Fabric companion. No name-based guessing.
RUNTIME_CAPABILITY_BINDINGS: dict[str, dict[str, Any]] = {
    "command.catalog.search": {
        "bridge_commands": ["command_catalog"],
        "mcp_tool": "mms_search_commands",
        "approval_required": False,
    },
    "command.inspect": {
        "bridge_commands": ["command_inspect"],
        "mcp_tool": "mms_inspect_command",
        "approval_required": False,
    },
    "command.syntax.validate": {
        "bridge_commands": ["command_validate"],
        "mcp_tool": "mms_validate_command",
        "approval_required": False,
    },
    "runtime.status.read": {
        "bridge_commands": ["status"],
        "mcp_tool": "mms_game_status",
        "approval_required": False,
    },
    "runtime.snapshot.read": {
        "bridge_commands": ["scene_snapshot"],
        "mcp_tool": "mms_get_scene_snapshot",
        "approval_required": False,
    },
    "runtime.screenshot.capture": {
        "bridge_commands": ["capture_screenshot"],
        "mcp_tool": "mms_capture_screenshot",
        "approval_required": False,
    },
    "entity.inspect": {
        "bridge_commands": ["inspect_entity"],
        "mcp_tool": "mms_inspect_entity",
        "approval_required": False,
    },
    "entity.attribute.read": {
        "bridge_commands": ["entity_attributes"],
        "mcp_tool": "mms_read_entity_attributes",
        "approval_required": False,
    },
    "entity.attribute.write_bounded": {
        "bridge_commands": ["set_entity_attribute"],
        "mcp_tool": "mms_set_entity_attribute",
        "approval_required": True,
    },
    "entity.attribute.restore": {
        "bridge_commands": ["reset_entity_attributes"],
        "mcp_tool": "mms_reset_entity_attributes",
        "approval_required": True,
    },
}

LOCAL_CAPABILITIES = {
    "template.registry.select": {
        "status": "available",
        "source": "local_template_registry",
        "mcp_tool": "mms_get_ai_template",
    },
}
AGENT_CAPABILITIES = {
    "evidence.report": {
        "status": "agent_responsibility",
        "source": "agent_reasoning",
        "mcp_tool": None,
    },
}
UNIMPLEMENTED_CAPABILITY_REASONS = {
    "mod.inventory.read": "No installed-mod inventory adapter is registered in this MCP server.",
    "mod.metadata.read": "No mod metadata inspection adapter is registered in this MCP server.",
    "mod.resources.inspect": "No resource archive inspection adapter is registered in this MCP server.",
    "mod.dependencies.inspect": "No dependency graph inspection adapter is registered in this MCP server.",
    "mod.schema.inspect": "No mod schema inspection adapter is registered in this MCP server.",
    "patch.diff.preview": "No patch diff engine is connected; this template can produce a textual plan only.",
    "patch.rollback.plan": "No patch snapshot or inverse-operation adapter is connected.",
    "world.region.inspect": "The companion can inspect individual nearby blocks, not bounded world regions.",
    "world.blueprint.create": "No persisted world-blueprint creation adapter is connected.",
    "world.blueprint.preview": "No in-game blueprint preview adapter is connected.",
    "diagnostics.logs.read": "No game-log retrieval adapter is connected.",
}


class TemplateRegistryError(ValueError):
    """Raised when the trusted, bundled template catalog is invalid."""


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TemplateRegistryError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TemplateRegistryError(message)


def validate_catalog(catalog: Any) -> None:
    _require(isinstance(catalog, dict), "Catalog root must be an object.")
    _require(set(catalog) == ROOT_KEYS, "Catalog has missing or unexpected root fields.")
    _require(catalog.get("schemaVersion") == "1.0.0", "Unsupported catalog schemaVersion.")
    _require(catalog.get("libraryId") == "mms.ai-template-library", "Unexpected libraryId.")
    _require(
        isinstance(catalog.get("libraryName"), str) and 1 <= len(catalog["libraryName"]) <= 120,
        "Invalid libraryName.",
    )

    product = catalog.get("product")
    _require(isinstance(product, dict), "product must be an object.")
    _require(
        product.get("minecraftEdition") == "Java"
        and product.get("modLoader") == "Fabric"
        and isinstance(product.get("minecraftVersion"), str),
        "Unsupported product identity.",
    )

    policy = catalog.get("defaultPolicy")
    _require(isinstance(policy, dict), "defaultPolicy must be an object.")
    for key, expected in EXPECTED_POLICY.items():
        _require(policy.get(key) == expected, f"Unsafe defaultPolicy value: {key}.")

    templates = catalog.get("templates")
    _require(isinstance(templates, list) and 1 <= len(templates) <= 32, "templates must contain 1–32 entries.")
    identifiers: set[str] = set()

    for template in templates:
        _require(isinstance(template, dict), "Each template must be an object.")
        _require(set(template) == TEMPLATE_KEYS, "Template has missing or unexpected fields.")
        template_id = template.get("id")
        _require(
            isinstance(template_id, str) and TEMPLATE_ID_PATTERN.fullmatch(template_id) is not None,
            "Invalid template ID.",
        )
        _require(template_id not in identifiers, f"Duplicate template ID: {template_id}.")
        identifiers.add(template_id)

        version = template.get("version")
        _require(isinstance(version, str) and SEMVER_PATTERN.fullmatch(version) is not None,
                 f"{template_id}: invalid semantic version.")
        _require(template.get("mode") in MODES, f"{template_id}: invalid operating mode.")
        for field in ("name", "category", "description", "promptTemplate"):
            _require(isinstance(template.get(field), str) and bool(template[field].strip()),
                     f"{template_id}: {field} must be a non-empty string.")
        _require(len(template["promptTemplate"]) <= 5000, f"{template_id}: promptTemplate is too long.")

        examples = template.get("triggerExamples")
        keywords = template.get("routingKeywords")
        _require(
            isinstance(examples, list) and 1 <= len(examples) <= 12
            and all(isinstance(item, str) and item.strip() for item in examples),
            f"{template_id}: invalid triggerExamples.",
        )
        _require(
            isinstance(keywords, list) and 3 <= len(keywords) <= 32
            and len(set(keywords)) == len(keywords)
            and all(isinstance(item, str) and 1 <= len(item) <= 48 for item in keywords),
            f"{template_id}: invalid routingKeywords.",
        )

        variables = template.get("inputVariables")
        _require(isinstance(variables, list) and len(variables) <= 16,
                 f"{template_id}: invalid inputVariables.")
        variable_names: set[str] = set()
        for variable in variables:
            _require(isinstance(variable, dict) and set(variable).issubset(INPUT_KEYS),
                     f"{template_id}: invalid input variable object.")
            _require(
                {"name", "type", "required", "description"}.issubset(variable),
                f"{template_id}: input variable is missing required fields.",
            )
            name = variable.get("name")
            _require(
                isinstance(name, str) and re.fullmatch(r"^[a-z][a-z0-9_]{1,47}$", name) is not None,
                f"{template_id}: invalid input variable name.",
            )
            _require(name not in variable_names, f"{template_id}: duplicate input variable {name}.")
            variable_names.add(name)
            _require(variable.get("type") in {"string", "boolean", "integer"},
                     f"{template_id}: unsupported input variable type.")
            _require(type(variable.get("required")) is bool,
                     f"{template_id}: input variable required must be boolean.")
            _require(isinstance(variable.get("description"), str),
                     f"{template_id}: input variable description must be text.")

        placeholders = set(PLACEHOLDER_PATTERN.findall(template["promptTemplate"]))
        _require(
            placeholders.issubset(variable_names),
            f"{template_id}: undeclared prompt placeholders: {sorted(placeholders - variable_names)}.",
        )

        required = template.get("requiredCapabilities")
        optional = template.get("optionalCapabilities")
        _require(isinstance(required, list) and isinstance(optional, list),
                 f"{template_id}: capability declarations must be arrays.")
        _require(
            all(isinstance(item, str) and item for item in required + optional),
            f"{template_id}: capability names must be non-empty strings.",
        )
        _require(len(set(required)) == len(required), f"{template_id}: duplicate required capability.")
        _require(len(set(optional)) == len(optional), f"{template_id}: duplicate optional capability.")
        _require(not (set(required) & set(optional)), f"{template_id}: required/optional capabilities overlap.")
        _require(
            not (set(required) | set(optional)) & FORBIDDEN_CAPABILITIES,
            f"{template_id}: forbidden capability declared.",
        )

        workflow = template.get("workflow")
        _require(isinstance(workflow, list) and 1 <= len(workflow) <= 16,
                 f"{template_id}: invalid workflow.")
        step_ids: set[str] = set()
        for step in workflow:
            _require(isinstance(step, dict) and set(step) == WORKFLOW_KEYS,
                     f"{template_id}: invalid workflow step.")
            step_id = step.get("id")
            _require(isinstance(step_id, str) and step_id and step_id not in step_ids,
                     f"{template_id}: invalid or duplicate workflow step ID.")
            step_ids.add(step_id)
            _require(step.get("operationClass") in OPERATION_CLASSES,
                     f"{template_id}/{step_id}: invalid operation class.")
            _require(step.get("approval") in APPROVALS,
                     f"{template_id}/{step_id}: invalid approval requirement.")
            _require(isinstance(step.get("instruction"), str) and step["instruction"].strip(),
                     f"{template_id}/{step_id}: instruction must be non-empty.")
            if step["operationClass"] == "mutation":
                _require(
                    template["mode"] == "approval_gated"
                    and step["approval"] == "explicit_user_approval",
                    f"{template_id}/{step_id}: mutation must be approval-gated.",
                )
        if template["mode"] in {"read_only", "plan_only"}:
            _require(
                all(step["operationClass"] != "mutation" for step in workflow),
                f"{template_id}: read-only/plan-only template cannot mutate.",
            )

        contract = template.get("resultContract")
        _require(
            isinstance(contract, dict)
            and isinstance(contract.get("requiredSections"), list)
            and bool(contract["requiredSections"]),
            f"{template_id}: resultContract.requiredSections is required.",
        )
        guardrails = template.get("guardrails")
        _require(
            isinstance(guardrails, list) and 1 <= len(guardrails) <= 16
            and all(isinstance(item, str) and item.strip() for item in guardrails),
            f"{template_id}: invalid guardrails.",
        )

    by_id = {item["id"]: item for item in templates}
    for template_id in ("modification-planner", "world-builder"):
        _require(by_id.get(template_id, {}).get("mode") == "plan_only",
                 f"{template_id} must remain plan_only.")
    _require(by_id.get("entity-workbench", {}).get("mode") == "approval_gated",
             "entity-workbench must remain approval_gated.")


def _normalize(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _terms(value: str) -> set[str]:
    folded = value.casefold()
    found = set(re.findall(r"[a-z0-9_.:-]+", folded))
    for segment in re.findall(r"[\u4e00-\u9fff]+", folded):
        if len(segment) == 1:
            found.add(segment)
        else:
            found.update(segment[index:index + 2] for index in range(len(segment) - 1))
            if len(segment) <= 6:
                found.add(segment)
    return found


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


class TemplateRegistry:
    """Load a fixed, bundled catalog; no caller-controlled runtime file path."""

    def __init__(self, catalog_path: Path | None = None):
        self.catalog_path = Path(catalog_path) if catalog_path is not None else DEFAULT_CATALOG_PATH
        if self.catalog_path.is_symlink():
            raise TemplateRegistryError("Refusing a symbolic-link template catalog.")
        try:
            size = self.catalog_path.stat().st_size
            if size <= 0 or size > MAX_CATALOG_BYTES:
                raise TemplateRegistryError("Template catalog size is outside the allowed limit.")
            raw = self.catalog_path.read_bytes()
        except OSError as exc:
            raise TemplateRegistryError("Bundled AI template catalog is unavailable.") from exc
        if len(raw) != size:
            raise TemplateRegistryError("Template catalog changed while being read.")
        try:
            catalog = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TemplateRegistryError("Template catalog is not valid UTF-8 JSON.") from exc
        validate_catalog(catalog)
        self._catalog = catalog
        self._templates = {item["id"]: item for item in catalog["templates"]}

    @property
    def count(self) -> int:
        return len(self._templates)

    def list_templates(
        self,
        category: str | None = None,
        mode: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 32:
            raise TemplateRegistryError("limit must be an integer from 1 to 32.")
        if mode is not None and mode not in MODES:
            raise TemplateRegistryError("Unknown template mode.")
        items = list(self._templates.values())
        if category:
            items = [item for item in items if item["category"].casefold() == category.casefold()]
        if mode:
            items = [item for item in items if item["mode"] == mode]
        return [
            {
                "id": item["id"],
                "version": item["version"],
                "name": item["name"],
                "category": item["category"],
                "description": item["description"],
                "mode": item["mode"],
                "routingKeywords": item["routingKeywords"],
                "requiredCapabilities": item["requiredCapabilities"],
                "optionalCapabilityCount": len(item["optionalCapabilities"]),
            }
            for item in items[:limit]
        ]

    def get_template(self, template_id: str) -> dict[str, Any]:
        template = self._templates.get(template_id)
        if template is None:
            raise TemplateRegistryError(f"Unknown AI template: {template_id}.")
        return _copy(template)

    def route_task(self, goal: str, max_results: int = 3) -> dict[str, Any]:
        if not isinstance(goal, str) or not goal.strip() or len(goal) > 500:
            raise TemplateRegistryError("goal must contain 1 to 500 characters.")
        if isinstance(max_results, bool) or not isinstance(max_results, int) or not 1 <= max_results <= 5:
            raise TemplateRegistryError("max_results must be an integer from 1 to 5.")

        query = goal.strip()
        query_norm = _normalize(query)
        query_terms = _terms(query)
        ranked: list[dict[str, Any]] = []

        for template in self._templates.values():
            score = 0
            signals: list[str] = []
            for keyword in template["routingKeywords"]:
                keyword_norm = _normalize(keyword)
                if keyword_norm and keyword_norm in query_norm:
                    score += 24 if len(keyword_norm) >= 2 else 8
                    if len(signals) < 8:
                        signals.append(f"keyword:{keyword}")
                else:
                    overlap = query_terms & _terms(keyword)
                    if overlap:
                        score += min(10, 4 * len(overlap))
                        if len(signals) < 8:
                            signals.append(f"term_overlap:{keyword}")

            for example in template["triggerExamples"]:
                example_norm = _normalize(example)
                if query_norm == example_norm:
                    score += 45
                    if len(signals) < 8:
                        signals.append("exact_trigger")
                elif len(query_norm) >= 5 and query_norm in example_norm:
                    score += 30
                    if len(signals) < 8:
                        signals.append("trigger_phrase")
                else:
                    overlap = query_terms & _terms(example)
                    if overlap:
                        score += min(15, 5 * len(overlap))
                        if len(signals) < 8:
                            signals.append("trigger_terms")

            name_norm = _normalize(template["name"])
            if query_norm and query_norm in name_norm:
                score += 20
                signals.append("template_name")
            if query_norm and query_norm in _normalize(template["description"]):
                score += 8
                signals.append("template_description")

            if score > 0:
                ranked.append({
                    "template_id": template["id"],
                    "name": template["name"],
                    "category": template["category"],
                    "mode": template["mode"],
                    "score": score,
                    "confidence": round(min(0.99, score / 100.0), 2),
                    "matched_signals": signals[:8],
                })

        ranked.sort(key=lambda item: (-item["score"], item["template_id"]))
        candidates = ranked[:max_results]
        recommended: str | None = None
        routing_status = "no_match"
        if candidates and candidates[0]["score"] >= 22:
            top_score = candidates[0]["score"]
            second_score = candidates[1]["score"] if len(candidates) > 1 else 0
            ambiguous = (
                second_score >= top_score * 0.82
                and top_score - second_score < max(8, top_score * 0.12)
            )
            if ambiguous:
                routing_status = "ambiguous"
            else:
                recommended = candidates[0]["template_id"]
                routing_status = "recommended"

        return {
            "goal": query,
            "routing_method": "deterministic_lexical_keyword_and_trigger_matching",
            "routing_status": routing_status,
            "recommended_template_id": recommended,
            "candidates": candidates,
            "execution_started": False,
            "next_step": (
                "Load the recommended template, then check its runtime capabilities."
                if recommended
                else "Ask one clarifying question or show the candidate templates; do not execute an operation."
            ),
        }

    def resolve_capabilities(
        self,
        template_id: str,
        bridge_capabilities: set[str] | None,
        runtime_status: str = "connected",
    ) -> dict[str, Any]:
        template = self.get_template(template_id)
        if runtime_status not in {"connected", "unavailable"}:
            raise TemplateRegistryError("Invalid runtime_status.")

        resolved: list[dict[str, Any]] = []
        missing_required: list[str] = []
        missing_optional: list[str] = []

        declarations = [
            *((name, "required") for name in template["requiredCapabilities"]),
            *((name, "optional") for name in template["optionalCapabilities"]),
        ]
        for capability, requirement in declarations:
            if capability in LOCAL_CAPABILITIES:
                binding = LOCAL_CAPABILITIES[capability]
                item = {
                    "name": capability, "requirement": requirement,
                    "status": binding["status"], "source": binding["source"],
                    "mcp_tool": binding["mcp_tool"], "bridge_commands": [],
                    "approval_required": False,
                }
            elif capability in AGENT_CAPABILITIES:
                binding = AGENT_CAPABILITIES[capability]
                item = {
                    "name": capability, "requirement": requirement,
                    "status": binding["status"], "source": binding["source"],
                    "mcp_tool": binding["mcp_tool"], "bridge_commands": [],
                    "approval_required": False,
                }
            elif capability in RUNTIME_CAPABILITY_BINDINGS:
                binding = RUNTIME_CAPABILITY_BINDINGS[capability]
                commands = binding["bridge_commands"]
                if runtime_status == "unavailable" or bridge_capabilities is None:
                    status = "runtime_unavailable"
                elif all(command in bridge_capabilities for command in commands):
                    status = "available"
                else:
                    status = "missing_runtime_capability"
                item = {
                    "name": capability, "requirement": requirement,
                    "status": status, "source": "fabric_companion_bridge",
                    "mcp_tool": binding["mcp_tool"], "bridge_commands": commands,
                    "approval_required": binding["approval_required"],
                }
            else:
                status = "unsupported"
                item = {
                    "name": capability, "requirement": requirement,
                    "status": status, "source": "no_registered_adapter",
                    "mcp_tool": None, "bridge_commands": [],
                    "approval_required": False,
                    "reason": UNIMPLEMENTED_CAPABILITY_REASONS.get(
                        capability, "No adapter is registered for this logical capability."
                    ),
                }

            resolved.append(item)
            if requirement == "required" and item["status"] not in {"available", "agent_responsibility"}:
                missing_required.append(capability)
            if requirement == "optional" and item["status"] not in {"available", "agent_responsibility"}:
                missing_optional.append(capability)

        if missing_required:
            if template["mode"] == "approval_gated":
                effective_mode = "read_only_plan_only"
            elif template["mode"] == "plan_only":
                effective_mode = "plan_only_with_explicit_unknowns"
            else:
                effective_mode = "request_user_context_or_choose_another_template"
        elif missing_optional:
            effective_mode = "available_with_reduced_scope"
        else:
            effective_mode = template["mode"]

        return {
            "template_id": template_id,
            "template_mode": template["mode"],
            "runtime_status": runtime_status,
            "capabilities": resolved,
            "missing_required": missing_required,
            "missing_optional": missing_optional,
            "required_capabilities_satisfied": not missing_required,
            "effective_mode": effective_mode,
            "permissions_granted": [],
            "execution_enabled": False,
            "notes": [
                "Capability discovery does not grant permission.",
                "Mutating tools still require their independent approval and confirmation gates.",
                "This adapter checks the Fabric companion bridge handshake, not unrelated tools in the host AI client's MCP registry.",
            ],
        }

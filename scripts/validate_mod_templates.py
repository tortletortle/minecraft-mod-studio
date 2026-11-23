#!/usr/bin/env python3
"""Validate the declarative Minecraft Mod Studio template catalog (stdlib only)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "mod-templates" / "mod-templates-v1.json"
ID_RE = re.compile(r"^[a-z0-9_][a-z0-9_./-]{0,79}$")
KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
TEMPLATE_RE = re.compile(r"^[a-z][a-z0-9-]{2,47}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
LOCALIZED = {"zh-CN", "en-US"}
KINDS = {"items", "blocks", "mobs", "quests", "effects", "guis"}
ALLOWED = {
    "items": {"kind", "damage", "durability", "rarity", "stack", "cooldown", "recipe", "behavior"},
    "blocks": {"hardness", "resistance", "material", "color", "dropCount", "oreMode", "oreSize", "oreCount", "oreMinY", "oreMaxY", "oreReplace"},
    "mobs": {"health", "attack", "speed", "body", "ai", "biome", "weight", "color", "drop", "dropCount"},
    "quests": {"description", "objective", "count", "rewardCount"},
    "effects": {"color", "category", "duration", "amplifier", "attribute", "modifier", "trigger"},
    "guis": {"title", "theme", "components"},
}
ENUMS = {
    ("items", "kind"): {"sword", "gem", "bolt", "ingot", "blank"},
    ("items", "rarity"): {"Common", "Uncommon", "Rare", "Epic"},
    ("blocks", "material"): {"stone", "wood", "metal", "glass"},
    ("blocks", "oreMode"): {"off", "overworld"},
    ("blocks", "oreReplace"): {"stone", "deepslate", "both"},
    ("mobs", "body"): {"humanoid", "quadruped", "slime"},
    ("mobs", "ai"): {"wander", "hostile", "neutral"},
    ("quests", "objective"): {"kill", "collect"},
    ("effects", "category"): {"beneficial", "harmful", "neutral"},
    ("effects", "attribute"): {"movement_speed", "attack_damage", "max_health", "none"},
    ("effects", "trigger"): {"on_apply", "on_tick"},
    ("guis", "theme"): {"parchment", "dark", "stone"},
}
RANGES = {
    "items": {"damage": (0, 100), "durability": (1, 100000), "stack": (1, 64), "cooldown": (0, 600)},
    "blocks": {"hardness": (0, 1000), "resistance": (0, 10000), "dropCount": (1, 64), "oreSize": (1, 64), "oreCount": (1, 32), "oreMinY": (-64, 319), "oreMaxY": (-64, 319)},
    "mobs": {"health": (1, 1024), "attack": (0, 1000), "speed": (0, 3), "weight": (0, 1000), "dropCount": (1, 64)},
    "quests": {"count": (1, 10000), "rewardCount": (1, 64)},
    "effects": {"duration": (1, 3600), "amplifier": (0, 255), "modifier": (-0.95, 10)},
    "guis": {},
}
RELATION_TYPES = {"drop_item", "item_recipe", "item_effect_link", "item_gui_link", "quest_target", "quest_reward", "quest_prerequisite", "quest_screen", "gui_action"}
FORBIDDEN_KEYS = {"javaSource", "sourceCode", "javascript", "script", "shellCommand", "commandText", "eval"}


def _localized(value, where, errors):
    if not isinstance(value, dict) or set(value) != LOCALIZED:
        errors.append(f"{where}: expected zh-CN and en-US strings")
        return
    for language, text in value.items():
        if not isinstance(text, str) or not text.strip() or len(text) > 240:
            errors.append(f"{where}.{language}: invalid localized text")


def _walk_forbidden(value, where, errors):
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_KEYS:
                errors.append(f"{where}: forbidden executable field {key}")
            _walk_forbidden(child, where + "." + str(key), errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{where}[{index}]", errors)


def _check_properties(resource, where, errors):
    kind = resource["kind"]
    props = resource["properties"]
    if not isinstance(props, dict):
        errors.append(f"{where}: properties must be an object")
        return
    unknown = set(props) - ALLOWED[kind]
    if unknown:
        errors.append(f"{where}: unsupported properties {sorted(unknown)}")
    for (enum_kind, field), allowed in ENUMS.items():
        if enum_kind == kind and field in props and props[field] not in allowed:
            errors.append(f"{where}: invalid {field}={props[field]!r}")
    for field, (low, high) in RANGES[kind].items():
        if field in props:
            value = props[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                errors.append(f"{where}: {field} outside [{low}, {high}]")
    if kind == "items" and props.get("kind") == "sword" and props.get("stack", 1) != 1:
        errors.append(f"{where}: sword stack must be 1")
    if kind == "blocks":
        if "color" in props and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(props["color"])):
            errors.append(f"{where}: color must be #RRGGBB")
        if props.get("oreMinY", -48) > props.get("oreMaxY", 32):
            errors.append(f"{where}: oreMinY must not exceed oreMaxY")
    if kind in {"mobs", "effects"} and "color" in props and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(props["color"])):
        errors.append(f"{where}: color must be #RRGGBB")
    if kind == "guis":
        if not isinstance(props.get("components", []), list) or len(props.get("components", [])) > 100:
            errors.append(f"{where}: components must be an array with at most 100 entries")
        for i, component in enumerate(props.get("components", [])):
            if not isinstance(component, dict):
                errors.append(f"{where}.components[{i}]: expected object")
                continue
            if set(component) - {"type", "text", "x", "y", "w", "h", "action"}:
                errors.append(f"{where}.components[{i}]: unsupported component fields")
            if component.get("type") not in {"label", "button", "slot", "progress"}:
                errors.append(f"{where}.components[{i}]: invalid component type")
            if component.get("action", "none") not in {"none", "claim_quest", "open_gui"}:
                errors.append(f"{where}.components[{i}]: invalid component action")
            for field in ("x", "y", "w", "h"):
                value = component.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    errors.append(f"{where}.components[{i}]: {field} must be numeric")
            if all(isinstance(component.get(k), (int, float)) and not isinstance(component.get(k), bool) for k in ("x", "y", "w", "h")):
                if component["w"] <= 0 or component["h"] <= 0 or component["x"] < 0 or component["y"] < 0 or component["x"] + component["w"] > 100 or component["y"] + component["h"] > 100:
                    errors.append(f"{where}.components[{i}]: component is outside the 0–100 layout bounds")
            if not isinstance(component.get("text", ""), str) or len(component.get("text", "")) > 120:
                errors.append(f"{where}.components[{i}]: invalid text")


def _relation_valid(relation, by_key, where, errors):
    kind = relation.get("type")
    source = by_key.get(relation.get("from"))
    target = by_key.get(relation.get("to"))
    if source is None or target is None:
        errors.append(f"{where}: relation endpoint does not exist")
        return
    sk, tk = source["kind"], target["kind"]
    expected = {
        "drop_item": ({"blocks", "mobs"}, {"items"}),
        "item_recipe": ({"items"}, {"items"}),
        "item_effect_link": ({"items"}, {"effects"}),
        "item_gui_link": ({"items"}, {"guis"}),
        "quest_reward": ({"quests"}, {"items"}),
        "quest_prerequisite": ({"quests"}, {"quests"}),
        "quest_screen": ({"quests"}, {"guis"}),
        "gui_action": ({"guis"}, {"quests", "guis"}),
    }
    if kind in expected:
        left, right = expected[kind]
        if sk not in left or tk not in right:
            errors.append(f"{where}: incompatible relation kinds {sk} -> {tk}")
    elif kind == "quest_target":
        if sk != "quests" or tk not in {"items", "mobs"}:
            errors.append(f"{where}: quest_target must connect quests to items or mobs")
        elif source.get("properties", {}).get("objective") == "kill" and tk != "mobs":
            errors.append(f"{where}: kill objective must target a mob")
        elif source.get("properties", {}).get("objective") == "collect" and tk != "items":
            errors.append(f"{where}: collect objective must target an item")
    else:
        errors.append(f"{where}: unknown relation type {kind!r}")
    if kind == "item_recipe" and (isinstance(relation.get("slot"), bool) or not isinstance(relation.get("slot"), int) or not 0 <= relation["slot"] <= 8):
        errors.append(f"{where}: item_recipe requires slot 0–8")
    if kind == "gui_action":
        index = relation.get("componentIndex")
        components = source.get("properties", {}).get("components", [])
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(components):
            errors.append(f"{where}: gui_action componentIndex is out of range")
        if relation.get("action") not in {"claim_quest", "open_gui"}:
            errors.append(f"{where}: gui_action requires claim_quest or open_gui")


def validate_catalog(data):
    errors = []
    if not isinstance(data, dict):
        return ["catalog must be an object"]
    if data.get("schemaVersion") != "1.0.0" or data.get("libraryId") != "mms.mod-template-library":
        errors.append("unsupported catalog identity or schema version")
    _localized(data.get("libraryName"), "libraryName", errors)
    target = data.get("target", {})
    if target != {"minecraftEdition": "Java", "minecraftVersion": "26.2", "modLoader": "Fabric", "projectSchema": [3, 4]}:
        errors.append("target must be Java/Fabric 26.2 with project schema 3–4")
    templates = data.get("templates")
    if not isinstance(templates, list) or not templates:
        return errors + ["templates must be a non-empty array"]
    ids = set()
    for index, template in enumerate(templates):
        where = f"templates[{index}]"
        if not isinstance(template, dict):
            errors.append(f"{where}: expected object")
            continue
        tid = template.get("id")
        if not isinstance(tid, str) or not TEMPLATE_RE.fullmatch(tid) or tid in ids:
            errors.append(f"{where}: invalid or duplicate template id {tid!r}")
        ids.add(tid)
        if not VERSION_RE.fullmatch(str(template.get("version", ""))):
            errors.append(f"{where}: invalid semantic version")
        for field in ("name", "description", "limitations"):
            _localized(template.get(field), where + "." + field, errors)
        if template.get("category") not in KINDS:
            errors.append(f"{where}: unsupported category")
        if template.get("difficulty") not in {"beginner", "intermediate", "advanced"}:
            errors.append(f"{where}: invalid difficulty")
        if template.get("supportLevel") not in {"source_generated", "design_only"}:
            errors.append(f"{where}: invalid supportLevel")
        resources = template.get("resources")
        if not isinstance(resources, list) or not resources:
            errors.append(f"{where}: resources must be a non-empty array")
            continue
        by_key = {}
        for ri, resource in enumerate(resources):
            rwhere = f"{where}.resources[{ri}]"
            if not isinstance(resource, dict):
                errors.append(f"{rwhere}: expected object")
                continue
            key, kind, rid = resource.get("key"), resource.get("kind"), resource.get("id")
            if not isinstance(key, str) or not KEY_RE.fullmatch(key) or key in by_key:
                errors.append(f"{rwhere}: invalid or duplicate resource key {key!r}")
            if kind not in KINDS:
                errors.append(f"{rwhere}: unsupported resource kind {kind!r}")
                continue
            if not isinstance(rid, str) or not ID_RE.fullmatch(rid) or ".." in rid or rid.startswith("/") or rid.endswith("/"):
                errors.append(f"{rwhere}: invalid registry path {rid!r}")
            _localized(resource.get("name"), rwhere + ".name", errors)
            by_key[key] = resource
            _check_properties(resource, rwhere, errors)
        if template.get("supportLevel") == "source_generated" and any(r.get("kind") not in {"items", "blocks"} for r in resources):
            errors.append(f"{where}: source_generated templates may only contain items and blocks")
        if template.get("supportLevel") == "design_only" and all(r.get("kind") in {"items", "blocks"} for r in resources):
            errors.append(f"{where}: item/block-only templates should not be marked design_only")
        relations = template.get("relations", [])
        if not isinstance(relations, list):
            errors.append(f"{where}: relations must be an array")
            continue
        for ri, relation in enumerate(relations):
            if not isinstance(relation, dict):
                errors.append(f"{where}.relations[{ri}]: expected object")
                continue
            _relation_valid(relation, by_key, f"{where}.relations[{ri}]", errors)
    _walk_forbidden(data, "catalog", errors)
    return errors


def load_catalog(path=CATALOG):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main():
    try:
        data = load_catalog()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    errors = validate_catalog(data)
    if errors:
        print("\n".join("ERROR: " + error for error in errors), file=sys.stderr)
        return 1
    print(f"OK: {len(data['templates'])} templates, {sum(len(t['resources']) for t in data['templates'])} resources, {sum(len(t.get('relations', [])) for t in data['templates'])} relations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

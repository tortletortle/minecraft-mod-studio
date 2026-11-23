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
INTEGER_FIELDS = {
    "items": {"durability", "stack"},
    "blocks": {"dropCount", "oreSize", "oreCount", "oreMinY", "oreMaxY"},
    "mobs": {"weight", "dropCount"},
    "quests": {"count", "rewardCount"},
    "effects": {"duration", "amplifier"},
    "guis": set(),
}
STRING_LIMITS = {
    "mobs": {"biome": 256, "drop": 500},
    "quests": {"description": 1000},
    "guis": {"title": 120},
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
        if enum_kind == kind and field in props and (not isinstance(props[field], str) or props[field] not in allowed):
            errors.append(f"{where}: invalid {field}={props[field]!r}")
    for field, (low, high) in RANGES[kind].items():
        if field in props:
            value = props[field]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= value <= high:
                errors.append(f"{where}: {field} outside [{low}, {high}]")
            elif field in INTEGER_FIELDS[kind] and not float(value).is_integer():
                errors.append(f"{where}: {field} must be an integer")
    for field, limit in STRING_LIMITS.get(kind, {}).items():
        if field in props and (not isinstance(props[field], str) or len(props[field]) > limit):
            errors.append(f"{where}: {field} must be a string of at most {limit} characters")
    if kind == "mobs" and "biome" in props and isinstance(props["biome"], str) and not re.fullmatch(r"[a-z0-9_.-]+:[a-z0-9_./-]+", props["biome"]):
        errors.append(f"{where}: biome must be a namespaced identifier")
    if kind == "items":
        if "recipe" in props and (not isinstance(props["recipe"], list) or len(props["recipe"]) != 9 or not all(isinstance(value, str) for value in props["recipe"])):
            errors.append(f"{where}: recipe must contain exactly nine string slots")
        if "behavior" in props and props["behavior"] is not None:
            behavior = props["behavior"]
            if not isinstance(behavior, dict) or set(behavior) != {"type", "distance"} or behavior.get("type") != "spawn_lightning":
                errors.append(f"{where}: unsupported item behavior definition")
            else:
                distance = behavior.get("distance")
                if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not float(distance).is_integer() or not 1 <= distance <= 32:
                    errors.append(f"{where}: behavior distance must be an integer from 1 to 32")
    if kind == "items" and props.get("kind") == "sword" and props.get("stack", 1) != 1:
        errors.append(f"{where}: sword stack must be 1")
    if kind == "blocks":
        if "color" in props and not re.fullmatch(r"#[0-9a-fA-F]{6}", str(props["color"])):
            errors.append(f"{where}: color must be #RRGGBB")
        min_y, max_y = props.get("oreMinY", -48), props.get("oreMaxY", 32)
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in (min_y, max_y)) and min_y > max_y:
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
            if not {"type", "text", "x", "y", "w", "h", "action"}.issubset(component):
                errors.append(f"{where}.components[{i}]: missing required component fields")
            if not isinstance(component.get("type"), str) or component.get("type") not in {"label", "button", "slot", "progress"}:
                errors.append(f"{where}.components[{i}]: invalid component type")
            action = component.get("action", "none")
            if not isinstance(action, str) or action not in {"none", "claim_quest", "open_gui"}:
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
    from_key, to_key = relation.get("from"), relation.get("to")
    if not isinstance(kind, str) or kind not in RELATION_TYPES:
        errors.append(f"{where}: unknown relation type {kind!r}")
        return
    if not isinstance(from_key, str) or not isinstance(to_key, str):
        errors.append(f"{where}: relation endpoints must be resource-key strings")
        return
    source = by_key.get(from_key)
    target = by_key.get(to_key)
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
        else:
            source_props = source.get("properties")
            objective = source_props.get("objective") if isinstance(source_props, dict) else None
            if objective == "kill" and tk != "mobs":
                errors.append(f"{where}: kill objective must target a mob")
            elif objective == "collect" and tk != "items":
                errors.append(f"{where}: collect objective must target an item")
    else:
        errors.append(f"{where}: unknown relation type {kind!r}")
    if kind == "item_recipe" and (isinstance(relation.get("slot"), bool) or not isinstance(relation.get("slot"), int) or not 0 <= relation["slot"] <= 8):
        errors.append(f"{where}: item_recipe requires slot 0–8")
    if kind == "gui_action":
        index = relation.get("componentIndex")
        source_props = source.get("properties")
        components = source_props.get("components", []) if isinstance(source_props, dict) else []
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(components):
            errors.append(f"{where}: gui_action componentIndex is out of range")
        action = relation.get("action")
        if not isinstance(action, str) or action not in {"claim_quest", "open_gui"}:
            errors.append(f"{where}: gui_action requires claim_quest or open_gui")
        elif (action == "claim_quest" and tk != "quests") or (action == "open_gui" and tk != "guis"):
            errors.append(f"{where}: gui_action target kind does not match action")


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
    categories = data.get("categories")
    if not isinstance(categories, list) or not categories:
        errors.append("categories must be a non-empty array")
    else:
        category_ids = set()
        for index, category in enumerate(categories):
            where = f"categories[{index}]"
            if not isinstance(category, dict):
                errors.append(f"{where}: expected object")
                continue
            category_id = category.get("id")
            if not isinstance(category_id, str) or category_id not in KINDS:
                errors.append(f"{where}: unsupported category id")
            elif category_id in category_ids:
                errors.append(f"{where}: duplicate category id {category_id}")
            else:
                category_ids.add(category_id)
            _localized(category.get("name"), where + ".name", errors)
        if category_ids != KINDS:
            errors.append("categories must define every supported resource category exactly once")

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
        if not isinstance(tid, str):
            errors.append(f"{where}: template id must be a string")
        elif not TEMPLATE_RE.fullmatch(tid) or tid in ids:
            errors.append(f"{where}: invalid or duplicate template id {tid!r}")
        else:
            ids.add(tid)
        if not VERSION_RE.fullmatch(str(template.get("version", ""))):
            errors.append(f"{where}: invalid semantic version")
        for field in ("name", "description", "limitations"):
            _localized(template.get(field), where + "." + field, errors)
        category = template.get("category")
        if not isinstance(category, str) or category not in KINDS:
            errors.append(f"{where}: unsupported category")
        difficulty = template.get("difficulty")
        if not isinstance(difficulty, str) or difficulty not in {"beginner", "intermediate", "advanced"}:
            errors.append(f"{where}: invalid difficulty")
        support_level = template.get("supportLevel")
        if not isinstance(support_level, str) or support_level not in {"source_generated", "design_only"}:
            errors.append(f"{where}: invalid supportLevel")
        tags = template.get("tags")
        if not isinstance(tags, list) or any(not isinstance(tag, str) or not tag.strip() or len(tag) > 32 for tag in tags):
            errors.append(f"{where}: tags must be an array of non-empty strings (max 32 chars)")
        elif len(tags) != len(set(tags)):
            errors.append(f"{where}: duplicate tags")
        resources = template.get("resources")
        if not isinstance(resources, list) or not resources or len(resources) > 24:
            errors.append(f"{where}: resources must be a non-empty array with at most 24 entries")
            continue
        by_key = {}
        for ri, resource in enumerate(resources):
            rwhere = f"{where}.resources[{ri}]"
            if not isinstance(resource, dict):
                errors.append(f"{rwhere}: expected object")
                continue
            key, kind, rid = resource.get("key"), resource.get("kind"), resource.get("id")
            key_valid = isinstance(key, str) and KEY_RE.fullmatch(key) is not None
            if not key_valid:
                errors.append(f"{rwhere}: invalid resource key {key!r}")
            elif key in by_key:
                errors.append(f"{rwhere}: duplicate resource key {key!r}")
            if not isinstance(kind, str) or kind not in KINDS:
                errors.append(f"{rwhere}: unsupported resource kind {kind!r}")
                continue
            if not isinstance(rid, str) or not ID_RE.fullmatch(rid) or ".." in rid or rid.startswith("/") or rid.endswith("/"):
                errors.append(f"{rwhere}: invalid registry path {rid!r}")
            _localized(resource.get("name"), rwhere + ".name", errors)
            if key_valid and key not in by_key:
                by_key[key] = resource
            _check_properties(resource, rwhere, errors)
        resource_kinds = [r.get("kind") for r in resources if isinstance(r, dict)]
        if template.get("supportLevel") == "source_generated" and any(not isinstance(k, str) or k not in {"items", "blocks"} for k in resource_kinds):
            errors.append(f"{where}: source_generated templates may only contain items and blocks")
        if template.get("supportLevel") == "design_only" and resource_kinds and len(resource_kinds) == len(resources) and all(isinstance(k, str) and k in {"items", "blocks"} for k in resource_kinds):
            errors.append(f"{where}: item/block-only templates should not be marked design_only")
        relations = template.get("relations", [])
        if not isinstance(relations, list) or len(relations) > 48:
            errors.append(f"{where}: relations must be an array with at most 48 entries")
            continue
        seen_relation_slots = set()
        for ri, relation in enumerate(relations):
            if not isinstance(relation, dict):
                errors.append(f"{where}.relations[{ri}]: expected object")
                continue
            extra = set(relation) - {"type", "from", "to", "slot", "componentIndex", "action"}
            if extra:
                errors.append(f"{where}.relations[{ri}]: unsupported fields {sorted(extra)}")
            _relation_valid(relation, by_key, f"{where}.relations[{ri}]", errors)
            if relation.get("type") == "item_recipe" and isinstance(relation.get("from"), str) and isinstance(relation.get("slot"), int) and not isinstance(relation.get("slot"), bool):
                slot_key = (relation["from"], relation["slot"])
                if slot_key in seen_relation_slots:
                    errors.append(f"{where}.relations[{ri}]: duplicate item_recipe slot for {relation['from']}")
                seen_relation_slots.add(slot_key)
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

#!/usr/bin/env python3
"""Run read-only or explicitly armed smoke checks against a live MMS test client."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from live_debugger_client import BridgeClient, BridgeError


REQUIRED_CAPABILITIES = {
    "status",
    "scene_snapshot",
    "capture_screenshot",
    "entities",
    "block",
    "entity_attributes",
    "set_entity_attribute",
    "reset_entity_attributes",
    "trigger_animation",
    "command_catalog",
    "command_inspect",
    "command_validate",
}


def validate_scene_snapshot(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("SCENE_SNAPSHOT_NOT_OBJECT")
    player = value.get("player")
    if not isinstance(player, dict):
        raise ValueError("SCENE_SNAPSHOT_PLAYER_MISSING")
    position = {
        axis: float(player[axis])
        for axis in ("x", "y", "z")
        if axis in player
    }
    if len(position) != 3 or not all(math.isfinite(number) for number in position.values()):
        raise ValueError("SCENE_SNAPSHOT_POSITION_INVALID")
    entities = value.get("nearby_entities")
    blocks = value.get("nearby_blocks")
    if not isinstance(entities, list) or not isinstance(blocks, dict):
        raise ValueError("SCENE_SNAPSHOT_CONTENT_INVALID")
    return {
        "dimension": value.get("dimension"),
        "game_time": value.get("game_time"),
        "position": position,
        "entity_count": len(entities),
        "entities_truncated": bool(value.get("entities_truncated", False)),
        "block_samples": sorted(blocks.keys()),
        "snapshot_consistency": value.get("snapshot_consistency"),
    }


def _validate_screenshot_metadata(value: Any, capture_id: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("capture_id") != capture_id:
        raise ValueError("SCREENSHOT_METADATA_ID_MISMATCH")
    if value.get("error"):
        raise ValueError("SCREENSHOT_CAPTURE_FAILED")
    width = value.get("width")
    height = value.get("height")
    if (
        isinstance(width, bool) or not isinstance(width, int) or width < 1
        or isinstance(height, bool) or not isinstance(height, int) or height < 1
    ):
        raise ValueError("SCREENSHOT_DIMENSIONS_INVALID")
    sha256 = value.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64:
        raise ValueError("SCREENSHOT_SHA256_MISSING")
    try:
        bytes.fromhex(sha256)
    except ValueError as exc:
        raise ValueError("SCREENSHOT_SHA256_INVALID") from exc
    return {"capture_id": capture_id, "width": width, "height": height, "sha256": sha256}


def capture_screenshot(bridge: BridgeClient, connection_file: Path, timeout_seconds: float = 10.0) -> dict[str, Any]:
    request = bridge.request("capture_screenshot")
    capture_id = request.get("capture_id")
    if request.get("capture_requested") is not True or not isinstance(capture_id, str):
        raise ValueError("SCREENSHOT_REQUEST_NOT_ACCEPTED")
    directory = connection_file.expanduser().resolve().parent
    metadata_path = directory / "capture.json"
    screenshot_path = directory / "capture.png"
    deadline = time.monotonic() + timeout_seconds
    metadata = None
    while time.monotonic() < deadline:
        if metadata_path.is_symlink() or screenshot_path.is_symlink():
            raise ValueError("SCREENSHOT_PATH_REJECTED")
        if metadata_path.is_file():
            try:
                if metadata_path.stat().st_size > 4096:
                    raise ValueError("SCREENSHOT_METADATA_TOO_LARGE")
                candidate = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                candidate = None
            if isinstance(candidate, dict) and candidate.get("capture_id") == capture_id:
                metadata = candidate
                break
        time.sleep(0.05)
    if metadata is None:
        raise TimeoutError("SCREENSHOT_CAPTURE_TIMEOUT")
    summary = _validate_screenshot_metadata(metadata, capture_id)
    if not screenshot_path.is_file():
        raise ValueError("SCREENSHOT_FILE_MISSING")
    size = screenshot_path.stat().st_size
    if size < 24 or size > 8 * 1024 * 1024:
        raise ValueError("SCREENSHOT_FILE_SIZE_INVALID")
    with screenshot_path.open("rb") as stream:
        signature = stream.read(8)
    if signature != bytes((137, 80, 78, 71, 13, 10, 26, 10)):
        raise ValueError("SCREENSHOT_PNG_SIGNATURE_INVALID")
    image_bytes = screenshot_path.read_bytes()
    actual_sha256 = hashlib.sha256(image_bytes).hexdigest()
    if actual_sha256 != summary["sha256"]:
        raise ValueError("SCREENSHOT_HASH_MISMATCH")
    summary["file_name"] = screenshot_path.name
    summary["size_bytes"] = size
    return summary


def record_check(report: dict[str, Any], name: str, action: Callable[[], Any]) -> Any:
    try:
        result = action()
        report["checks"].append({"name": name, "status": "PASS", "result": result})
        return result
    except Exception as exc:
        report["checks"].append({"name": name, "status": "FAIL", "error": str(exc)})
        return None


def validate_status(value: dict[str, Any]) -> dict[str, Any]:
    player = value.get("player")
    if not isinstance(player, dict):
        raise ValueError("STATUS_PLAYER_MISSING")
    position: dict[str, float] = {}
    for key in ("x", "y", "z"):
        number = player.get(key)
        if not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ValueError(f"STATUS_INVALID_POSITION_{key.upper()}")
        position[key] = float(number)
    return {
        "dimension": value.get("dimension"),
        "game_time": value.get("game_time"),
        "player_uuid": player.get("uuid"),
        "position": position,
    }


def validate_entities(value: dict[str, Any]) -> dict[str, Any]:
    entities = value.get("entities")
    if not isinstance(entities, list):
        raise ValueError("ENTITIES_LIST_MISSING")
    return {
        "returned": value.get("returned", len(entities)),
        "truncated": bool(value.get("truncated", False)),
        "entities": [
            {
                "uuid": item.get("uuid"),
                "type": item.get("type"),
                "name": item.get("name"),
                "distance": item.get("distance"),
            }
            for item in entities
            if isinstance(item, dict)
        ],
    }


def _validate_manifest_entry(value: Any, expected_root: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("COMMAND_MANIFEST_SUMMARY_NOT_OBJECT")
    if value.get("root_present_in_live_dispatcher") is not True:
        raise ValueError("COMMAND_MANIFEST_ROOT_NOT_LIVE")
    if value.get("ownership_verified") is not False:
        raise ValueError("COMMAND_MANIFEST_OWNERSHIP_MUST_REMAIN_UNVERIFIED")
    if value.get("trust") != "untrusted_mod_supplied_metadata":
        raise ValueError("COMMAND_MANIFEST_TRUST_LABEL_INVALID")
    if not isinstance(value.get("source_mod_id"), str) or not value["source_mod_id"]:
        raise ValueError("COMMAND_MANIFEST_SOURCE_MOD_MISSING")
    description = value.get("description")
    keywords = value.get("keywords")
    if not isinstance(description, str) or not description:
        raise ValueError("COMMAND_MANIFEST_DESCRIPTION_MISSING")
    if not isinstance(keywords, list) or not keywords:
        raise ValueError("COMMAND_MANIFEST_KEYWORDS_MISSING")
    return {
        "root": expected_root,
        "source_mod_id": value["source_mod_id"],
        "trust": value["trust"],
        "ownership_verified": False,
        "keyword_count": len(keywords),
        "description_locale": value.get("description_locale"),
    }


def validate_command_catalog(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("operator_id") != "MMS_AI_OPERATOR":
        raise ValueError("COMMAND_CATALOG_OPERATOR_INVALID")
    if value.get("execution_enabled") is not False:
        raise ValueError("COMMAND_CATALOG_EXECUTION_MUST_BE_DISABLED")
    commands = value.get("commands")
    total = value.get("total")
    if not isinstance(commands, list) or isinstance(total, bool) or not isinstance(total, int) or total < len(commands):
        raise ValueError("COMMAND_CATALOG_SHAPE_INVALID")
    names = [item.get("name") for item in commands if isinstance(item, dict)]
    if len(names) != len(commands) or any(not isinstance(name, str) or not name for name in names):
        raise ValueError("COMMAND_CATALOG_ENTRY_INVALID")
    if len(set(names)) != len(names):
        raise ValueError("COMMAND_CATALOG_DUPLICATE_ROOT")

    file_count = value.get("manifest_file_count")
    command_count = value.get("manifest_command_count")
    scanned_mods = value.get("manifest_scanned_mods")
    issue_count = value.get("manifest_issue_count")
    issues = value.get("manifest_issues")
    issues_truncated = value.get("manifest_issues_truncated")
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (
        file_count, command_count, scanned_mods, issue_count
    )):
        raise ValueError("COMMAND_MANIFEST_COUNTER_INVALID")
    if file_count > 512 or command_count > 512 or scanned_mods > 512:
        raise ValueError("COMMAND_MANIFEST_COUNTER_OUT_OF_RANGE")
    if file_count > scanned_mods or command_count > total or (command_count > 0 and file_count == 0):
        raise ValueError("COMMAND_MANIFEST_COUNTER_INCONSISTENT")
    if (
        not isinstance(issues, list)
        or len(issues) > 4
        or issue_count < len(issues)
        or type(issues_truncated) is not bool
        or issues_truncated is not (issue_count > len(issues))
    ):
        raise ValueError("COMMAND_MANIFEST_DIAGNOSTICS_INVALID")
    if any(
        not isinstance(issue, dict)
        or not isinstance(issue.get("mod_id"), str)
        or not isinstance(issue.get("code"), str)
        for issue in issues
    ):
        raise ValueError("COMMAND_MANIFEST_ISSUE_SHAPE_INVALID")
    if value.get("manifest_source") != "mms/commands.json":
        raise ValueError("COMMAND_MANIFEST_SOURCE_PATH_INVALID")

    manifests = []
    for item in commands:
        if "manifest_summary" in item:
            manifests.append(_validate_manifest_entry(item["manifest_summary"], item["name"]))
    if len(manifests) > command_count:
        raise ValueError("COMMAND_MANIFEST_PAGE_COUNT_EXCEEDS_REGISTRY")

    return {
        "operator_id": value["operator_id"],
        "execution_enabled": False,
        "total": total,
        "page_count": len(names),
        "commands": names,
        "has_more": value.get("has_more") is True,
        "catalog_source": value.get("catalog_source"),
        "manifest_registry": {
            "source": value["manifest_source"],
            "file_count": file_count,
            "command_count": command_count,
            "scanned_mods": scanned_mods,
            "issue_count": issue_count,
            "issues_truncated": issues_truncated,
            "matched_page_entries": manifests,
        },
    }


def _validate_full_command_manifest(value: Any, expected_root: str) -> dict[str, Any]:
    fields = {
        "root", "source_mod_id", "source_mod_name", "source_mod_version",
        "matched_minecraft_version", "descriptions", "keywords", "examples",
        "argument_descriptions", "effects", "execution_context", "advisory_risk",
        "advisory_reversibility", "root_present_in_live_dispatcher",
        "ownership_verified", "binding", "trust",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("COMMAND_MANIFEST_FIELDS_INVALID")
    if value.get("root") != expected_root:
        raise ValueError("COMMAND_MANIFEST_ROOT_MISMATCH")
    if value.get("root_present_in_live_dispatcher") is not True:
        raise ValueError("COMMAND_MANIFEST_ROOT_NOT_LIVE")
    if value.get("ownership_verified") is not False:
        raise ValueError("COMMAND_MANIFEST_OWNERSHIP_MUST_REMAIN_UNVERIFIED")
    if value.get("binding") != "exact_live_root_name_match_only":
        raise ValueError("COMMAND_MANIFEST_BINDING_INVALID")
    if value.get("trust") != "untrusted_mod_supplied_metadata":
        raise ValueError("COMMAND_MANIFEST_TRUST_LABEL_INVALID")

    for key, maximum in (
        ("source_mod_id", 64),
        ("source_mod_name", 64),
        ("source_mod_version", 64),
        ("matched_minecraft_version", 32),
    ):
        item = value.get(key)
        if not isinstance(item, str) or not item or len(item) > maximum or "\0" in item:
            raise ValueError("COMMAND_MANIFEST_IDENTITY_INVALID")

    descriptions = value.get("descriptions")
    if (
        not isinstance(descriptions, dict)
        or not 1 <= len(descriptions) <= 2
        or any(
            not isinstance(locale, str)
            or not re.fullmatch(r"[a-z]{2}_[a-z]{2}", locale)
            or not isinstance(description, str)
            or not description
            or len(description) > 80
            or "\0" in description
            for locale, description in descriptions.items()
        )
    ):
        raise ValueError("COMMAND_MANIFEST_DESCRIPTIONS_INVALID")

    keywords = value.get("keywords")
    if (
        not isinstance(keywords, list)
        or not 1 <= len(keywords) <= 4
        or any(not isinstance(item, str) or not item or len(item) > 24 or "\0" in item for item in keywords)
        or len(set(keywords)) != len(keywords)
    ):
        raise ValueError("COMMAND_MANIFEST_KEYWORDS_INVALID")

    examples = value.get("examples")
    if (
        not isinstance(examples, list)
        or len(examples) > 1
        or any(not isinstance(item, str) or not item or len(item) > 96 or "\0" in item for item in examples)
        or len(set(examples)) != len(examples)
    ):
        raise ValueError("COMMAND_MANIFEST_EXAMPLES_INVALID")

    arguments = value.get("argument_descriptions")
    if (
        not isinstance(arguments, dict)
        or len(arguments) > 4
        or any(
            not isinstance(key, str)
            or not key
            or len(key) > 96
            or not isinstance(description, str)
            or not description
            or len(description) > 64
            or "\0" in key
            or "\0" in description
            for key, description in arguments.items()
        )
    ):
        raise ValueError("COMMAND_MANIFEST_ARGUMENT_DESCRIPTIONS_INVALID")

    allowed_effects = {
        "blocks", "entities", "inventory", "world_rules", "time_weather",
        "player_state", "server_state", "structures", "unknown",
    }
    effects = value.get("effects")
    if (
        not isinstance(effects, list)
        or not 1 <= len(effects) <= 3
        or any(not isinstance(item, str) or item not in allowed_effects for item in effects)
        or len(set(effects)) != len(effects)
    ):
        raise ValueError("COMMAND_MANIFEST_EFFECTS_INVALID")
    execution_context = value.get("execution_context")
    if not isinstance(execution_context, str) or execution_context not in {"server", "player", "entity"}:
        raise ValueError("COMMAND_MANIFEST_EXECUTION_CONTEXT_INVALID")
    advisory_risk = value.get("advisory_risk")
    if not isinstance(advisory_risk, str) or advisory_risk not in {
        "read_only", "bounded_mutation", "destructive", "unknown"
    }:
        raise ValueError("COMMAND_MANIFEST_ADVISORY_RISK_INVALID")
    advisory_reversibility = value.get("advisory_reversibility")
    if not isinstance(advisory_reversibility, str) or advisory_reversibility not in {
        "reversible", "partially_reversible", "irreversible", "unknown"
    }:
        raise ValueError("COMMAND_MANIFEST_ADVISORY_REVERSIBILITY_INVALID")
    return value


def validate_command_inspection(value: Any, expected_name: str) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("command") != expected_name:
        raise ValueError("COMMAND_INSPECTION_NAME_MISMATCH")
    if value.get("execution_enabled") is not False:
        raise ValueError("COMMAND_INSPECTION_EXECUTION_MUST_BE_DISABLED")
    usages = value.get("usages")
    if (
        not isinstance(usages, list)
        or not usages
        or len(usages) > 4
        or any(not isinstance(item, str) or len(item) > 80 for item in usages)
    ):
        raise ValueError("COMMAND_INSPECTION_USAGE_MISSING")
    children = value.get("children")
    if not isinstance(children, list) or len(children) > 4:
        raise ValueError("COMMAND_INSPECTION_CHILDREN_INVALID")
    manifest_present = value.get("manifest_present")
    if type(manifest_present) is not bool:
        raise ValueError("COMMAND_INSPECTION_MANIFEST_FLAG_INVALID")
    manifest = None
    if manifest_present:
        manifest = _validate_full_command_manifest(value.get("manifest"), expected_name)
    elif "manifest" in value:
        raise ValueError("COMMAND_INSPECTION_MANIFEST_FLAG_MISMATCH")
    return {
        "command": expected_name,
        "usage_count": value.get("usage_count"),
        "usages": usages,
        "children_count": len(children),
        "manifest_present": manifest_present,
        "manifest": manifest,
    }


def validate_command_parse(value: Any, expected_valid: bool) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("syntax_only") is not True:
        raise ValueError("COMMAND_VALIDATION_NOT_PARSE_ONLY")
    if value.get("execution_enabled") is not False:
        raise ValueError("COMMAND_VALIDATION_EXECUTION_MUST_BE_DISABLED")
    if value.get("valid") is not expected_valid:
        raise ValueError("COMMAND_VALIDATION_RESULT_MISMATCH")
    return {
        "command": value.get("command"),
        "valid": value["valid"],
        "error_code": value.get("error_code"),
        "parsed_characters": value.get("parsed_characters"),
    }


def probe_value(attribute: dict[str, Any]) -> tuple[float, float]:
    base = float(attribute["base"])
    minimum = float(attribute["minimum"])
    maximum = float(attribute["maximum"])
    step = min(0.5, (maximum - minimum) / 10.0)
    candidate = base + step if base + step <= maximum else base - step
    if not math.isfinite(candidate) or candidate < minimum or candidate > maximum or candidate == base:
        raise ValueError("NO_SAFE_PROBE_VALUE")
    return base, candidate


def exercise_attribute(bridge: BridgeClient, mob_uuid: str, key: str) -> dict[str, Any]:
    before = bridge.request("entity_attributes", uuid=mob_uuid)
    attribute = before.get("attributes", {}).get(key)
    if not isinstance(attribute, dict) or not attribute.get("available"):
        raise ValueError("ATTRIBUTE_NOT_AVAILABLE")
    original, candidate = probe_value(attribute)

    try:
        try:
            bridge.request("set_entity_attribute", uuid=mob_uuid, attribute=key, value=candidate)
        except BridgeError as exc:
            if str(exc) != "CONFIRM_REQUIRED":
                raise
        else:
            raise AssertionError("Write without confirm unexpectedly succeeded")

        changed = bridge.request(
            "set_entity_attribute",
            uuid=mob_uuid,
            attribute=key,
            value=candidate,
            confirm=True,
        )
        observed = bridge.request("entity_attributes", uuid=mob_uuid)
        observed_value = float(observed["attributes"][key]["base"])
        if not math.isclose(observed_value, candidate, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("ATTRIBUTE_WRITE_NOT_OBSERVED")
        return {
            "attribute": key,
            "original_base": original,
            "probe_base": candidate,
            "write_response": changed,
            "observed_base": observed_value,
            "confirm_guard": "PASS",
        }
    finally:
        # Restore the exact pre-test base value; do not reset all attributes to Rig defaults.
        bridge.request(
            "set_entity_attribute",
            uuid=mob_uuid,
            attribute=key,
            value=original,
            confirm=True,
        )
        restored = bridge.request("entity_attributes", uuid=mob_uuid)
        restored_value = float(restored["attributes"][key]["base"])
        if not math.isclose(restored_value, original, rel_tol=0.0, abs_tol=1e-6):
            raise AssertionError("ATTRIBUTE_RESTORE_NOT_OBSERVED")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection-file", required=True, type=Path)
    parser.add_argument("--mob-uuid", help="Optional generated Studio mob UUID for entity/attribute checks")
    parser.add_argument("--animation-id", help="Optional generated animation ID to trigger")
    parser.add_argument(
        "--exercise-attribute",
        choices=("attack_damage", "movement_speed"),
        help="Temporarily change and restore one attribute; requires --allow-world-mutation",
    )
    parser.add_argument(
        "--allow-world-mutation",
        action="store_true",
        help="Explicitly arm the temporary attribute write test in a disposable world",
    )
    parser.add_argument("--report", type=Path, help="Optional path for a JSON acceptance report")

    args = parser.parse_args()
    if args.animation_id and not args.mob_uuid:
        parser.error("--animation-id requires --mob-uuid")
    if args.exercise_attribute and not args.mob_uuid:
        parser.error("--exercise-attribute requires --mob-uuid")
    if args.exercise_attribute and not args.allow_world_mutation:
        parser.error("--exercise-attribute requires --allow-world-mutation")

    report: dict[str, Any] = {
        "schema_version": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "connection_file": str(args.connection_file),
        "checks": [],
    }

    try:
        with BridgeClient(args.connection_file) as bridge:
            report["protocol"] = 1
            report["capabilities"] = bridge.capabilities
            missing = sorted(REQUIRED_CAPABILITIES.difference(bridge.capabilities))
            if missing:
                report["checks"].append({
                    "name": "protocol_capabilities",
                    "status": "FAIL",
                    "error": "MISSING_CAPABILITIES",
                    "missing": missing,
                })
            else:
                report["checks"].append({
                    "name": "protocol_capabilities",
                    "status": "PASS",
                    "result": {"required": sorted(REQUIRED_CAPABILITIES)},
                })

            status = record_check(
                report,
                "player_status",
                lambda: validate_status(bridge.request("status")),
            )
            record_check(
                report,
                "scene_snapshot",
                lambda: validate_scene_snapshot(bridge.request("scene_snapshot", radius=16.0)),
            )
            command_catalog = record_check(
                report,
                "command_catalog",
                lambda: validate_command_catalog(bridge.request("command_catalog", offset=0, limit=8)),
            )
            if command_catalog:
                if "fill" in command_catalog["commands"]:
                    record_check(
                        report,
                        "command_inspection",
                        lambda: validate_command_inspection(
                            bridge.request("command_inspect", name="fill"),
                            "fill",
                        ),
                    )
                    record_check(
                        report,
                        "command_syntax_valid",
                        lambda: validate_command_parse(
                            bridge.request("command_validate", command="fill ~ ~ ~ ~1 ~1 ~1 minecraft:stone"),
                            True,
                        ),
                    )
                    record_check(
                        report,
                        "command_syntax_invalid",
                        lambda: validate_command_parse(
                            bridge.request("command_validate", command="mms_not_a_real_command"),
                            False,
                        ),
                    )
                else:
                    report["checks"].append({
                        "name": "command_inspection",
                        "status": "FAIL",
                        "error": "VANILLA_FILL_COMMAND_NOT_FOUND",
                    })
            record_check(
                report,
                "render_target_screenshot",
                lambda: capture_screenshot(bridge, args.connection_file),
            )
            entities = record_check(
                report,
                "nearby_entities",
                lambda: validate_entities(bridge.request("entities", radius=16.0)),
            )

            if status:
                position = status["position"]
                coords = {
                    "x": math.floor(position["x"]),
                    "y": math.floor(position["y"]),
                    "z": math.floor(position["z"]),
                }
                record_check(
                    report,
                    "block_inspection",
                    lambda: _validate_block(bridge.request("block", **coords)),
                )

            if args.mob_uuid:
                record_check(
                    report,
                    "generated_mob_inspection",
                    lambda: _validate_mob(
                        bridge.request("inspect_entity", uuid=args.mob_uuid),
                        args.mob_uuid,
                    ),
                )
                attributes = record_check(
                    report,
                    "generated_mob_attributes",
                    lambda: _validate_attributes(
                        bridge.request("entity_attributes", uuid=args.mob_uuid),
                        args.mob_uuid,
                    ),
                )
                if args.exercise_attribute:
                    record_check(
                        report,
                        "attribute_write_and_restore",
                        lambda: exercise_attribute(bridge, args.mob_uuid, args.exercise_attribute),
                    )
                if args.animation_id:
                    record_check(
                        report,
                        "generated_animation_trigger",
                        lambda: _validate_animation(
                            bridge.request(
                                "trigger_animation",
                                uuid=args.mob_uuid,
                                animation_id=args.animation_id,
                            ),
                            args.animation_id,
                        ),
                    )
            else:
                report["notes"] = [
                    "Pass --mob-uuid to exercise generated-mob inspection and attribute controls.",
                    "Pass --animation-id to trigger a generated animation.",
                ]
    except (OSError, ValueError, BridgeError) as exc:
        report["connection_error"] = str(exc)

    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report["passed"] = (
        "connection_error" not in report
        and bool(report["checks"])
        and all(item.get("status") == "PASS" for item in report["checks"])
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(rendered + "\n", encoding="utf-8")

    return 0 if report["passed"] else 1


def _validate_block(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value.get("id"), str):
        raise ValueError("BLOCK_ID_MISSING")
    return {key: value.get(key) for key in ("x", "y", "z", "id", "name", "air", "fluid")}


def _validate_mob(value: dict[str, Any], expected_uuid: str) -> dict[str, Any]:
    if value.get("uuid") != expected_uuid:
        raise ValueError("ENTITY_UUID_MISMATCH")
    return {key: value.get(key) for key in ("uuid", "type", "name", "health", "max_health")}


def _validate_attributes(value: dict[str, Any], expected_uuid: str) -> dict[str, Any]:
    if value.get("uuid") != expected_uuid:
        raise ValueError("ATTRIBUTE_UUID_MISMATCH")
    attributes = value.get("attributes")
    if not isinstance(attributes, dict):
        raise ValueError("ATTRIBUTE_MAP_MISSING")
    for key in ("max_health", "attack_damage", "movement_speed"):
        if (
            not isinstance(attributes.get(key), dict)
            or "base" not in attributes[key]
            or "effective" not in attributes[key]
        ):
            raise ValueError(f"ATTRIBUTE_VALUE_MISSING_{key.upper()}")
    return {
        "uuid": expected_uuid,
        "attributes": {
            key: {
                "base": attributes[key]["base"],
                "effective": attributes[key]["effective"],
            }
            for key in ("max_health", "attack_damage", "movement_speed")
        },
    }


def _validate_animation(value: dict[str, Any], expected_id: str) -> dict[str, Any]:
    if value.get("animation_id") != expected_id or value.get("triggered") is not True:
        raise ValueError("ANIMATION_TRIGGER_NOT_CONFIRMED")
    return value


if __name__ == "__main__":
    raise SystemExit(main())

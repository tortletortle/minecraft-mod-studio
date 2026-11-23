import base64
import hashlib
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from runtime_acceptance import (
    _validate_animation,
    _validate_attributes,
    _validate_block,
    _validate_screenshot_metadata,
    _validate_manifest_entry,
    validate_command_catalog,
    validate_command_inspection,
    validate_command_parse,
    capture_screenshot,
    probe_value,
    validate_entities,
    validate_scene_snapshot,
    validate_status,
)


class RuntimeAcceptanceTests(unittest.TestCase):
    def test_status_summary_requires_finite_player_position(self):
        value = {
            "dimension": "minecraft:overworld",
            "game_time": 120,
            "player": {"uuid": "player-1", "x": 1.5, "y": 64.0, "z": -2.5},
        }
        summary = validate_status(value)
        self.assertEqual(summary["position"], {"x": 1.5, "y": 64.0, "z": -2.5})

    def test_status_rejects_non_finite_position(self):
        with self.assertRaisesRegex(ValueError, "STATUS_INVALID_POSITION_X"):
            validate_status({"player": {"x": math.inf, "y": 0, "z": 0}})

    def test_entities_summary_filters_non_object_entries(self):
        summary = validate_entities({
            "returned": 2,
            "truncated": False,
            "entities": [{"uuid": "mob-1", "type": "test:mob"}, None],
        })
        self.assertEqual(summary["returned"], 2)
        self.assertEqual(len(summary["entities"]), 1)

    def test_scene_snapshot_requires_player_entities_and_block_samples(self):
        summary = validate_scene_snapshot({
            "dimension": "minecraft:overworld",
            "game_time": 123,
            "player": {"x": 1.0, "y": 64.0, "z": -2.0},
            "nearby_entities": [{"uuid": "mob-1"}],
            "nearby_blocks": {"below_feet": {"id": "minecraft:stone"}},
            "snapshot_consistency": "single_client_thread_capture",
        })
        self.assertEqual(summary["entity_count"], 1)
        self.assertEqual(summary["block_samples"], ["below_feet"])
        with self.assertRaisesRegex(ValueError, "SCENE_SNAPSHOT_POSITION_INVALID"):
            validate_scene_snapshot({
                "player": {"x": math.inf, "y": 64.0, "z": 0.0},
                "nearby_entities": [],
                "nearby_blocks": {},
            })

    def test_screenshot_metadata_requires_matching_id_and_dimensions(self):
        summary = _validate_screenshot_metadata({
            "capture_id": "capture-1", "width": 1280, "height": 720, "sha256": "a" * 64,
        }, "capture-1")
        self.assertEqual(summary["width"], 1280)
        with self.assertRaisesRegex(ValueError, "SCREENSHOT_METADATA_ID_MISMATCH"):
            _validate_screenshot_metadata({"capture_id": "other"}, "capture-1")
        with self.assertRaisesRegex(ValueError, "SCREENSHOT_DIMENSIONS_INVALID"):
            _validate_screenshot_metadata({
                "capture_id": "capture-1", "width": 0, "height": 720,
            }, "capture-1")

    def test_capture_screenshot_validates_fixed_png_and_records_hash(self):
        capture_id = "00000000-0000-0000-0000-000000000001"
        png = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p0sAAAAASUVORK5CYII="
        )

        class FakeBridge:
            def request(self, command):
                self.assert_command = command
                return {
                    "capture_id": capture_id,
                    "capture_requested": True,
                    "file_name": "capture.png",
                }

        with tempfile.TemporaryDirectory() as temporary:
            connection_file = Path(temporary) / "connection.json"
            connection_file.write_text("{}", encoding="utf-8")
            directory = connection_file.parent
            (directory / "capture.png").write_bytes(png)
            (directory / "capture.json").write_text(json.dumps({
                "capture_id": capture_id, "width": 1, "height": 1, "sha256": hashlib.sha256(png).hexdigest(),
            }), encoding="utf-8")

            result = capture_screenshot(FakeBridge(), connection_file)
            self.assertEqual(result["file_name"], "capture.png")
            self.assertEqual(result["width"], 1)
            self.assertEqual(result["height"], 1)
            self.assertEqual(result["size_bytes"], len(png))
            self.assertEqual(len(result["sha256"]), 64)

    def test_command_catalog_requires_virtual_operator_and_read_only_mode(self):
        summary = validate_command_catalog({
            "operator_id": "MMS_AI_OPERATOR",
            "execution_enabled": False,
            "total": 2,
            "commands": [
                {
                    "name": "fill",
                    "manifest_summary": {
                        "source_mod_id": "example_mod",
                        "description_locale": "zh_cn",
                        "description": "区域填充",
                        "keywords": ["批量替换"],
                        "root_present_in_live_dispatcher": True,
                        "ownership_verified": False,
                        "trust": "untrusted_mod_supplied_metadata",
                    },
                },
                {"name": "summon"},
            ],
            "has_more": False,
            "catalog_source": "live_integrated_server_brigadier_dispatcher",
            "manifest_source": "mms/commands.json",
            "manifest_file_count": 1,
            "manifest_command_count": 1,
            "manifest_scanned_mods": 24,
            "manifest_issue_count": 0,
            "manifest_issues_truncated": False,
            "manifest_issues": [],
        })
        self.assertEqual(summary["commands"], ["fill", "summon"])
        self.assertEqual(summary["manifest_registry"]["command_count"], 1)
        self.assertFalse(summary["manifest_registry"]["matched_page_entries"][0]["ownership_verified"])
        with self.assertRaisesRegex(ValueError, "COMMAND_CATALOG_EXECUTION_MUST_BE_DISABLED"):
            validate_command_catalog({
                "operator_id": "MMS_AI_OPERATOR",
                "execution_enabled": True,
                "total": 0,
                "commands": [],
            })

    def test_command_manifest_must_remain_untrusted_and_unverified(self):
        manifest = {
            "source_mod_id": "example_npc_mod",
            "description_locale": "zh_cn",
            "description": "管理 NPC",
            "keywords": ["NPC"],
            "root_present_in_live_dispatcher": True,
            "ownership_verified": False,
            "trust": "untrusted_mod_supplied_metadata",
        }
        self.assertEqual(_validate_manifest_entry(manifest, "npc")["trust"], "untrusted_mod_supplied_metadata")
        manifest["ownership_verified"] = True
        with self.assertRaisesRegex(ValueError, "COMMAND_MANIFEST_OWNERSHIP_MUST_REMAIN_UNVERIFIED"):
            _validate_manifest_entry(manifest, "npc")

    def test_command_catalog_reports_total_manifest_diagnostics_when_samples_are_truncated(self):
        catalog = {
            "operator_id": "MMS_AI_OPERATOR",
            "execution_enabled": False,
            "total": 0,
            "commands": [],
            "manifest_source": "mms/commands.json",
            "manifest_file_count": 1,
            "manifest_command_count": 0,
            "manifest_scanned_mods": 1,
            "manifest_issue_count": 6,
            "manifest_issues": [
                {"mod_id": f"mod_{index}", "code": "MANIFEST_REJECTED"}
                for index in range(3)
            ],
            "manifest_issues_truncated": True,
        }
        summary = validate_command_catalog(catalog)
        self.assertEqual(summary["manifest_registry"]["issue_count"], 6)
        self.assertTrue(summary["manifest_registry"]["issues_truncated"])

        catalog["manifest_issues_truncated"] = False
        with self.assertRaisesRegex(ValueError, "COMMAND_MANIFEST_DIAGNOSTICS_INVALID"):
            validate_command_catalog(catalog)

    def test_command_inspection_and_syntax_validation_are_non_executing(self):
        inspected = validate_command_inspection({
            "command": "fill",
            "execution_enabled": False,
            "usage_count": 1,
            "usages": ["fill <from> <to> <block>"],
            "children": [],
            "manifest_present": False,
        }, "fill")
        self.assertEqual(inspected["usage_count"], 1)
        self.assertTrue(validate_command_parse({
            "syntax_only": True,
            "execution_enabled": False,
            "valid": True,
            "command": "fill ~ ~ ~ ~1 ~1 ~1 minecraft:stone",
        }, True)["valid"])
        with self.assertRaisesRegex(ValueError, "COMMAND_VALIDATION_RESULT_MISMATCH"):
            validate_command_parse({
                "syntax_only": True,
                "execution_enabled": False,
                "valid": True,
            }, False)

    def test_command_inspection_validates_full_untrusted_manifest(self):
        manifest = {
            "root": "fill",
            "source_mod_id": "example_mod",
            "source_mod_name": "Example Mod",
            "source_mod_version": "1.0.0",
            "matched_minecraft_version": "26.2",
            "descriptions": {"zh_cn": "区域填充"},
            "keywords": ["批量替换"],
            "examples": ["/fill ~ ~ ~ ~1 ~1 ~1 stone"],
            "argument_descriptions": {"<from>": "起始坐标"},
            "effects": ["blocks"],
            "execution_context": "server",
            "advisory_risk": "destructive",
            "advisory_reversibility": "unknown",
            "root_present_in_live_dispatcher": True,
            "ownership_verified": False,
            "binding": "exact_live_root_name_match_only",
            "trust": "untrusted_mod_supplied_metadata",
        }
        value = {
            "command": "fill",
            "execution_enabled": False,
            "usage_count": 1,
            "usages": ["fill <from> <to> <block>"],
            "children": [],
            "manifest_present": True,
            "manifest": manifest,
        }
        summary = validate_command_inspection(value, "fill")
        self.assertTrue(summary["manifest_present"])
        self.assertEqual(summary["manifest"]["trust"], "untrusted_mod_supplied_metadata")

        manifest["ownership_verified"] = True
        with self.assertRaisesRegex(ValueError, "COMMAND_MANIFEST_OWNERSHIP_MUST_REMAIN_UNVERIFIED"):
            validate_command_inspection(value, "fill")

        manifest["ownership_verified"] = False
        manifest["descriptions"]["zh_cn"] = "非法控制字符\x01"
        with self.assertRaisesRegex(ValueError, "COMMAND_MANIFEST_DESCRIPTIONS_INVALID"):
            validate_command_inspection(value, "fill")

    def test_worst_case_manifest_catalog_and_inspection_fit_bridge_line_limit(self):
        def repeated(value, count):
            return value * count

        summary = {
            "source_mod_id": repeated("m", 64),
            "description_locale": "zh_cn",
            "description": repeated("汉", 64),
            "keywords": [repeated("词", 16) for _ in range(3)],
            "root_present_in_live_dispatcher": True,
            "ownership_verified": False,
            "trust": "untrusted_mod_supplied_metadata",
        }
        issues = [
            {"mod_id": repeated("m", 64), "code": repeated("X", 64)}
            for _ in range(3)
        ]
        catalog = {
            "operator_id": "MMS_AI_OPERATOR",
            "operator_entity_bound": False,
            "permission_view": "ALL_PERMISSIONS",
            "execution_enabled": False,
            "dimension": "minecraft:overworld",
            "total": 512,
            "oversized_root_names_skipped": 0,
            "offset": 0,
            "limit": 8,
            "has_more": True,
            "commands": [
                {
                    "name": repeated("r", 62) + f"{index:02d}",
                    "executable_at_root": False,
                    "child_count": 2147483647,
                    "redirect": False,
                    "manifest_summary": summary,
                }
                for index in range(8)
            ],
            "catalog_source": "live_integrated_server_brigadier_dispatcher",
            "manifest_source": "mms/commands.json",
            "manifest_file_count": 512,
            "manifest_command_count": 512,
            "manifest_scanned_mods": 512,
            "manifest_issues": issues,
            "manifest_issue_count": 40_000,
            "manifest_issues_truncated": True,
        }

        manifest = {
            "root": repeated("r", 64),
            "source_mod_id": repeated("m", 64),
            "source_mod_name": repeated("汉", 64),
            "source_mod_version": repeated("v", 64),
            "matched_minecraft_version": repeated("2", 32),
            "descriptions": {"zh_cn": repeated("汉", 64), "en_us": repeated("汉", 64)},
            "keywords": [repeated("词", 16) for _ in range(3)],
            "examples": [repeated("例", 64)],
            "argument_descriptions": {
                repeated("键", 62) + f"{index:02d}": repeated("值", 48)
                for index in range(3)
            },
            "effects": ["blocks", "entities", "inventory"],
            "execution_context": "entity",
            "advisory_risk": "destructive",
            "advisory_reversibility": "partially_reversible",
            "root_present_in_live_dispatcher": True,
            "ownership_verified": False,
            "binding": "exact_live_root_name_match_only",
            "trust": "untrusted_mod_supplied_metadata",
        }
        usages = [repeated("用", 64) for _ in range(3)]
        inspection = {
            "operator_id": "MMS_AI_OPERATOR",
            "execution_enabled": False,
            "command": repeated("r", 64),
            "executable_at_root": True,
            "child_count": 2147483647,
            "smart_usage_count": 2147483647,
            "smart_usage_truncated": True,
            "redirect": True,
            "usage_count": 2147483647,
            "usages": usages,
            "smart_usage": usages,
            "children": [
                {
                    "name": repeated("子", 32),
                    "node_type": repeated("类", 32),
                    "executable": True,
                    "child_count": 2147483647,
                    "redirect": True,
                }
                for _ in range(3)
            ],
            "children_truncated": True,
            "catalog_source": "live_integrated_server_brigadier_dispatcher",
            "manifest_present": True,
            "manifest": manifest,
            "manifest_file_count": 512,
            "manifest_command_count": 512,
            "manifest_scanned_mods": 512,
            "manifest_issues": issues,
            "manifest_issue_count": 40_000,
            "manifest_issues_truncated": True,
        }
        for payload in (catalog, inspection):
            encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8") + b"\n"
            self.assertLessEqual(len(encoded), 8192)

    def test_probe_value_stays_inside_bounds_and_changes_value(self):
        candidate = probe_value({"base": 10.0, "minimum": 0.0, "maximum": 20.0})
        self.assertEqual(candidate, (10.0, 10.5))
        candidate_at_max = probe_value({"base": 20.0, "minimum": 0.0, "maximum": 20.0})
        self.assertEqual(candidate_at_max, (20.0, 19.5))

    def test_probe_value_rejects_fixed_range(self):
        with self.assertRaisesRegex(ValueError, "NO_SAFE_PROBE_VALUE"):
            probe_value({"base": 2.0, "minimum": 2.0, "maximum": 2.0})

    def test_block_summary_requires_registry_id(self):
        self.assertEqual(_validate_block({"x": 1, "y": 2, "z": 3, "id": "minecraft:stone"})["id"], "minecraft:stone")
        with self.assertRaisesRegex(ValueError, "BLOCK_ID_MISSING"):
            _validate_block({"x": 1, "y": 2, "z": 3})

    def test_attribute_summary_checks_all_supported_attributes(self):
        values = {
            "uuid": "mob-1",
            "attributes": {
                key: {"base": 1.0, "effective": 1.0}
                for key in ("max_health", "attack_damage", "movement_speed")
            },
        }
        self.assertEqual(_validate_attributes(values, "mob-1")["uuid"], "mob-1")
        with self.assertRaisesRegex(ValueError, "ATTRIBUTE_VALUE_MISSING_ATTACK_DAMAGE"):
            _validate_attributes(
                {"uuid": "mob-1", "attributes": {
                    "max_health": {"base": 1.0, "effective": 1.0},
                }},
                "mob-1",
            )

    def test_animation_summary_requires_confirmed_matching_id(self):
        self.assertTrue(_validate_animation({"animation_id": "attack", "triggered": True}, "attack")["triggered"])
        with self.assertRaisesRegex(ValueError, "ANIMATION_TRIGGER_NOT_CONFIRMED"):
            _validate_animation({"animation_id": "idle", "triggered": True}, "attack")


if __name__ == "__main__":
    unittest.main()

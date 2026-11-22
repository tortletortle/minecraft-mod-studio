import base64
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
            "capture_id": "capture-1", "width": 1280, "height": 720,
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
                "capture_id": capture_id, "width": 1, "height": 1,
            }), encoding="utf-8")

            result = capture_screenshot(FakeBridge(), connection_file)
            self.assertEqual(result["file_name"], "capture.png")
            self.assertEqual(result["width"], 1)
            self.assertEqual(result["height"], 1)
            self.assertEqual(result["size_bytes"], len(png))
            self.assertEqual(len(result["sha256"]), 64)

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

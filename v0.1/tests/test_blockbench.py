from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from creature_studio.blockbench import BlockbenchImportError, export_bbmodel, import_bbmodel

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples/void_scout/void_scout.bbmodel"


def signature(model):
    return (
        model["textureSize"],
        tuple(
            (
                bone["uuid"], bone["name"], bone["parent"], tuple(bone["origin"]), tuple(bone["pivot"]),
                tuple(
                    (cube["uuid"], tuple(cube["from"]), tuple(cube["to"]), tuple(cube["uv"]))
                    for cube in bone["cubes"]
                )
            )
            for bone in model["bones"]
        ),
        model["texture"]["pngBase64"],
        model["animations"]
    )


class BlockbenchTests(unittest.TestCase):
    def test_import_and_export_roundtrip_preserves_supported_content(self):
        original = import_bbmodel(SAMPLE)
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "roundtrip.bbmodel"
            export_bbmodel(original, output)
            restored = import_bbmodel(output)
        self.assertEqual(signature(original), signature(restored))
        self.assertEqual(len(restored["bones"]), 3)
        self.assertEqual(sum(len(bone["cubes"]) for bone in restored["bones"]), 2)

    def test_rejects_rotated_cube_instead_of_silently_losing_rotation(self):
        import json
        data = json.loads(SAMPLE.read_text(encoding="utf-8"))
        data["elements"][0]["rotation"] = [0, 30, 0]
        with tempfile.TemporaryDirectory() as temp:
            model = Path(temp) / "rotated.bbmodel"
            model.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaises(BlockbenchImportError):
                import_bbmodel(model)


if __name__ == "__main__":
    unittest.main()

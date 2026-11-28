from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creature_studio.generator import generate
from model_fixtures import write_duplicate_sibling_bbmodel

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples/void_scout"


class GeneratorTests(unittest.TestCase):
    def _project_copy(self, temp: Path, name: str, backend: str):
        model = SAMPLE / "void_scout.bbmodel"
        target = temp / name
        target.mkdir()
        (target / "void_scout.bbmodel").write_bytes(model.read_bytes())
        project = json.loads((SAMPLE / ("creature-geckolib.json" if backend == "geckolib" else "creature.json")).read_text())
        (target / "creature.json").write_text(json.dumps(project), encoding="utf-8")
        return target / "creature.json"

    def test_vanilla_generator_emits_a_buildable_project_shape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = self._project_copy(root, "project", "vanilla")
            output = root / "generated"
            report = generate(project, output)
            self.assertEqual(report["status"], "GENERATED")
            self.assertTrue((output / "build.gradle").is_file())
            self.assertTrue((output / "src/main/resources/fabric.mod.json").is_file())
            self.assertTrue((output / "src/main/java/com/example/voidscout/ModItems.java").is_file())
            self.assertTrue((output / "src/main/resources/assets/voidscout/items/void_scout_spawn_egg.json").is_file())
            self.assertTrue((output / "src/main/resources/assets/voidscout/models/item/void_scout_spawn_egg.json").is_file())
            self.assertTrue((output / "src/main/resources/assets/voidscout/textures/item/void_scout_spawn_egg.png").is_file())
            self.assertTrue((output / "src/main/java/com/example/voidscout/VoidScoutEntity.java").is_file())
            self.assertTrue((output / "src/client/java/com/example/voidscout/client/model/VoidScoutModel.java").is_file())
            main = (output / "src/main/java/com/example/voidscout/ModMain.java").read_text()
            self.assertIn("UseEntityCallback.EVENT", main)
            self.assertIn("InteractionHand.MAIN_HAND", main)
            model_java = (output / "src/client/java/com/example/voidscout/client/model/VoidScoutModel.java").read_text()
            self.assertIn("PartPose.offset(0.0000F, 24.0000F, 0.0000F)", model_java)
            self.assertIn(".addBox(-4.0000F, -4.0000F, -2.0000F, 8.0000F, 8.0000F, 4.0000F)", model_java)
            self.assertIn("MeleeAttackGoal", (output / "src/main/java/com/example/voidscout/VoidScoutEntity.java").read_text())
            self.assertEqual(report["bones"], 3)
            self.assertEqual(report["cubes"], 2)

    def test_duplicate_sibling_bones_keep_unique_names_after_file_generation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            model_path = write_duplicate_sibling_bbmodel(
                SAMPLE / "void_scout.bbmodel", root / "duplicate.bbmodel"
            )
            for backend in ("vanilla", "geckolib"):
                project = json.loads((SAMPLE / (
                    "creature-geckolib.json" if backend == "geckolib" else "creature.json"
                )).read_text(encoding="utf-8"))
                project["creature"]["model"]["file"] = model_path.name
                project_path = root / f"{backend}.json"
                project_path.write_text(json.dumps(project), encoding="utf-8")
                output = root / f"{backend}-output"
                generate(project_path, output)

                if backend == "vanilla":
                    source = (output / "src/client/java/com/example/voidscout/client/model/VoidScoutModel.java").read_text()
                    self.assertIn('addOrReplaceChild("body_2"', source)
                    self.assertIn('getChild("body_2")', source)
                else:
                    geo_path = output / "src/main/resources/assets/voidscout_gecko/geckolib/models/entity/void_scout.geo.json"
                    bones = json.loads(geo_path.read_text())["minecraft:geometry"][0]["bones"]
                    names = [bone["name"] for bone in bones]
                    self.assertEqual(len(names), len(set(names)))
                    by_name = {bone["name"]: bone for bone in bones}
                    self.assertEqual(by_name["head"]["parent"], "body")
                    self.assertEqual(by_name["body_2"]["parent"], "root")

    def test_geckolib_backend_generates_dependency_and_geo_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            project = self._project_copy(root, "project", "geckolib")
            output = root / "generated"
            report = generate(project, output)
            build = (output / "build.gradle").read_text()
            fabric = json.loads((output / "src/main/resources/fabric.mod.json").read_text())
            geo = json.loads((output / "src/main/resources/assets/voidscout_gecko/geckolib/models/entity/void_scout.geo.json").read_text())
            entity = (output / "src/main/java/com/example/voidscout_gecko/VoidScoutEntity.java").read_text()
            self.assertEqual(report["renderBackend"], "geckolib")
            self.assertIn("geckolib-fabric-26.2:5.5.8", build)
            self.assertIn("geckolib", fabric["depends"])
            bones = geo["minecraft:geometry"][0]["bones"]
            self.assertEqual(geo["minecraft:geometry"][0]["description"]["texture_width"], 64)
            self.assertEqual(next(b for b in bones if b["name"] == "head")["pivot"], [0.0, 9.0, 0.0])
            head_cube = next(b for b in bones if b["name"] == "head")["cubes"][0]
            self.assertEqual(head_cube["origin"], [-3.0, 9.0, -3.0])
            self.assertIn("implements GeoEntity", entity)


if __name__ == "__main__":
    unittest.main()

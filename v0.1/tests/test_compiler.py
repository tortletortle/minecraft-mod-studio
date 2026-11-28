from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from creature_studio.blockbench import import_bbmodel
from creature_studio.compiler import compile_project, _gecko_geometry, _vanilla_model_source
from model_fixtures import write_duplicate_sibling_bbmodel
from creature_studio.generator import generate

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "examples/void_scout"


class CompilerTests(unittest.TestCase):
    def test_compiler_returns_deterministic_in_memory_file_map(self):
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        model_path = SAMPLE / "void_scout.bbmodel"
        model = import_bbmodel(model_path)
        source = model_path.read_bytes()
        first = compile_project(project, model, source)
        second = compile_project(project, model, source)
        self.assertEqual(first.files, second.files)
        self.assertIn("studio-build-manifest.json", first.files)
        manifest = json.loads(first.files["studio-build-manifest.json"])
        self.assertIn("src/main/java/com/example/voidscout/ModMain.java", manifest["files"])
        self.assertEqual(first.report["status"], "COMPILED")
        self.assertEqual(first.report["fileCount"], len(first.files))

    def test_blockbench_y_up_conversion_matches_vanilla_and_geckolib_world_geometry(self):
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        model = import_bbmodel(SAMPLE / "void_scout.bbmodel")
        vanilla_source = _vanilla_model_source(project, model, "com.example.voidscout", "VoidScout")
        geometry = _gecko_geometry(project, model)
        gecko_bones = {bone["name"]: bone for bone in geometry["minecraft:geometry"][0]["bones"]}

        self.assertIn("PartPose.offset(0.0000F, 24.0000F, 0.0000F)", vanilla_source)
        self.assertIn("PartPose.offset(0.0000F, -4.0000F, 0.0000F)", vanilla_source)
        self.assertIn("PartPose.offset(0.0000F, -5.0000F, 0.0000F)", vanilla_source)
        self.assertIn(".addBox(-4.0000F, -4.0000F, -2.0000F, 8.0000F, 8.0000F, 4.0000F)", vanilla_source)
        self.assertIn(".addBox(-3.0000F, -6.0000F, -3.0000F, 6.0000F, 6.0000F, 6.0000F)", vanilla_source)
        self.assertEqual(gecko_bones["body"]["pivot"], [0.0, 4.0, 0.0])
        self.assertEqual(gecko_bones["head"]["pivot"], [0.0, 9.0, 0.0])
        self.assertEqual(gecko_bones["body"]["cubes"][0]["origin"], [-4.0, 0.0, -2.0])
        self.assertEqual(gecko_bones["head"]["cubes"][0]["origin"], [-3.0, 9.0, -3.0])

        vanilla_pose = {}
        for bone in model["bones"]:
            if bone["parent"] is None:
                vanilla_pose[bone["uuid"]] = [
                    bone["origin"][0], 24.0 - bone["origin"][1], bone["origin"][2]
                ]
            else:
                parent = vanilla_pose[bone["parent"]]
                vanilla_pose[bone["uuid"]] = [
                    parent[0] + bone["pivot"][0],
                    parent[1] - bone["pivot"][1],
                    parent[2] + bone["pivot"][2],
                ]
            geo_bone = gecko_bones[bone["name"]]
            self.assertEqual(geo_bone["pivot"], [
                -bone["origin"][0], bone["origin"][1], bone["origin"][2]
            ])
            for cube, geo_cube in zip(bone["cubes"], geo_bone["cubes"]):
                x, local_y, z = cube["localFrom"]
                w, h, d = cube["size"]
                vanilla_min_x = vanilla_pose[bone["uuid"]][0] + x
                vanilla_min_y = vanilla_pose[bone["uuid"]][1] - (local_y + h)
                vanilla_min_z = vanilla_pose[bone["uuid"]][2] + z
                self.assertEqual(vanilla_min_x, cube["from"][0])
                self.assertEqual(vanilla_min_y, 24.0 - cube["to"][1])
                self.assertEqual(vanilla_min_z, cube["from"][2])
                self.assertEqual(geo_cube["origin"], [
                    -cube["to"][0], cube["from"][1], cube["from"][2]
                ])
                self.assertEqual(geo_cube["size"], [w, h, d])
                self.assertEqual(-(geo_cube["origin"][0] + w), vanilla_min_x)
                self.assertEqual(24.0 - (geo_cube["origin"][1] + h), vanilla_min_y)
                self.assertEqual(geo_cube["origin"][2], vanilla_min_z)

    def test_duplicate_sibling_bones_use_unique_names_in_both_backends(self):
        with tempfile.TemporaryDirectory() as temp:
            model_path = write_duplicate_sibling_bbmodel(
                SAMPLE / "void_scout.bbmodel", Path(temp) / "duplicate.bbmodel"
            )
            model = import_bbmodel(model_path)
            source_bytes = model_path.read_bytes()

            vanilla_project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
            vanilla = compile_project(vanilla_project, model, source_bytes)
            java_path = "src/client/java/com/example/voidscout/client/model/VoidScoutModel.java"
            java = vanilla.files[java_path]
            self.assertIn('part_root.addOrReplaceChild("body_2"', java)
            self.assertIn('this.part_body_2 = this.part_root.getChild("body_2")', java)
            self.assertIn('this.part_head = this.part_body.getChild("head")', java)

            gecko_project = json.loads((SAMPLE / "creature-geckolib.json").read_text(encoding="utf-8"))
            gecko = compile_project(gecko_project, model, source_bytes)
            geo_path = (
                "src/main/resources/assets/voidscout_gecko/geckolib/models/entity/void_scout.geo.json"
            )
            geometry = json.loads(gecko.files[geo_path])
            bones = geometry["minecraft:geometry"][0]["bones"]
            names = [bone["name"] for bone in bones]
            self.assertEqual(len(names), len(set(names)))
            by_name = {bone["name"]: bone for bone in bones}
            self.assertEqual(by_name["head"]["parent"], "body")
            self.assertEqual(by_name["body_2"]["parent"], "root")

    def test_behavior_graph_and_state_machine_compile_for_both_render_backends(self):
        model_path = SAMPLE / "void_scout.bbmodel"
        model = import_bbmodel(model_path)
        source_bytes = model_path.read_bytes()
        graph = {
            "version": 1,
            "entry": "event",
            "variables": [],
            "nodes": [
                {"id": "event", "op": "event", "event": "use", "next": "message", "x": 0, "y": 0},
                {"id": "message", "op": "message", "text": "Behavior graph executed",
                 "next": "done", "x": 1, "y": 0},
                {"id": "done", "op": "end", "success": True, "x": 2, "y": 0},
            ],
        }
        machine = {
            "enabled": True,
            "initial": "idle",
            "states": [
                {"id": "idle", "animation": "idle", "loop": True},
                {"id": "walk", "animation": "walk", "loop": True},
            ],
            "transitions": [
                {"id": "tr_walk", "from": "idle", "to": "walk", "condition": "moving",
                 "threshold": 0.02, "priority": 40, "cooldown": 2},
                {"id": "tr_idle", "from": "walk", "to": "idle", "condition": "stopped",
                 "threshold": 0.01, "priority": 10, "cooldown": 2},
            ],
        }

        for backend in ("vanilla", "geckolib"):
            with self.subTest(backend=backend):
                project = json.loads((SAMPLE / (
                    "creature-geckolib.json" if backend == "geckolib" else "creature.json"
                )).read_text(encoding="utf-8"))
                project["behavior_graph"] = graph
                project["state_machine"] = machine
                result = compile_project(project, model, source_bytes)
                package_path = f"src/main/java/com/example/{project['project']['modId']}"
                entity_path = f"{package_path}/VoidScoutEntity.java"
                entity = result.files[entity_path]
                main = result.files[f"{package_path}/ModMain.java"]

                self.assertIn("private static boolean run0(Context ctx)", entity)
                self.assertIn("new BehaviorContext(player, stack)", entity)
                self.assertIn('private String studioState = "idle";', entity)
                self.assertIn("this.tickStudioStateMachine();", entity)
                self.assertIn('this.studioState.equals("walk")', entity)
                self.assertIn(
                    "creature.onPlayerInteracted(player, player.getItemInHand(hand));",
                    main,
                )
                self.assertEqual(result.report["behaviorGraph"], "JAVA_METHODS_GENERATED")
                self.assertEqual(result.report["stateMachine"], "SERVER_TICK_SKELETON_GENERATED")
                if backend == "geckolib":
                    self.assertIn("implements GeoEntity", entity)
                else:
                    self.assertIn(
                        "src/client/java/com/example/voidscout/client/model/VoidScoutModel.java",
                        result.files,
                    )

    def test_legacy_compilation_keeps_original_interaction_entrypoints(self):
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        model_path = SAMPLE / "void_scout.bbmodel"
        result = compile_project(project, import_bbmodel(model_path), model_path.read_bytes())
        entity = result.files["src/main/java/com/example/voidscout/VoidScoutEntity.java"]
        main = result.files["src/main/java/com/example/voidscout/ModMain.java"]
        self.assertIn("public void onPlayerInteracted()", entity)
        self.assertNotIn("BehaviorContext", entity)
        self.assertNotIn("tickStudioStateMachine", entity)
        self.assertIn("creature.onPlayerInteracted();", main)
        self.assertNotIn("behaviorGraph", result.report)
        self.assertNotIn("stateMachine", result.report)

    def test_file_generator_persists_the_same_compiler_output(self):
        project = json.loads((SAMPLE / "creature.json").read_text(encoding="utf-8"))
        model_path = SAMPLE / "void_scout.bbmodel"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "void_scout.bbmodel").write_bytes(model_path.read_bytes())
            project["creature"]["model"]["file"] = "void_scout.bbmodel"
            project_file = input_dir / "creature.json"
            project_file.write_text(json.dumps(project), encoding="utf-8")
            output = root / "output"
            report = generate(project_file, output)
            self.assertEqual(report["status"], "GENERATED")
            self.assertTrue((output / "studio-build-manifest.json").is_file())
            self.assertTrue((output / "source-assets/void_scout.bbmodel").is_file())


if __name__ == "__main__":
    unittest.main()

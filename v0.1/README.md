# Minecraft Mod Studio V0.1

V0.1 is a deliberately small, independent creature compiler for Minecraft Java 26.2 / Fabric.

It is not a rewrite of the old editor. It establishes a versioned project contract, a Blockbench import bridge, a standalone Fabric generator and reproducible build/runtime acceptance fixtures.

## Quick start

From the repository root:

    python -m pip install -r v0.1/requirements.txt
    PYTHONPATH=v0.1 python -m creature_studio.cli validate --project v0.1/examples/void_scout/creature.json
    PYTHONPATH=v0.1 python -m creature_studio.cli roundtrip --model v0.1/examples/void_scout/void_scout.bbmodel --out /tmp/void_scout_roundtrip.bbmodel
    PYTHONPATH=v0.1 python -m creature_studio.cli generate --project v0.1/examples/void_scout/creature.json --out /tmp/void_scout_fabric

Then build the generated project with JDK 25 and Gradle 9.5.1:

    cd /tmp/void_scout_fabric
    gradle build

The JAR is written to build/libs/voidscout-0.1.0.jar. Install it and Fabric API into a Minecraft 26.2 Fabric instance, then run:

    /summon voidscout:void_scout

Right-click the creature to trigger the configured message interaction.

## Optional GeckoLib backend

Generate the same creature through the optional GeckoLib adapter:

    PYTHONPATH=v0.1 python -m creature_studio.cli generate --project v0.1/examples/void_scout/creature-geckolib.json --out /tmp/void_scout_gecko

This adds GeckoLib Fabric 5.5.8 for Minecraft 26.2 and emits a GeckoLib geo model. The CI build verifies API and dependency compatibility. V0.1 does not yet compile Blockbench animation tracks into runtime GeckoLib animations.

## Blockbench support boundary

Supported input is Blockbench .bbmodel format 5.0, Generic Model or Modded Entity, one PNG texture, box UV, unrotated groups and unrotated cubes. The bridge preserves bone hierarchy, cube bounds, UV offsets, texture bytes and animation source data in .bbmodel round-trip.

V0.1 explicitly rejects rotated groups/cubes, per-face UV, multiple textures, meshes, locators and unsupported Blockbench format versions. Runtime animation compilation is not included in the first version. This avoids silently damaging model data.

## Static complexity report

Every generated project includes creature-analysis.json with entity, bone, cube, animation, texture and handler counts. It does not claim to predict CPU, RAM, MSPT or FPS. Runtime measurements are a later stage.

## Evidence levels

- Schema and generator tests: automated Python tests.
- Fabric compile: Gradle build on GitHub Actions.
- GeckoLib compatibility: generated GeckoLib project compile on the same Fabric 26.2/JDK 25 toolchain.
- In-world acceptance: separate manual-only Fabric GameTest workflow. It requires the user to explicitly run the workflow and check the Minecraft EULA confirmation; ordinary PR CI never accepts the EULA.

from __future__ import annotations

import base64
import json
import math
import re
import shutil
from pathlib import Path
from typing import Any

from .blockbench import import_bbmodel
from .schema import validate_project


class GenerationError(ValueError):
    pass


def _java_id(value: str, fallback: str = "Part") -> str:
    words = re.findall(r"[A-Za-z0-9]+", value)
    result = "".join(word[:1].upper() + word[1:] for word in words) or fallback
    if result[0].isdigit():
        result = "N" + result
    return result


def _java_field(value: str) -> str:
    result = re.sub(r"[^A-Za-z0-9_]", "_", value).lower()
    if not result or result[0].isdigit():
        result = "bone_" + result
    return result


def _jstr(value: str) -> str:
    return json.dumps(str(value), ensure_ascii=True)


def _f(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise GenerationError("Non-finite numeric value reached the Java generator")
    return f"{number:.4f}F"


def _write(root: Path, relative: str, data: str | bytes) -> None:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise GenerationError(f"Generated path escapes project root: {relative}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, bytes):
        target.write_bytes(data)
    else:
        target.write_text(data, encoding="utf-8", newline="\n")


def _model_bones(model: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    bones = model["bones"]
    names: dict[str, str] = {}
    used: set[str] = set()
    for bone in bones:
        candidate = _java_field(bone["name"])
        base = candidate
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        names[bone["uuid"]] = candidate
    return bones, names


def _vanilla_model_source(project: dict[str, Any], model: dict[str, Any], package: str, cls: str) -> str:
    bones, fields = _model_bones(model)
    lines: list[str] = []
    for bone in bones:
        field = fields[bone["uuid"]]
        parent_uuid = bone["parent"]
        parent = f"part_{fields[parent_uuid]}" if parent_uuid else "root"
        builder = f"cubes_{field}"
        lines.append(f"        CubeListBuilder {builder} = CubeListBuilder.create();")
        for cube in bone["cubes"]:
            u, v = cube["uv"]
            x, y, z = cube["localFrom"]
            w, h, d = cube["size"]
            lines.append(
                f"        {builder} = {builder}.texOffs({u}, {v}).addBox("
                f"{_f(x)}, {_f(y)}, {_f(z)}, {_f(w)}, {_f(h)}, {_f(d)});"
            )
        lines.append(
            f"        PartDefinition part_{field} = {parent}.addOrReplaceChild("
            f"{_jstr(bone['name'])}, {builder}, PartPose.offset("
            f"{_f(bone['pivot'][0])}, {_f(bone['pivot'][1])}, {_f(bone['pivot'][2])}));"
        )

    fields_source = "\n".join(f"    private final ModelPart part_{fields[b['uuid']]};" for b in bones)
    assigns: list[str] = []
    for bone in bones:
        field = fields[bone["uuid"]]
        parent_uuid = bone["parent"]
        parent = f"this.part_{fields[parent_uuid]}" if parent_uuid else "root"
        assigns.append(f"        this.part_{field} = {parent}.getChild({_jstr(bone['name'])});")
    width, height = model["textureSize"]
    mod_id = project["project"]["modId"]
    entity_id = project["creature"]["id"]
    return f"""package {package}.client.model;

import net.minecraft.client.model.EntityModel;
import net.minecraft.client.model.geom.ModelLayerLocation;
import net.minecraft.client.model.geom.ModelPart;
import net.minecraft.client.model.geom.PartPose;
import net.minecraft.client.model.geom.builders.CubeListBuilder;
import net.minecraft.client.model.geom.builders.LayerDefinition;
import net.minecraft.client.model.geom.builders.MeshDefinition;
import net.minecraft.client.model.geom.builders.PartDefinition;
import net.minecraft.resources.Identifier;
import {package}.client.state.{cls}RenderState;

/** Generated from Blockbench .bbmodel 5.0 by Minecraft Mod Studio V0.1. */
public final class {cls}Model extends EntityModel<{cls}RenderState> {{
    public static final ModelLayerLocation LAYER = new ModelLayerLocation(
        Identifier.fromNamespaceAndPath({_jstr(mod_id)}, {_jstr("entity/" + entity_id)}), "main");
{fields_source}

    public {cls}Model(ModelPart root) {{
        super(root);
{chr(10).join(assigns)}
    }}

    public static LayerDefinition createBodyLayer() {{
        MeshDefinition mesh = new MeshDefinition();
        PartDefinition root = mesh.getRoot();
{chr(10).join(lines)}
        return LayerDefinition.create(mesh, {width}, {height});
    }}

    @Override
    public void setupAnim({cls}RenderState state) {{
        super.setupAnim(state);
    }}
}}
"""


def _gecko_geometry(project: dict[str, Any], model: dict[str, Any]) -> dict[str, Any]:
    bones, _ = _model_bones(model)
    width, height = model["textureSize"]
    output_bones = []
    for bone in bones:
        item: dict[str, Any] = {
            "name": _java_field(bone["name"]),
            "pivot": [-bone["pivot"][0], bone["pivot"][1], bone["pivot"][2]],
            "cubes": []
        }
        if bone["parent"]:
            parent = next(b for b in bones if b["uuid"] == bone["parent"])
            item["parent"] = _java_field(parent["name"])
        for cube in bone["cubes"]:
            x, y, z = cube["localFrom"]
            w, h, d = cube["size"]
            item["cubes"].append({
                "origin": [x, y, z],
                "size": [w, h, d],
                "uv": cube["uv"]
            })
        output_bones.append(item)
    creature = project["creature"]
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [{
            "description": {
                "identifier": f"geometry.{project['project']['modId']}.{creature['id']}",
                "texture_width": width,
                "texture_height": height,
                "visible_bounds_width": max(2.0, creature["dimensions"]["width"] * 2.0),
                "visible_bounds_height": max(2.0, creature["dimensions"]["height"] * 2.0),
                "visible_bounds_offset": [0, 1, 0]
            },
            "bones": output_bones
        }]
    }


def _java_sources(project: dict[str, Any], model: dict[str, Any]) -> dict[str, str]:
    mod_id = project["project"]["modId"]
    creature = project["creature"]
    target = project["target"]
    cls = _java_id(creature["id"])
    package = f"com.example.{mod_id}"
    attr = creature["attributes"]
    size = creature["dimensions"]
    category = creature["category"]
    backend = target["renderBackend"]
    interaction_message = creature["interaction"]["message"]
    combat_goal = (
        "        this.goalSelector.addGoal(0, new MeleeAttackGoal(this, 1.1D, true));\\n"
        if category == "MONSTER" and float(attr["attackDamage"]) > 0 else ""
    )
    target_goal = (
        "        this.targetSelector.addGoal(1, new NearestAttackableTargetGoal<>(this, Player.class, true));\\n"
        if category == "MONSTER" and float(attr["attackDamage"]) > 0 else ""
    )

    if backend == "geckolib":
        entity_imports = """import com.geckolib.animatable.GeoEntity;
import com.geckolib.animatable.instance.AnimatableInstanceCache;
import com.geckolib.animatable.manager.AnimatableManager;
import com.geckolib.util.GeckoLibUtil;
"""
        entity_interfaces = " implements GeoEntity"
        entity_fields = """    private final AnimatableInstanceCache geoCache = GeckoLibUtil.createInstanceCache(this);

    @Override
    public void registerControllers(AnimatableManager.ControllerRegistrar controllers) {
        // V0.1 compatibility fixture: controller registration is intentionally empty.
    }

    @Override
    public AnimatableInstanceCache getAnimatableInstanceCache() {
        return this.geoCache;
    }
"""
        renderer = f"""package {package}.client.renderer;

import com.geckolib.renderer.GeoEntityRenderer;
import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.state.LivingEntityRenderState;
import {package}.ModEntities;
import {package}.{cls}Entity;

/** GeckoLib 5 renderer generated by Mod Studio V0.1. */
public final class {cls}Renderer extends GeoEntityRenderer<{cls}Entity, LivingEntityRenderState> {{
    public {cls}Renderer(EntityRendererProvider.Context context) {{
        super(context, ModEntities.{cls.upper()});
    }}
}}
"""
        client = f"""package {package}.client;

import net.fabricmc.api.ClientModInitializer;
import net.minecraft.client.renderer.entity.EntityRenderers;
import {package}.ModEntities;
import {package}.client.renderer.{cls}Renderer;

public final class ModClient implements ClientModInitializer {{
    @Override
    public void onInitializeClient() {{
        EntityRenderers.register(ModEntities.{cls.upper()}, {cls}Renderer::new);
    }}
}}
"""
    else:
        entity_imports = ""
        entity_interfaces = ""
        entity_fields = ""
        renderer = f"""package {package}.client.renderer;

import net.minecraft.client.renderer.entity.EntityRendererProvider;
import net.minecraft.client.renderer.entity.MobRenderer;
import net.minecraft.resources.Identifier;
import {package}.{cls}Entity;
import {package}.client.model.{cls}Model;
import {package}.client.state.{cls}RenderState;

/** Vanilla renderer generated by Mod Studio V0.1. */
public final class {cls}Renderer extends MobRenderer<{cls}Entity, {cls}RenderState, {cls}Model> {{
    private static final Identifier TEXTURE = Identifier.fromNamespaceAndPath(
        {_jstr(mod_id)}, {_jstr("textures/entity/" + creature["id"] + ".png")});

    public {cls}Renderer(EntityRendererProvider.Context context) {{
        super(context, new {cls}Model(context.bakeLayer({cls}Model.LAYER)), 0.45F);
    }}

    @Override
    public {cls}RenderState createRenderState() {{
        return new {cls}RenderState();
    }}

    @Override
    public Identifier getTextureLocation({cls}RenderState state) {{
        return TEXTURE;
    }}
}}
"""
        client = f"""package {package}.client;

import net.fabricmc.api.ClientModInitializer;
import net.fabricmc.fabric.api.client.rendering.v1.ModelLayerRegistry;
import net.minecraft.client.renderer.entity.EntityRenderers;
import {package}.ModEntities;
import {package}.client.model.{cls}Model;
import {package}.client.renderer.{cls}Renderer;

public final class ModClient implements ClientModInitializer {{
    @Override
    public void onInitializeClient() {{
        ModelLayerRegistry.registerModelLayer({cls}Model.LAYER, {cls}Model::createBodyLayer);
        EntityRenderers.register(ModEntities.{cls.upper()}, {cls}Renderer::new);
    }}
}}
"""

    entity = f"""package {package};

import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.goal.LookAtPlayerGoal;
import net.minecraft.world.entity.ai.goal.MeleeAttackGoal;
import net.minecraft.world.entity.ai.goal.RandomLookAroundGoal;
import net.minecraft.world.entity.ai.goal.WaterAvoidingRandomStrollGoal;
import net.minecraft.world.entity.ai.goal.target.NearestAttackableTargetGoal;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.level.Level;
import net.minecraft.network.chat.Component;
{entity_imports}
/** Generated creature implementation. Runtime interaction is server-authoritative. */
public final class {cls}Entity extends PathfinderMob{entity_interfaces} {{
    private int interactionCount;

    public {cls}Entity(EntityType<? extends {cls}Entity> type, Level level) {{
        super(type, level);
    }}

    @Override
    protected void registerGoals() {{
{combat_goal}        this.goalSelector.addGoal(1, new WaterAvoidingRandomStrollGoal(this, 1.0D));
        this.goalSelector.addGoal(2, new LookAtPlayerGoal(this, Player.class, 8.0F));
        this.goalSelector.addGoal(3, new RandomLookAroundGoal(this));
{target_goal}    }}

    public void onPlayerInteracted() {{
        this.interactionCount++;
        this.setCustomName(Component.literal({_jstr(interaction_message)}));
        this.setCustomNameVisible(true);
    }}

    public int getInteractionCount() {{
        return this.interactionCount;
    }}

{entity_fields}}}
"""

    entities = f"""package {package};

import net.fabricmc.fabric.api.object.builder.v1.entity.FabricDefaultAttributeRegistry;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.entity.EntityType;
import net.minecraft.world.entity.MobCategory;
import net.minecraft.world.entity.PathfinderMob;
import net.minecraft.world.entity.ai.attributes.Attributes;

public final class ModEntities {{
    public static final EntityType<{cls}Entity> {cls.upper()} = register();

    private static EntityType<{cls}Entity> register() {{
        var key = ResourceKey.create(Registries.ENTITY_TYPE,
            Identifier.fromNamespaceAndPath(ModMain.MOD_ID, {_jstr(creature["id"])}));
        return Registry.register(BuiltInRegistries.ENTITY_TYPE, key,
            EntityType.Builder.of({cls}Entity::new, MobCategory.{category})
                .sized({_f(size["width"])}, {_f(size["height"])})
                .build(key));
    }}

    public static void initialize() {{
        FabricDefaultAttributeRegistry.register({cls.upper()},
            PathfinderMob.createMobAttributes()
                .add(Attributes.MAX_HEALTH, {float(attr["maxHealth"]):.4f}D)
                .add(Attributes.ATTACK_DAMAGE, {float(attr["attackDamage"]):.4f}D)
                .add(Attributes.MOVEMENT_SPEED, {float(attr["movementSpeed"]):.4f}D));
    }}

    private ModEntities() {{}}
}}
"""

    items = f"""package {package};

import net.fabricmc.fabric.api.itemgroup.v1.ItemGroupEvents;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.Identifier;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.SpawnEggItem;

public final class ModItems {{
    public static final Item {cls.upper()}_SPAWN_EGG = registerSpawnEgg();

    private static Item registerSpawnEgg() {{
        var key = ResourceKey.create(Registries.ITEM,
            Identifier.fromNamespaceAndPath(ModMain.MOD_ID, {_jstr(creature["id"] + "_spawn_egg")}));
        Item item = Registry.register(BuiltInRegistries.ITEM, key,
            new SpawnEggItem(new Item.Properties().setId(key).spawnEgg(ModEntities.{cls.upper()})));
        ItemGroupEvents.modifyEntriesEvent(CreativeModeTabs.SPAWN_EGGS)
            .register(entries -> entries.accept(item));
        return item;
    }}

    public static void initialize() {{ }}

    private ModItems() {{ }}
}}
"""

    main = f"""package {package};

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.player.UseEntityCallback;
import net.minecraft.world.InteractionResult;

public final class ModMain implements ModInitializer {{
    public static final String MOD_ID = {_jstr(mod_id)};

    @Override
    public void onInitialize() {{
        ModEntities.initialize();
        ModItems.initialize();
        UseEntityCallback.EVENT.register((player, level, hand, entity, hitResult) -> {{
            if (!(entity instanceof {cls}Entity creature)) {{
                return InteractionResult.PASS;
            }}
            if (player.isSpectator()) {{
                return InteractionResult.PASS;
            }}
            if (!level.isClientSide()) {{
                creature.onPlayerInteracted();
            }}
            return InteractionResult.SUCCESS;
        }});
    }}
}}
"""

    output = {
        f"src/main/java/{package.replace('.', '/')}/ModMain.java": main,
        f"src/main/java/{package.replace('.', '/')}/ModEntities.java": entities,
        f"src/main/java/{package.replace('.', '/')}/ModItems.java": items,
        f"src/main/java/{package.replace('.', '/')}/{cls}Entity.java": entity,
        f"src/client/java/{package.replace('.', '/')}/client/ModClient.java": client,
        f"src/client/java/{package.replace('.', '/')}/client/renderer/{cls}Renderer.java": renderer
    }

    if backend == "vanilla":
        state = f"""package {package}.client.state;

import net.minecraft.client.renderer.entity.state.LivingEntityRenderState;

public final class {cls}RenderState extends LivingEntityRenderState {{ }}
"""
        output[f"src/client/java/{package.replace('.', '/')}/client/state/{cls}RenderState.java"] = state
        output[f"src/client/java/{package.replace('.', '/')}/client/model/{cls}Model.java"] = _vanilla_model_source(
            project, model, package, cls
        )
    else:
        if model.get("animations"):
            raise GenerationError(
                "V0.1 GeckoLib backend currently supports geometry/texture only. "
                "Animation data is preserved in .bbmodel round-trip but is not yet compiled."
            )
        geometry = _gecko_geometry(project, model)
        output[
            f"src/main/resources/assets/{mod_id}/geckolib/models/entity/{creature['id']}.geo.json"
        ] = json.dumps(geometry, indent=2) + "\n"
        output[
            f"src/main/resources/assets/{mod_id}/geckolib/animations/entity/{creature['id']}.animation.json"
        ] = json.dumps({"format_version": "1.8.0", "animations": {}}, indent=2) + "\n"

    return output


def _gradle_files(project: dict[str, Any]) -> dict[str, str]:
    mod_id = project["project"]["modId"]
    target = project["target"]
    gecko = target["renderBackend"] == "geckolib"
    gecko_repo = """
    maven {
        name = "GeckoLib"
        url = "https://dl.cloudsmith.io/public/geckolib3/geckolib/maven/"
    }
""" if gecko else ""
    gecko_dependency = (
        f'    implementation "com.geckolib:geckolib-fabric-26.2:{target["geckolibVersion"]}"\n'
        if gecko else ""
    )
    gecko_property = f"geckolib_version={target['geckolibVersion']}\n" if gecko else ""
    return {
        "settings.gradle": f"""pluginManagement {{
    repositories {{
        maven {{ url = 'https://maven.fabricmc.net/' }}
        gradlePluginPortal()
        mavenCentral()
    }}
}}
rootProject.name = '{mod_id}'
""",
        "gradle.properties": f"""org.gradle.jvmargs=-Xmx2G
org.gradle.parallel=false
minecraft_version={target['minecraftVersion']}
loader_version={target['fabricLoaderVersion']}
loom_version={target['loomVersion']}
fabric_api_version={target['fabricApiVersion']}
{gecko_property}""",
        "build.gradle": f"""plugins {{
    id 'net.fabricmc.fabric-loom' version '{target["loomVersion"]}'
}}

group = 'com.example'
version = '0.1.0'
base {{
    archivesName = '{mod_id}'
}}

repositories {{
    maven {{ url = 'https://maven.fabricmc.net/' }}
    mavenCentral()
{gecko_repo}}}

loom {{
    splitEnvironmentSourceSets()
    mods {{
        "{mod_id}" {{
            sourceSet sourceSets.main
            sourceSet sourceSets.client
        }}
    }}
}}

dependencies {{
    minecraft "com.mojang:minecraft:{target['minecraftVersion']}"
    implementation "net.fabricmc:fabric-loader:{target['fabricLoaderVersion']}"
    implementation "net.fabricmc.fabric-api:fabric-api:{target['fabricApiVersion']}"
{gecko_dependency}}}

java {{
    sourceCompatibility = JavaVersion.VERSION_25
    targetCompatibility = JavaVersion.VERSION_25
}}

tasks.withType(JavaCompile).configureEach {{
    options.release = 25
    options.encoding = 'UTF-8'
}}

tasks.withType(AbstractArchiveTask).configureEach {{
    preserveFileTimestamps = false
    reproducibleFileOrder = true
}}
""",
    }


def generate(project_path: str | Path, output_path: str | Path) -> dict[str, Any]:
    project_file = Path(project_path).resolve()
    try:
        project = json.loads(project_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GenerationError(f"Cannot read creature project: {exc}") from exc
    validate_project(project, project_file)

    model_file = (project_file.parent / project["creature"]["model"]["file"]).resolve()
    if not model_file.is_relative_to(project_file.parent.resolve()):
        raise GenerationError("Model file escapes the creature project directory")
    model = import_bbmodel(model_file)
    if model.get("animations"):
        raise GenerationError(
            "V0.1 imports and round-trips Blockbench geometry, bones, UVs and texture. "
            "Runtime animation compilation is not included in this first version."
        )

    output = Path(output_path).resolve()
    if output.exists() and any(output.iterdir()):
        raise GenerationError(f"Output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    for relative, content in _gradle_files(project).items():
        _write(output, relative, content)
    for relative, content in _java_sources(project, model).items():
        _write(output, relative, content)

    mod_id = project["project"]["modId"]
    creature = project["creature"]
    cls = _java_id(creature["id"])
    package = f"com.example.{mod_id}"
    backend = project["target"]["renderBackend"]
    fabric = {
        "schemaVersion": 1,
        "id": mod_id,
        "version": "0.1.0",
        "name": project["project"]["name"],
        "description": "Generated by Minecraft Mod Studio V0.1",
        "environment": "*",
        "entrypoints": {
            "main": [f"{package}.ModMain"],
            "client": [f"{package}.client.ModClient"]
        },
        "depends": {
            "fabricloader": f">={project['target']['fabricLoaderVersion']}",
            "minecraft": project["target"]["minecraftVersion"],
            "java": ">=25",
            "fabric-api": "*"
        }
    }
    if backend == "geckolib":
        fabric["depends"]["geckolib"] = f">={project['target']['geckolibVersion']}"
    _write(output, "src/main/resources/fabric.mod.json", json.dumps(fabric, indent=2) + "\n")
    _write(
        output,
        f"src/main/resources/assets/{mod_id}/lang/en_us.json",
        json.dumps({f"entity.{mod_id}.{creature['id']}": creature["displayName"]}, indent=2) + "\n"
    )
    texture = base64.b64decode(model["texture"]["pngBase64"])
    _write(output, f"src/main/resources/assets/{mod_id}/textures/entity/{creature['id']}.png", texture)
    source_assets = output / "source-assets"
    source_assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(model_file, source_assets / f"{creature['id']}.bbmodel")

    cube_count = sum(len(bone["cubes"]) for bone in model["bones"])
    analysis = {
        "schemaVersion": "1.0.0",
        "analysisType": "static_complexity",
        "runtimeCpuPrediction": None,
        "runtimeMemoryPrediction": None,
        "metrics": {
            "entityTypes": 1,
            "bones": len(model["bones"]),
            "cubes": cube_count,
            "animations": len(model["animations"]),
            "texturePixels": model["textureSize"][0] * model["textureSize"][1],
            "interactionHandlers": 1,
            "aiGoals": 4 if creature["category"] == "MONSTER" and creature["attributes"]["attackDamage"] > 0 else 3,
            "targetSelectors": 1 if creature["category"] == "MONSTER" and creature["attributes"]["attackDamage"] > 0 else 0,
            "spawnEggItems": 1
        },
        "classification": "low" if len(model["bones"]) <= 8 and cube_count <= 24 else "medium",
        "note": "Static structural counts only. No CPU, memory, MSPT or FPS estimate is claimed."
    }
    _write(output, "creature-analysis.json", json.dumps(analysis, indent=2) + "\n")
    _write(output, "creature-project.json", json.dumps(project, indent=2) + "\n")
    _write(output, "BUILD_README.md", f"""# {project['project']['name']}

Generated by Minecraft Mod Studio V0.1.

## Toolchain
- Minecraft {project['target']['minecraftVersion']}
- Fabric Loader {project['target']['fabricLoaderVersion']}
- Fabric API {project['target']['fabricApiVersion']}
- Java 25
- Fabric Loom {project['target']['loomVersion']}
- Render backend: {backend}

## Build
Run gradle build from this directory with JDK 25 and Gradle 9.5.1 installed.
The distributable JAR is written to build/libs/{mod_id}-0.1.0.jar.

## In-game check
Install the JAR and its declared dependencies in a Fabric 26.2 instance.
Use the {creature['displayName']} Spawn Egg from the Spawn Eggs creative tab, or run /summon {mod_id}:{creature['id']}.
Right-click the creature to trigger its configured interaction.

## Model support boundary
V0.1 imports Blockbench 5.0 Generic Model / Modded Entity .bbmodel files
with one PNG texture, box UV, unrotated groups and unrotated cubes.
The original .bbmodel is retained in source-assets/.
Runtime animation compilation, per-face UV, rotated cubes/bones, multiple
textures, meshes and locators are not included. Unsupported input is rejected
instead of silently degraded.

The complexity report is static structural analysis, not a runtime performance
prediction. creature-analysis.json does not claim CPU or memory percentages.
""")

    return {
        "status": "GENERATED",
        "output": str(output),
        "modId": mod_id,
        "entityId": f"{mod_id}:{creature['id']}",
        "renderBackend": backend,
        "bones": len(model["bones"]),
        "cubes": cube_count,
        "animations": len(model["animations"]),
        "gradleBuild": "NOT_RUN",
        "gameRuntime": "NOT_RUN"
    }

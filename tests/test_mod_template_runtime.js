"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const ROOT = path.resolve(__dirname, "..");
const html = fs.readFileSync(path.join(ROOT, "Minecraft_Mod_Studio_V25.html"), "utf8");
const catalog = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/mod-templates/mod-templates-v1.json"), "utf8"));
const schema = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/schemas/mms-mod-template-v1.schema.json"), "utf8"));
const scripts = [...html.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(match => match[1]);

for (let index = 0; index < scripts.length; index += 1) {
  assert.doesNotThrow(() => new Function(scripts[index]), "inline script " + index + " must parse");
}

const marker = "const MMT_CATALOG=";
const catalogStart = html.indexOf(marker) + marker.length;
const catalogEnd = html.indexOf(";\nconst MMT_COPY", catalogStart);
assert.ok(catalogStart >= marker.length && catalogEnd > catalogStart, "embedded catalog markers must exist");
const embeddedCatalog = JSON.parse(html.slice(catalogStart, catalogEnd));
assert.deepEqual(embeddedCatalog, catalog, "embedded browser catalog must match canonical JSON");

assert.equal(catalog.templates.length, 20);
assert.equal(schema.$defs.resource.allOf.length, 6, "resource schema must constrain all six resource kinds");
assert.equal(schema.$defs.relation.allOf.length, 2, "relation schema must require type-specific fields");

const coreScript = scripts.find(source => source.includes("const StudioCore ="));
const appScript = scripts.find(source => source.includes("function make(id,name"));
const templateScript = scripts.find(source => source.includes("const MMT_CATALOG="));
assert.ok(coreScript && appScript && templateScript, "required application modules must exist");

const StudioCore = new Function("StudioBehavior", "module", coreScript + "\nreturn StudioCore;")({}, undefined);

const makeStart = appScript.indexOf("function make(id,name,kind='blank')");
const makeEnd = appScript.indexOf("\nconst seed=", makeStart);
const resourceStart = appScript.indexOf("function sNew(kind,id,name)");
const resourceEnd = appScript.indexOf("\nfunction sMigrate()", resourceStart);
assert.ok(makeStart >= 0 && makeEnd > makeStart && resourceStart >= 0 && resourceEnd > resourceStart);

let uid = 0;
const newUid = () => "template_test_" + (++uid);
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const blank = () => Array(256).fill(null);
const sprite = () => Array(256).fill("#55aacc");
const defaultRig = () => ({ bones: [], texture: { width: 16, height: 16, painted: {} }, materials: [] });

const resourceFactorySource =
  appScript.slice(makeStart, makeEnd) + "\n" +
  appScript.slice(resourceStart, resourceEnd) + "\nreturn { make, sNew, sComponent };";
const resourceFactory = new Function("StudioCore", "newUid", "blank", "sprite", "defaultRig", "clamp", resourceFactorySource);
const { make, sNew, sComponent } = resourceFactory(StudioCore, newUid, blank, sprite, defaultRig, clamp);

const MMT_ALLOWED = {
  items: new Set(["kind", "damage", "durability", "rarity", "stack", "cooldown", "recipe", "behavior"]),
  blocks: new Set(["hardness", "resistance", "material", "color", "dropCount", "oreMode", "oreSize", "oreCount", "oreMinY", "oreMaxY", "oreReplace"]),
  mobs: new Set(["health", "attack", "speed", "body", "ai", "biome", "weight", "color", "drop", "dropCount"]),
  quests: new Set(["description", "objective", "count", "rewardCount"]),
  effects: new Set(["color", "category", "duration", "amplifier", "attribute", "modifier", "trigger"]),
  guis: new Set(["title", "theme", "components"])
};

const uniqueStart = templateScript.indexOf("function uniqueId(");
const uniqueEnd = templateScript.indexOf("\nfunction instantiate", uniqueStart);
const instantiateStart = templateScript.indexOf("function instantiate(", uniqueEnd);
const instantiateEnd = templateScript.indexOf("\nfunction applySelected", instantiateStart);
assert.ok(uniqueStart >= 0 && uniqueEnd > uniqueStart && instantiateStart > uniqueEnd && instantiateEnd > instantiateStart);

const instantiateFactorySource =
  "const MMT_COPY = value => JSON.parse(JSON.stringify(value));\n" +
  "const lang = 'zh-CN';\n" +
  templateScript.slice(uniqueStart, uniqueEnd) + "\n" +
  templateScript.slice(instantiateStart, instantiateEnd) + "\nreturn instantiate;";
const instantiateFactory = new Function(
  "StudioCore", "MMT_ALLOWED", "MMT_TEXT", "make", "sNew", "sComponent", "newUid", "clamp",
  instantiateFactorySource
);
const instantiate = instantiateFactory(
  StudioCore,
  MMT_ALLOWED,
  (value, language) => value?.[language] || value?.["zh-CN"] || "",
  make, sNew, sComponent, newUid, clamp
);

function createSource(id = "existing_item") {
  const seed = make(id, "Existing Item", "gem");
  seed.recipe = Array(9).fill("");
  seed.behavior = null;
  return {
    schemaVersion: 1,
    name: "Template Runtime Test",
    modId: "template_test",
    target: { loader: "fabric", minecraft: "26.2" },
    items: [seed]
  };
}

const source = createSource();
const sourceSnapshot = JSON.stringify(source);
const results = [];
for (const template of catalog.templates) {
  const result = instantiate(template, source, "zh-CN");
  assert.equal(result.validation.errors.length, 0, template.id + " must pass StudioCore validation");
  assert.equal(result.created.length, template.resources.length, template.id + " must create every declared resource");
  assert.notEqual(result.project, source, template.id + " must produce a candidate project copy");
  results.push(template.id);
}
assert.equal(JSON.stringify(source), sourceSnapshot, "instantiation must not mutate the source project");

const collisionResult = instantiate(catalog.templates.find(template => template.id === "basic-item"), createSource("new_item"), "zh-CN");
assert.equal(collisionResult.created[0].id, "new_item_2", "registry collisions must receive a deterministic suffix");

const oreTemplate = catalog.templates.find(template => template.id === "ore-vein");
const oreResult = instantiate(oreTemplate, source, "zh-CN");
const oreRefs = new Map(oreResult.created.map(resource => [resource.key, resource]));
const oreBlock = oreResult.project.studio.blocks.find(resource => resource.uid === oreRefs.get("ore_block").uid);
assert.equal(oreBlock.drop, oreRefs.get("raw_ore").uid, "drop relationship must resolve to the new item UID");

const recipeTemplate = catalog.templates.find(template => template.id === "crafted-crystal-blade");
const recipeResult = instantiate(recipeTemplate, source, "zh-CN");
const recipeRefs = new Map(recipeResult.created.map(resource => [resource.key, resource]));
const craftedWeapon = recipeResult.project.items.find(resource => resource.uid === recipeRefs.get("weapon").uid);
assert.equal(craftedWeapon.recipe[4], StudioCore.internal(recipeRefs.get("crystal").uid), "internal recipe references must resolve to the new material UID");

const malformed = JSON.parse(JSON.stringify(oreTemplate));
malformed.relations[0].to = "missing_resource";
assert.throws(() => instantiate(malformed, source, "zh-CN"), /relation endpoint|Missing template relationship endpoint|项目校验未通过|Project validation failed/i);
assert.equal(JSON.stringify(source), sourceSnapshot, "failed instantiation must leave the source project untouched");

console.log("OK: " + results.length + " templates instantiated and validated; catalog sync, script parsing, collision handling, relationships, and atomicity checks passed.");

const assert = require("node:assert/strict");
const { test } = require("node:test");
const { webcrypto } = require("node:crypto");

global.window = global;
global.crypto = webcrypto;

require("../mms_project_operator_api.js");

const project = {
  schemaVersion: 3,
  name: "Example Mod",
  modId: "example_mod",
  target: { loader: "fabric", minecraft: "26.2" },
  items: [{
    uid: "uid-sword",
    id: "sword",
    name: "Storm Sword",
    kind: "sword",
    damage: 8,
    pixels: ["#ffffff", null]
  }],
  resourceOverrides: [],
  studio: {
    blocks: [],
    mobs: [],
    quests: [],
    effects: [],
    guis: [],
    links: {}
  }
};

const jsonBytes = new TextEncoder().encode(JSON.stringify({
  parent: "minecraft:item/generated",
  textures: { layer0: "example_mod:item/sword" }
}));

const archives = [{
  id: "archive-1",
  name: "example-mod.jar",
  meta: {
    id: "example_mod",
    loader: "fabric",
    version: "1.2.0",
    license: "MIT (unverified claim)"
  },
  total: jsonBytes.length,
  skipped: 0,
  licenses: [],
  entries: [{
    path: "assets/example_mod/models/item/sword.json",
    bytes: jsonBytes
  }, {
    path: "assets/example_mod/textures/item/sword.png",
    bytes: Uint8Array.from([137, 80, 78, 71])
  }]
}];

const Core = {
  encode(value) { return JSON.stringify(value); },
  validate() { return { errors: [], warnings: ["sample warning"] }; }
};
const Compiler = {
  analyze() { return { errors: [], warnings: [], omitted: ["quests/demo"] }; }
};
const Resources = {
  kind(path) {
    if (path.endsWith(".png")) return "纹理";
    if (path.includes("/models/")) return "模型";
    if (path.endsWith(".json")) return "JSON";
    return "其他";
  },
  refs(_path, bytes) {
    const parsed = JSON.parse(new TextDecoder().decode(bytes));
    return [parsed.textures.layer0];
  },
  decode(bytes) { return new TextDecoder().decode(bytes); },
  crc() { return 0x1234abcd; },
  un64(value) { return Uint8Array.from(Buffer.from(value, "base64")); }
};

function createApi(overrides = {}) {
  return global.MMSProjectOperatorFactory({
    getProject: () => overrides.project || project,
    getArchives: () => overrides.archives || archives,
    getDatabase: () => ({}),
    ready: Promise.resolve(),
    core: Core,
    compiler: Compiler,
    resources: Resources
  });
}

test("snapshot returns project counts, validation and deterministic SHA-256 revision", async () => {
  const api = createApi();
  const snapshot = await api.snapshot();
  assert.equal(snapshot.project.modId, "example_mod");
  assert.equal(snapshot.counts.items, 1);
  assert.equal(snapshot.counts.importedArchives, 1);
  assert.equal(snapshot.counts.importedResources, 2);
  assert.equal(snapshot.validation.warnings[0], "sample warning");
  assert.equal(snapshot.buildAnalysis.omitted[0], "quests/demo");
  assert.match(snapshot.revision, /^[0-9a-f]{64}$/);
  assert.equal(snapshot.trust.archiveMetadata, "unverified_claims");
});

test("search ranks matching project definitions and imported resource paths", async () => {
  const api = createApi();
  const result = await api.search({ query: "sword", scope: "all", limit: 10 });
  assert.ok(result.results.some(row =>
    row.resultType === "project_object" && row.id === "sword"
  ));
  assert.ok(result.results.some(row =>
    row.resultType === "imported_resource" && row.path.endsWith("sword.json")
  ));
});

test("search bounds result count and rejects malformed filters", async () => {
  const api = createApi();
  await assert.rejects(api.search({ query: "", limit: 10 }));
  await assert.rejects(api.search({ query: "sword", limit: 51 }));
  await assert.rejects(api.search({ query: "sword", scope: "filesystem" }));
});

test("resource inspection returns bounded text and marks mod content untrusted", async () => {
  const api = createApi();
  const result = await api.inspectResource({
    archiveId: "archive-1",
    path: "assets/example_mod/models/item/sword.json"
  });
  assert.equal(result.kind, "模型");
  assert.match(result.content, /minecraft:item\/generated/);
  assert.deepEqual(result.references, ["example_mod:item/sword"]);
  assert.equal(result.contentTrust, "untrusted_mod_supplied_data");
  assert.equal(result.sourceMetadataUnverified, true);
});

test("binary resource inspection never returns image bytes", async () => {
  const api = createApi();
  const result = await api.inspectResource({
    archiveId: "archive-1",
    path: "assets/example_mod/textures/item/sword.png"
  });
  assert.equal(result.binaryContentOmitted, true);
  assert.equal(Object.hasOwn(result, "content"), false);
});

test("staged project resource overrides can be inspected without persistence", async () => {
  const bytes = new TextEncoder().encode('{"parent":"minecraft:item/generated"}');
  const staged = {
    ...project,
    resourceOverrides: [{
      path: "assets/example_mod/models/item/staged.json",
      base64: Buffer.from(bytes).toString("base64"),
      source: { archive: "source.jar", license: "unknown" }
    }]
  };
  const api = createApi({ project: staged });
  const result = await api.inspectResource({
    archiveId: "project",
    path: "assets/example_mod/models/item/staged.json"
  });
  assert.match(result.content, /minecraft:item\/generated/);
  assert.equal(result.archiveId, "project");
});

test("project object inspection strips oversized visual payloads", async () => {
  const largeProject = {
    ...project,
    items: [{
      ...project.items[0],
      pixels: Array.from({ length: 30000 }, () => "#ffffff")
    }]
  };
  const api = createApi({ project: largeProject });
  const result = await api.inspectProjectObject({
    collection: "items",
    id: "sword"
  });
  assert.equal(result.detailsTruncated, true);
  assert.equal(result.object.pixels.pixelCount, 30000);
  assert.equal(result.object.pixels.detailOmitted, true);
});

test("project object inspection rejects unknown collection and missing object", async () => {
  const api = createApi();
  await assert.rejects(api.inspectProjectObject({
    collection: "unknown",
    id: "sword"
  }));
  await assert.rejects(api.inspectProjectObject({
    collection: "items",
    id: "missing"
  }));
});

# V0.8 — Minecraft Mod Studio V25 integration audit

Date: 2026-11-21  
Target source: `Minecraft_Mod_Studio_V25.html`  
Target blob: `cb10de80d28bdef5e2da7fa73065624a93466d73`  
Research branch: `research/extension-engine`

## Executive finding

The extension engine is **not yet integrated** with the actual V25 editor. The V25 source is a standalone HTML application with substantial internal APIs, but its project state and most service objects remain private to inline-script closures. The correct next step is a narrow host bridge and declarative contribution adapter, not a general executable-plugin runtime.

The V25 source snapshot was merged from main into this research branch through PR #11. The merge target was `research/extension-engine`; main was not modified. The branch now compares as 54 commits ahead and 0 behind main.

## Observed V25 architecture

### 1. Project state and persistence
- `StudioCore` owns project migration, validation, encoding, loading, commit and backup operations.
- The project save path calls `StudioCore.commit(localStorage, project, storageState.raw, ...)`.
- The save contract compares the expected raw storage envelope before writing and rejects a changed revision, protecting against a stale tab overwriting a newer save.
- The project save store is localStorage with a head/previous snapshot envelope; it is not the extension engine's IndexedDB catalog.
- The editor's project object and save functions are scoped inside the application script rather than exposed as a documented extension API.

### 2. Separate resource-library persistence
- The resource-library panel opens IndexedDB database `minecraft-mod-studio-resource-library-v1`, object store `archives`.
- It persists imported resource archives and tracks source provenance.
- This database is not an extension catalog and has a different data model from `PersistentExtensionStore`.
- Reusing its object store for package records or content-addressed blobs would couple unrelated schemas and should be avoided.

### 3. Existing editor services
- `StudioBehavior` provides a typed, bounded control-flow graph and function validation/evaluation logic.
- `StudioCore` provides project-level data validation and persistence contracts.
- `StudioCompiler` provides deterministic Fabric source/resource packaging and validation output.
- The V25 UI exposes project editing, behavior editing, recipes, textures, resource overrides and a local build/export workflow.
- The source explicitly indicates that a local build is required; the browser editor is not itself proof that a generated mod compiles or runs in Minecraft.
- These services are internal lexical bindings; the only obvious public window-level service found in the inspected source is a trace/diagnostic interface, not a general extension API.

## Integration gaps

| Area | Extension-engine state | V25 state | Gap |
|---|---|---|---|
| Package catalog | Persistent package records | No extension catalog UI | Host bridge and UI required |
| Package persistence | Dedicated KV/IndexedDB backend | Separate localStorage project store and resource-library IndexedDB | Keep storage schemas isolated |
| Contributions | template / blueprint / recipe data contracts | Existing editor models and validation | Explicit mapping and schema validation required |
| Permissions | Package permission grants | No extension permission review UI | User-consent UI required |
| Publisher trust | Ed25519 API and opt-in install gate | No visible publisher trust surface | Display signer, scope, expiry and revocation status |
| Activation | Data-only registry and package state | No documented dynamic contribution API | Controlled host activation contract |
| Build output | Staged host-tool prototype | V25 compiler and local build/export workflow | Adapter and output regression tests |
| Runtime safety | No executable plugin runtime | Existing typed behavior graph | Preserve data-only extension boundary |

## Recommended integration architecture

1. **Do not execute package-supplied JavaScript.** Continue to accept only validated manifests and static assets.
2. Add a small, explicit `StudioExtensionHost` bridge inside the V25 application scope. It should expose only the operations required by the extension engine, not the entire project object or arbitrary compiler internals.
3. Keep package catalog and content-addressed blobs in a dedicated IndexedDB database. Do not reuse the resource-library `archives` object store.
4. Map contribution types to concrete V25 concepts through versioned schemas. Reject unsupported contribution types rather than silently accepting inert records.
5. Apply contributions through staged project snapshots and existing validation. A failed host validation must leave the live project unchanged.
6. Add a feature flag defaulting off. The first integration should support browsing, installing, permission review, enabling/disabling and uninstalling data-only packages before enabling project mutation.
7. Require publisher signatures for remote/marketplace packages. Keep unsigned local development packages as a separately labelled development mode.
8. Persist signer identity and verification evidence, and re-check against the latest trusted revocation state before activation.
9. Test in a real browser: reload, two tabs, IndexedDB abort/quota behavior, signature rejection, project save/restore, extension rollback and editor regression.
10. Require a local Fabric build and Minecraft fixture test before claiming an extension contribution is game-compatible.

## Proposed staged delivery

- **V0.8-A — Host bridge contract:** define stable capability API, version negotiation, project snapshot boundary and feature flag.
- **V0.8-B — Catalog UI:** installed packages, status, publisher identity, permission review, enable/disable and uninstall.
- **V0.8-C — First real contribution:** select one contribution type supported by V25, map it to an existing editor model, and test import/export round-trip.
- **V0.8-D — Browser acceptance:** real IndexedDB, multi-tab, reload, failure recovery and signature-required install.
- **V0.8-E — Game validation:** build the generated Fabric project and load it in a Minecraft test instance.

## Non-claims

This is a source-level integration audit. It does not establish successful browser execution, working extension UI, successful Fabric compilation, or Minecraft in-game behavior. No V25 editor source file was modified in this audit.

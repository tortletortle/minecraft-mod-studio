# MMS Extension Engine V0.8-B — V25 extension manager integration

Date: 2026-11-21  
Branch: `research/extension-engine`

## Delivered

### 1. Standalone V25 integration
- Added a self-contained browser runtime bundle at `v25-extension-runtime.js`, assembled from the existing package manager, strict archive reader/writer, persistent store, publisher-trust API and V25 host bridge.
- Added `v25-extension-manager.js` and embedded both scripts into `Minecraft_Mod_Studio_V25.html` between explicit integration markers.
- Added `build-v25-integration.mjs` so the embedded HTML copy can be regenerated from the maintained source files.
- V25 remains a single HTML file for normal use; the research source files and tests remain in the repository.

### 2. Local extension lifecycle UI
- Added a new `🧩 扩展` control in the existing V25 top action bar.
- The manager uses a dedicated IndexedDB database: `minecraft-mod-studio-extension-store-v1`.
- Supports strict local .mmse import, catalog refresh, explicit enable/disable, uninstall, staged catalog commit and orphaned content-addressed blob collection.
- Newly installed packages remain disabled.
- Enabling a package presents the declared permission list and requires explicit user confirmation.
- The UI labels imported packages as local and unsigned. Remote marketplace installation is not exposed.
- Added an explicit recovery action for prepared but unfinished install transactions; it warns the user to close other tabs first because recovery aborts all prepared journals in that catalog.

### 3. First real V25 contribution adapter: recipe templates
- Added a strict V25 adapter for `recipe` contributions.
- Contribution data must contain a name and exactly nine ingredient slots. Ingredients may be namespaced game resource IDs or V25 internal item references in the form `@item:<uid>`; resource IDs and internal UIDs are validated, traversal-like path segments and prototype-sensitive UIDs are rejected, and internal references must resolve to an existing project item before commit.
- Only active packages publish recipe contributions in the manager.
- Applying a recipe template stages a copy of the current project, changes the selected item's existing `recipe` array, and commits through the V25 host bridge.
- The bridge runs `StudioCore.migrate`, `StudioCore.validate` and `StudioCore.encode`, preserves the current item selection, and rejects stale plans.
- Applying a template modifies the unsaved project draft only; the existing V25 Save action remains authoritative.

### 4. Example package
Added `examples/recipe-pack/manifest.json`, `build.mjs` and `README.md`. The example builds a local `.mmse` package with two 3×3 recipe templates (diamond sword and golden apple) using the existing archive writer.

## Verification evidence

| Check | Result | Qualification |
|---|---:|---|
| Real Chromium happy-path acceptance | **2/2 runs passed** | GitHub Actions; real browser IndexedDB, local `.mmse` file-input import, project save/reload and uninstall |
| Extension runtime | 9/9 | V8 harness; in-memory KV backend |
| V25 manager end-to-end flow | Passed | Simulated DOM + IndexedDB transaction mock; actual V25 StudioCore |
| StudioCore validation after recipe application | 0 errors / 0 warnings | Deterministic fixture with nonblank textures |
| Manager source syntax | Passed | V8 parse check |
| Standalone HTML embedding | Passed | Exact runtime and manager source strings found inside V25 HTML |

The deterministic manager simulation performed: open manager → generate/import demo .mmse → enable global feature flag → approve `recipe.register` → activate package → display two recipe contributions → apply the diamond-sword template. The selected item's recipe changed, the host bridge incremented project generation, and actual V25 `StudioCore.validate` returned no errors or warnings. A separate actual-StudioCore check confirmed that a project-local `@item:item-2` reference resolves to the intended project item and remains valid after commit.

Two separate GitHub Actions Chromium runs passed. [Run #44896241981](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44896241981) exercised the built-in demo path; [run #44896416380](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44896416380) built an actual `.mmse` archive from the example manifest and imported it through the file input. Both used real Chromium and real IndexedDB, applied the recipe, saved the project, reloaded the page, verified the recipe and active package survived, then uninstalled the package. Both reported zero `StudioCore` validation errors and zero uncaught page errors.

## Security and scope limits

- The manager accepts local files only and does not claim publisher authentication. Local packages are unsigned and must be treated as untrusted input.
- The runtime never executes package-supplied JavaScript.
- Only the `recipe` contribution type is applied in V25. `template` and `blueprint` data can be stored but do not yet have V25 adapters.
- Static asset blobs can be stored and deduplicated, but the V25 manager does not yet apply them to project resources.
- Publisher trust roots, detached signatures and revocation verification are not yet wired into the V25 UI. The persistent store's signature-required mode remains opt-in.
- The deterministic manager unit harness still uses a fake DOM and IndexedDB transaction mock; the separate Chromium acceptance runs establish the normal single-tab browser path, not multi-tab safety.
- No local Fabric build or Minecraft in-game test was performed.

## Next acceptance gates

1. Exercise two-tab writers, transaction aborts, quota errors and abrupt page termination in real browsers.
2. Add Firefox/WebKit acceptance and adversarial archive fixtures.
3. Integrate pinned publisher roots and mandatory signatures for any future remote package source.
4. Implement template, blueprint and static-asset contribution adapters with round-trip project tests.
5. Run V25 regression and a local Fabric build, then validate the generated mod in a Minecraft test instance.

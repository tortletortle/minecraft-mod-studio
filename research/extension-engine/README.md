# MMS Extension Engine — research branch

**Purpose:** Add independently installable, data-only extensions to Minecraft Mod Studio without continuously modifying the editor core.

## Current status

- **V0.1:** in-memory, data-only contribution registry.
- **V0.2:** staged project-mutation contract and structure-generation request adapter.
- **V0.3:** dependency resolver, atomic install/uninstall, permission grants, upgrades, rollback and manifest lockfile.
- **V0.4:** strict ZIP/.mmse reader for data-only manifests and static assets.
- **V0.5:** deterministic stored-ZIP writer, full-archive SHA-256 lockfile and content-addressed asset index.
- **V0.6:** persistent catalog and asset blobs, staged transaction journal, recovery, rollback and garbage collection; IndexedDB backend implemented.
- **V0.7:** Ed25519 publisher certificates, detached whole-archive signatures, pinned trust roots, root-signed revocation statements, and an opt-in signature-required install gate with persisted publisher provenance.
- **V0.8 audit:** V25 source-level architecture and integration-boundary audit.
- **V0.8-A:** V25 host bridge with defensive snapshots, staged validation, explicit approval, stale-plan detection and rollback.
- **V0.8-B:** actual V25 extension manager integration. Standalone V25 HTML embeds the tested runtime and UI. Supports local .mmse import, separate IndexedDB catalog, enable/disable/uninstall, explicit permission review, garbage collection, and the first V25 contribution adapter: 3×3 recipe templates.

**Not yet accepted:** real-browser IndexedDB and multi-tab behavior, signed publisher verification in the V25 UI, remote marketplace installation, template/blueprint contribution adapters, arbitrary asset activation, Fabric build acceptance, and Minecraft in-game validation.

## Compatibility baseline

The current main branch baseline is `8e8703875131c60b3bf2440c2dd8f44ae8c616a9`. Main was merged into `research/extension-engine` through PR #11 (merge commit `6771a650c7a91be4b5a40ebe3d88b929675fe8a3`). The research branch compares as ahead of main and **0 commits behind** at the latest check; the exact ahead count changes with each research commit. V25 editor integration changes remain isolated on this research branch; nothing from this branch has been merged into main.

The research branch's V25 HTML is self-contained (current blob `cb00539217e7b99ef15978cadaff55e7040d26ac`) and embeds the extension runtime and manager between explicit integration markers. The maintainable source files remain `v25-extension-runtime.js` and `v25-extension-manager.js`; regenerate the embedded copy after editing either source:

```sh
node research/extension-engine/build-v25-integration.mjs
```

## Architecture and security decisions

1. Git branches isolate research development; the eventual extension mechanism is product-level package installation.
2. L1 packages contain inert JSON data and static assets only. Package-supplied JavaScript is never executed.
3. Manifest SDK version is pinned to 0.1.0. Dependencies use exact version pins.
4. Resolve and validate the complete dependency graph before state mutation.
5. Batch catalog changes commit atomically; stale plans fail by revision checks.
6. New packages remain disabled until explicit permission grants.
7. ZIP CRC-32 detects entry corruption; SHA-256 lockfiles detect byte changes relative to a trusted lockfile. Hashes alone do not authenticate publishers.
8. The .mmse writer emits deterministic stored ZIP entries; compression is not currently implemented.
9. Content-addressed asset blobs deduplicate identical bytes.
10. Project edits use staged snapshots and the existing V25 `StudioCore.migrate / validate / encode` path. The bridge preserves the selected item and leaves saving to the user's existing Save action.
11. The V25 extension catalog uses its own IndexedDB database, `minecraft-mod-studio-extension-store-v1`; it does not reuse the editor's localStorage project envelope or the resource library's IndexedDB schema.
12. The first V25 contribution adapter supports only `recipe`: a named, validated nine-slot ingredient array mapped to the selected item's existing `recipe` field. Ingredients can reference namespaced game items or existing project items via `@item:<uid>`; project references are resolved before commit. Other contribution types remain inert until dedicated adapters exist.
13. The V25 manager accepts local .mmse files only. Imports are labelled unsigned; no remote marketplace path is exposed.
14. Publisher public-key IDs are SHA-256 hashes of raw Ed25519 public keys. Publisher certificates are signed by host-pinned trust roots and constrained by validity windows and package scopes.
15. Package signatures cover a domain-separated canonical message containing package ID, version, signer key ID and SHA-256 of the complete .mmse archive. Signature and certificate metadata are detached from the archive to preserve the .mmse v1 format.
16. Revocation statements are root-signed. A key is rejected when its matching revocation is effective. The host must supply current revocation data; no signed feed or anti-rollback sequence is implemented yet.
17. Trust-root rotation is an out-of-band host update. A root cannot make itself trusted merely by signing a replacement root.
18. Signature verification in `PersistentExtensionStore` is opt-in via `requireSignatures: true`; the backward-compatible default permits unsigned local development packages. The V25 local manager currently uses this local-development path and does not yet wire in publisher trust roots.
19. A valid publisher signature establishes provenance and archive integrity relative to a trusted key; it does not prove the package is benign. The data-only/no-executable-code restriction remains in force.

## Reproducible commands

Run from the repository root with Node.js 22+:

```sh
# Existing engine suites
node research/extension-engine/registry.test.mjs
node research/extension-engine/host-tools.test.mjs
node research/extension-engine/package-manager.test.mjs
node research/extension-engine/archive.test.mjs
node research/extension-engine/archive-writer.test.mjs
node research/extension-engine/persistent-store.test.mjs
node research/extension-engine/publisher-trust.test.mjs
node research/extension-engine/v25-host-bridge.test.mjs

# V25 browser-runtime and manager integration suites
node research/extension-engine/v25-extension-runtime.test.mjs
node research/extension-engine/v25-extension-manager.test.mjs

# Rebuild the standalone V25 HTML after changing integration source
node research/extension-engine/build-v25-integration.mjs

# Build the example local recipe package
node research/extension-engine/examples/recipe-pack/build.mjs
```

## Verification evidence (2026-11-21)

- Existing branch suites: **219/219 passed** in the V8 harness (24 registry + 33 host transaction + 47 package manager + 39 archive reader + 35 writer/lockfile/asset-index + 41 persistent-store).
- Publisher trust: **30/30 passed** in Node 22.16.0 using native WebCrypto Ed25519; certificate issuance, signing, tampering, scope/expiry checks, revocation and key rotation were exercised.
- V25 host bridge contract: **17/17 passed** in the V8 harness.
- V25 extension runtime: **9/9 passed** in the V8 harness, including safe internal-item references and dangling-reference rejection. The committed Node suite groups these into eight reproducible test scenarios. Coverage includes MMSE round-trip, install-disabled default, permission grant, contribution filtering, recipe mutation, stale-plan rejection and malformed-input rejection.
- V25 manager flow: an end-to-end simulated DOM + IndexedDB transaction harness completed local demo-package installation, permission grant, two recipe contributions, and recipe application through the actual V25 `StudioCore`. The resulting project had **0 validation errors and 0 warnings** in that fixture.
- The V25 HTML embeds the exact runtime and manager source blobs and remains a single-file editor artifact. The integration build script can regenerate the embedded block.
- The writer-generated 549-byte .mmse fixture passed Python's standard-library ZIP reader (`ZipFile.testzip()` returned no corrupt member).

**Qualification:** the manager harness uses a fake DOM and a deterministic IndexedDB transaction mock. It is not real Chromium/Firefox acceptance and does not establish real browser persistence, cross-tab coordination, quota behavior, crash recovery, or browser Deflate interoperability. The persistent-store suite also exercises the in-memory backend. Real browser tests and Minecraft game tests remain outstanding.

## Next acceptance gates

1. Run the self-contained V25 HTML in a real browser. Test IndexedDB close/reopen, reload, local .mmse import, permission grant, enable/disable/uninstall, recipe application, project save/export/import and failure recovery.
2. Test concurrent tabs, transaction aborts, quota errors and interrupted installation recovery.
3. Wire host-pinned publisher roots and mandatory signatures for any future remote/marketplace source; keep local unsigned development imports visibly labelled.
4. Add dedicated adapters and schema tests for template, blueprint and static-asset contributions.
5. Run V25 editor regression, local Fabric build, generated project import/export fixtures and Minecraft in-game validation before considering a main-branch merge.

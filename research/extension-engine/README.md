# MMS Extension Engine — research branch

**Purpose:** Add future capabilities to Minecraft Mod Studio as independently installable extensions, without continuously modifying the editor core.

## Current status
- **V0.1:** in-memory data-only contribution registry.
- **V0.2:** staged project mutation contract and structure-generation request adapter.
- **V0.3:** local package dependency resolver, atomic install/uninstall, explicit permission grants, upgrade/rollback and SHA-256 lockfile.
- **Not implemented:** ZIP/.mmse archive import/export, persistent catalog, remote package sources, publisher signatures, executable plugins, browser sandbox, real Studio UI integration.

## Compatibility baseline
The current main branch moved to commit b249e564cbb3b482bd7668817fe337e665b43c72 to archive the original V2.3 standalone HTML. The V2.5 editor source blob is still a0e47c2b137679475e5a3325314c2acc42c8fa6f, identical to the source blob in this research branch. The extension work remains isolated; no merge or main-branch editor change was made.

## Architecture decisions
1. Git branches isolate development; installed extensions are the eventual product-level expansion mechanism.
2. L1 packages contain inert JSON data only. No arbitrary JS execution.
3. Manifest SDK version is pinned to 0.1.0. Dependencies use exact version pins, not ranges.
4. Resolve the complete dependency graph and validate it before any state mutation.
5. Batch changes commit atomically and stale plans fail by generation check.
6. New packages remain disabled until explicit permission grants.
7. Hash lockfiles detect content changes relative to a trusted lockfile; they do not authenticate publishers.
8. Project edits use staged snapshots and host validation. The host adapter remains a prototype, not integrated with the browser editor.
9. Structure generation is a separate service contract. NBT is not a supported V2.5 resource override and must not be inserted there.

## Reproducible tests
Run from the repository root with Node.js 18+:

    node research/extension-engine/registry.test.mjs
    node research/extension-engine/host-tools.test.mjs
    node research/extension-engine/package-manager.test.mjs

The source and test files were re-read from GitHub and all 101 scenarios were executed in the V8 harness: 24 registry + 33 host transaction + 44 package manager. Node CLI execution, browser integration and Minecraft game tests remain outstanding.

## Next
- V0.4: strict ZIP/.mmse archive reader; path traversal, symlink, duplicate path, malformed local/central directory, CRC and decompression-bomb defenses.
- V0.5: persistent catalog and crash-safe recovery journal.
- V0.6: publisher signatures and trust roots.
- Later: editor UI integration and isolated L2/L3 runtimes after security and regression gates.
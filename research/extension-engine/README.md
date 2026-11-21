# MMS Extension Engine — research branch

**Purpose:** Add future capabilities to Minecraft Mod Studio as independently installable extensions, without continuously modifying the editor core.

## Current status
- **V0.1:** in-memory data-only contribution registry.
- **V0.2:** staged project mutation contract and structure-generation request adapter.
- **V0.3:** local dependency resolver, atomic install/uninstall, permission grants, upgrades, rollback and manifest lockfile.
- **V0.4:** strict ZIP/.mmse reader for data-only manifests and static assets.
- **Not implemented:** .mmse writer, persistent catalog, remote sources, full-archive SHA-256 lock, publisher signatures, executable plugins, browser sandbox, real Studio UI integration.

## Compatibility baseline
The current main branch is b249e564cbb3b482bd7668817fe337e665b43c72. The V2.5 editor source blob remains a0e47c2b137679475e5a3325314c2acc42c8fa6f, identical to the source blob in this research branch. Extension work remains isolated; no merge or main-branch editor change was made.

## Architecture decisions
1. Git branches isolate development; installed extensions are the eventual product-level expansion mechanism.
2. L1 packages contain inert JSON data and static assets only. No arbitrary JS execution.
3. Manifest SDK version is pinned to 0.1.0. Dependencies use exact version pins, not ranges.
4. Resolve the complete dependency graph and validate it before any state mutation.
5. Batch changes commit atomically; stale plans fail by generation check.
6. New packages remain disabled until explicit permission grants.
7. Current lockfile hashes exact manifest bytes only. ZIP CRC-32 detects accidental entry corruption but is not publisher authentication; full archive hashing and signatures remain pending.
8. Project edits use staged snapshots and host validation. The host adapter remains a prototype, not integrated with the browser editor.
9. Structure generation is a separate service contract. NBT is not a supported V2.5 resource override and must not be inserted there.

## Reproducible tests
Run from the repository root with Node.js 18+:

    node research/extension-engine/registry.test.mjs
    node research/extension-engine/host-tools.test.mjs
    node research/extension-engine/package-manager.test.mjs
    node research/extension-engine/archive.test.mjs

The committed source and tests were re-read from GitHub and executed in the V8 harness: 140/140 scenarios passed (24 registry + 33 host transaction + 44 package manager + 39 archive). Node CLI execution, actual browser Deflate decompression, editor integration and Minecraft game tests remain outstanding.

## Next
- V0.5: actual Deflate interoperability and a controlled .mmse writer.
- V0.6: persistent catalog, crash-safe recovery journal and full archive hashes.
- V0.7: publisher signatures and trust roots.
- Later: editor UI integration and isolated L2/L3 runtimes after security and regression gates.
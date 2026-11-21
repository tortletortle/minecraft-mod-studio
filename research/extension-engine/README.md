# MMS Extension Engine — research branch

**Purpose:** Add future capabilities to Minecraft Mod Studio as independently installable extensions, without continuously modifying the editor core.

## Current status
- **V0.1:** in-memory data-only contribution registry.
- **V0.2:** staged project mutation contract and structure-generation request adapter.
- **V0.3:** local dependency resolver, atomic install/uninstall, permission grants, upgrades, rollback and manifest lockfile.
- **V0.4:** strict ZIP/.mmse reader for data-only manifests and static assets.
- **V0.5:** deterministic stored-ZIP writer, full-archive SHA-256 lockfile (schema 2), and content-addressed asset index with duplicate-blob elimination.
- **Not implemented:** persistent catalog, crash-safe disk journal, remote sources, publisher signatures/trust roots, executable plugins, browser sandbox, real Studio UI integration.

## Compatibility baseline
The current main branch is b249e564cbb3b482bd7668817fe337e665b43c72. The V2.5 editor source blob remains a0e47c2b137679475e5a3325314c2acc42c8fa6f, identical to the source blob in this research branch. Extension work remains isolated; no merge or main-branch editor change was made.

## Architecture decisions
1. Git branches isolate development; installed extensions are the eventual product-level expansion mechanism.
2. L1 packages contain inert JSON data and static assets only. No arbitrary JS execution.
3. Manifest SDK version is pinned to 0.1.0. Dependencies use exact version pins, not ranges.
4. Resolve the complete dependency graph and validate it before any state mutation.
5. Batch changes commit atomically; stale plans fail by generation check.
6. New packages remain disabled until explicit permission grants.
7. Schema-1 lockfiles hash exact manifest bytes; schema-2 .mmse lockfiles hash the complete archive bytes. Neither hash format authenticates the publisher.
8. ZIP CRC-32 detects accidental entry corruption; SHA-256 lockfiles detect archive-byte changes relative to a trusted lockfile.
9. Content-addressed asset indexes deduplicate identical bytes in memory. They are staging metadata, not yet a persistent asset store.
10. Project edits use staged snapshots and host validation. The host adapter remains a prototype, not integrated with the browser editor.
11. Structure generation is a separate service contract. NBT is not a supported V2.5 resource override and must not be inserted there.

## Reproducible tests
Run from the repository root with Node.js 18+:

    node research/extension-engine/registry.test.mjs
    node research/extension-engine/host-tools.test.mjs
    node research/extension-engine/package-manager.test.mjs
    node research/extension-engine/archive.test.mjs
    node research/extension-engine/archive-writer.test.mjs
    node research/extension-engine/persistent-store.test.mjs
    node research/extension-engine/archive-writer.test.mjs

The committed source and tests were re-read from GitHub and executed in the V8 harness: **209/209 scenarios passed** (24 registry + 33 host transaction + 47 package manager + 39 archive reader + 35 writer/lockfile/asset index + 31 persistent-store). A writer-generated 549-byte .mmse fixture also passed an independent Python standard-library ZIP reader: `ZipFile.testzip()` returned no corrupt member, and its manifest and README decoded correctly. The 31 persistent-store tests exercise the in-memory transactional backend; real IndexedDB/browser concurrency and crash recovery, Node CLI execution, browser Deflate decompression, editor integration and Minecraft game tests remain outstanding.

## Next
- **V0.6:** persistent content-addressed asset store, catalog metadata and crash-safe install journal; atomic recovery tests.
- **V0.7:** publisher signatures, trust roots and revocation policy.
- **Later:** browser/editor integration behind a feature flag, then Studio V2.5 regression and Minecraft fixture validation before any main-branch merge.

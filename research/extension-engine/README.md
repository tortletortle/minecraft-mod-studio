# MMS Extension Engine — research branch

**Purpose:** Add independently installable extension capabilities to Minecraft Mod Studio without continuously modifying the editor core.

## Current status
- **V0.1:** in-memory, data-only contribution registry.
- **V0.2:** staged project-mutation contract and structure-generation request adapter.
- **V0.3:** dependency resolver, atomic install/uninstall, permission grants, upgrades, rollback and manifest lockfile.
- **V0.4:** strict ZIP/.mmse reader for data-only manifests and static assets.
- **V0.5:** deterministic stored-ZIP writer, full-archive SHA-256 lockfile and content-addressed asset index.
- **V0.6:** persistent catalog and asset blobs, staged transaction journal, recovery, rollback and garbage collection; IndexedDB backend implemented but not yet exercised in a real browser.
- **V0.7:** Ed25519 publisher certificates, detached whole-archive signatures, pinned trust roots, root-signed revocation statements, and an opt-in signature-required install gate with persisted publisher provenance.
- **V0.8 audit:** V25 source-level integration audit; host bridge, storage boundaries, contribution mapping and browser acceptance gates documented.
- **V0.8-A:** isolated V25 host bridge contract with defensive snapshots, staged validation, explicit commit approval, stale-plan detection and rollback. It is tested but not yet wired into the V25 HTML.

**Not implemented:** real browser/IndexedDB acceptance, cross-tab coordination, signed revocation-feed distribution and anti-rollback, publisher key provisioning/secure storage, automated trust-root rotation, remote catalog/marketplace, real Studio UI integration, executable plugins, browser sandbox, and Minecraft in-game validation.

## Compatibility baseline
Current main branch: `8e8703875131c60b3bf2440c2dd8f44ae8c616a9`. Main was merged into `research/extension-engine` through PR #11 (merge commit `6771a650c7a91be4b5a40ebe3d88b929675fe8a3`); the research branch now compares as 54 commits ahead / 0 behind main. The V25 source snapshot is present at blob `cb10de80d28bdef5e2da7fa73065624a93466d73`. This sync changed only the research branch; extension-engine work has not been merged into main. V25 compatibility remains unverified until browser integration and regression tests are completed.

## Architecture decisions
1. Git branches isolate research development; the eventual extension mechanism is product-level package installation.
2. L1 packages contain inert JSON data and static assets only. No arbitrary JavaScript execution.
3. Manifest SDK version is pinned to 0.1.0. Dependencies use exact version pins.
4. Resolve and validate the complete dependency graph before state mutation.
5. Batch changes commit atomically; stale plans fail by revision checks.
6. New packages remain disabled until explicit permission grants.
7. ZIP CRC-32 detects entry corruption; SHA-256 lockfiles detect byte changes relative to a trusted lockfile. Hashes alone do not authenticate publishers.
8. The .mmse writer emits deterministic stored ZIP entries; compression is not currently implemented.
9. Content-addressed asset blobs deduplicate identical bytes.
10. Project edits use staged snapshots and host validation. The host adapter remains a prototype, not integrated with the browser editor.
11. Structure generation is a separate service contract. NBT is not a supported V2.5 resource override.
12. Publisher public-key IDs are SHA-256 hashes of raw Ed25519 public keys. Publisher certificates are signed by host-pinned trust roots and are constrained by validity windows and package scopes.
13. Package signatures cover a domain-separated canonical message containing package ID, version, signer key ID and SHA-256 of the complete .mmse archive. Signature and certificate metadata are detached from the archive to preserve the .mmse v1 format.
14. Revocation statements are root-signed. A key is rejected when its matching revocation is effective. The host must supply current revocation data; no signed feed or anti-rollback sequence is implemented yet.
15. Trust-root rotation is an out-of-band host update. A root cannot make itself trusted merely by signing a replacement root.
16. Signature verification in `PersistentExtensionStore` is opt-in via `requireSignatures: true`; the backward-compatible default still permits unsigned local packages. Production UI integration must explicitly enable the mandatory policy.
17. A valid publisher signature establishes provenance and archive integrity relative to a trusted key; it does not prove the package is benign. The data-only/no-executable-code restriction remains in force.

## Reproducible tests
Run from the repository root with Node.js 22+ (the publisher trust suite requires Ed25519 WebCrypto):

```sh
node research/extension-engine/registry.test.mjs
node research/extension-engine/host-tools.test.mjs
node research/extension-engine/package-manager.test.mjs
node research/extension-engine/archive.test.mjs
node research/extension-engine/archive-writer.test.mjs
node research/extension-engine/persistent-store.test.mjs
node research/extension-engine/publisher-trust.test.mjs
node research/extension-engine/v25-host-bridge.test.mjs
```

## Verification evidence (2026-11-21)
- Existing branch suites were re-read from GitHub and executed in the V8 harness: **219/219 passed** (24 registry + 33 host transaction + 47 package manager + 39 archive reader + 35 writer/lockfile/asset-index + 41 persistent-store).
- Publisher trust: **30/30 passed** in Node 22.16.0 using native WebCrypto Ed25519 and the project's SHA-256 implementation logic; valid signatures, tampering, scope/expiry checks, revocation and key rotation were exercised.
- The same 30 behavioral assertions also passed in the V8 harness with a deterministic test crypto adapter. That secondary run validates control flow only; the Node native run is the cryptographic acceptance evidence.
- V25 host bridge contract: **17/17 passed** in the V8 harness; no actual V25 UI integration has been performed.
- The writer-generated 549-byte .mmse fixture passed Python's standard-library ZIP reader (`ZipFile.testzip()` returned no corrupt member).
- The persistent-store tests exercise the in-memory transactional backend. Real IndexedDB/browser concurrency, abrupt process termination, quota handling, browser Deflate decompression, Studio UI integration, and Minecraft game tests remain outstanding.

## Next acceptance gates
1. Execute the native Node WebCrypto Ed25519 suite and add negative interoperability vectors.
2. Add a signed, versioned revocation bundle with monotonic sequence/anti-rollback.
3. Run real-browser IndexedDB tests for multi-tab writers, transaction aborts, reload/reopen, quota errors and crash recovery.
4. Wire the extension catalog and permission review into Studio behind a feature flag; require signatures for remote/marketplace installs.
5. Run V2.5 editor regression, project import/export fixtures and Minecraft in-game validation before considering a main-branch merge.

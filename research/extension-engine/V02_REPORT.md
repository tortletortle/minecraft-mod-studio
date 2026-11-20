# MMS Extension Engine V0.2 — staged host operations

V2.5 base HTML blob a0e47c2b137679475e5a3325314c2acc42c8fa6f. Structure Studio example-pack.json blob 17b87680e617bf314756f0e0feec4a05416d636f (feature/structure-studio-v0.1). No main/editor/structure branch changes.

## Discovery
StudioCore schema 3/4 items store a nine-string recipe. StudioCore.validate returns errors/warnings; existing replaceProject migrates and resets selection/history and calls render; changed() only marks dirty, not a revision counter. Therefore a generation counter alone is insufficient for edits. This prototype uses revision plus exact serialized project snapshot and a trusted synchronous atomic compareAndSwap. The real browser host is not wired yet. Do not implement CAS by calling a potentially throwing UI callback halfway through the commit; separate authoritative state swap from rendering and handle render errors after publication. Existing StudioResources.allowed accepts png/ogg/json/mcmeta/jem/jpm/bbmodel, not NBT. Do not inject structure NBT into resourceOverrides or claim Fabric output works.

## Implemented
- RecipeTransactions: active registry contribution -> bounded nine-slot vanilla-only recipe -> copy and host validation -> user-approved CAS -> one-use undo receipt. Plan/receipt identities are opaque objects held by WeakMap; previews are detached; no arbitrary project paths. Undo is conditional on no intervening mutation and exact revision. The trusted host must atomically validate revision/raw and swap, increment revision on every edit, and return the new revision. No safety guarantee for a faulty host. Caller must be trusted; approved boolean is a host confirmation contract, not a security boundary.
- planStructure: L1 declarative building preset -> Structure Studio createPack options. Allows house/tower/factory with uint32 seed and current project namespace. Explicitly rejects worldgen, additional fields and path traversal. Only produces a detached request, not NBT or a game modification. Namespace is narrower than StudioCore because Structure Studio currently limits it to 48 characters.
- example-extension.json: V0.1 compatible package demonstrating recipe and template contributions. No .mmse ZIP support yet.

## Evidence
33/33 scenarios passed in V8 on 2026-11-21. Executed authoring functions directly, then serialized exact function source for the branch. Tests use simulated registry, validator and CAS host with schema-3 fixture reconstructed from V2.5 source; fixture is not a user save and real StudioCore.validate has NOT been run. Structure mapping uses actual retrieved example pack (worldgen stripped deliberately for mapping test; tested rejection separately). No actual NBT generation, browser or Minecraft execution. Repeat: node research/extension-engine/host-tools.test.mjs. V0.1 registry tests remain separate.

- PASS preview preserves original snapshot
- PASS explicit approval required
- PASS valid commit modifies only recipe
- PASS forged token refused
- PASS token cannot be replayed
- PASS mutated preview cannot alter operation
- PASS concurrent project edit refused
- PASS ABA edit refused by revision
- PASS two previews cannot overwrite
- PASS inactive package refused at preview
- PASS revoked package refused at commit
- PASS changed contribution refused
- PASS invalid recipe size rejected
- PASS empty recipe rejected
- PASS path traversal ingredient rejected
- PASS non-vanilla recipe refused by v0.2 policy
- PASS missing item rejected
- PASS host validator rejection during preview
- PASS host validator rejection at commit
- PASS failed write leaves project intact and token retryable
- PASS undo restores exact original bytes
- PASS undo requires approval
- PASS undo never overwrites later edit
- PASS invalid receipt denied
- PASS undo receipt single use
- PASS same recipe no-op refused
- PASS recipe preview rejects incompatible target
- PASS real structure sample house/tower/factory mapped without worldgen
- PASS worldgen is explicitly rejected at L1 boundary
- PASS structure traversal ID rejected
- PASS structure reserved namespace rejected
- PASS structure seed bounds enforced
- PASS structure request rejects inactive contribution

## Next acceptance gates
1. Run registry + host tools against real StudioCore on an exported project fixture. Compare validation, compiler artifacts and original bytes after undo.
2. Wire trusted adapter into the browser state layer; verify interleaving edits, import, save, undo, error handling and real editor regressions. Do not change the main branch before acceptance.
3. Wire a real Structure Studio createPack invocation in an isolated service, then validate gzip NBT/Java 26.2 in a disposable world. No auto worldgen.
4. ZIP reader and signed/hash-locked manifests; semantic checks before exposing additional contribution types. Limit pending previews and persistent history when integrated.

# MMS Extension Engine V0.6 — persistent catalog, content store and recovery journal

Date: 2026-11-21  
Branch: research/extension-engine

## Delivered and verified

### Persistent storage
- Added a backend-neutral key/value transaction contract.
- Added an in-memory transactional backend for deterministic tests.
- Added an IndexedDB backend for browser persistence, with a single object store and read/write transactions.
- Package metadata, content-addressed asset blobs, staged blobs and transaction journals use separate key prefixes.

### Install / upgrade / uninstall
- Prepare phase parses each .mmse archive through the V0.4 reader and builds a SHA-256 content-addressed asset index.
- New blobs and a prepared journal are staged before any package becomes visible.
- Commit requires explicit approval and checks the base catalog revision to reject stale plans.
- Package records and blob writes are committed in one backend transaction.
- Exact dependency pins, topological validation, permission grants, upgrade rules and atomic batch uninstall are retained.
- Rollback restores the previous package records, and rejects stale rollback receipts.
- Garbage collection removes blobs not referenced by any installed package.

### Crash recovery
- A prepared journal is not visible as an installed package.
- Recovery aborts leftover prepared journals and deletes their staged blobs.
- The IndexedDB implementation relies on the atomicity of a single IndexedDB read/write transaction for commit.
- Recovery and rollback behavior are exercised against the in-memory transactional backend; abrupt browser process termination and actual IndexedDB crash recovery have not yet been tested in a browser.

## Test evidence

The committed persistent-store source and test files were re-read from GitHub and executed in the V8 harness on 2026-11-21.

| Scenario group | Result |
|---|---:|
| Install staging / visibility / explicit approval | PASS |
| Blob persistence and deduplication | PASS |
| Dependency ordering and failure atomicity | PASS |
| Upgrade / downgrade / exact pin constraints | PASS |
| Permission reauthorization and closure activation | PASS |
| Disable / uninstall dependency safety | PASS |
| Rollback after install, upgrade and uninstall | PASS |
| Stale plans and stale rollback receipts | PASS |
| Recovery of prepared-but-uncommitted transactions | PASS |
| Garbage collection and defensive copies | PASS |
| Missing IndexedDB capability error | PASS |
| **Persistent-store suite** | **31/31** |

Combined branch regression is now 209/209 based on the recorded V8 suite results: 24 registry + 33 host transaction + 47 package manager + 39 archive reader + 35 archive writer/lockfile/asset-index + 31 persistent-store tests.

## Important limitations

- IndexedDB browser execution is not yet verified. The 31 tests exercise the MemoryKVBackend; one test only checks the missing-IndexedDB error path.
- No fake-indexeddb or real browser transaction/concurrency test was run.
- The store is not wired into Minecraft Mod Studio's actual UI or project import/export workflow.
- No filesystem extraction is performed; asset bytes remain in IndexedDB blobs.
- No cross-tab locking/coordination protocol is implemented. Revision checks protect stale plans inside a transaction, but multi-tab race behavior needs explicit browser tests.
- No publisher signature, trust root, revocation or remote marketplace is implemented.
- No Minecraft in-game test has been performed.

## Next acceptance gates

1. Add browser integration tests against real IndexedDB: concurrent prepare/commit, two tabs, transaction abort, quota errors, reload/reopen and recovery.
2. Add cross-tab coordination or prove the revision/transaction design is sufficient under concurrent writers.
3. Connect persistent package state to a feature-flagged Studio UI without modifying the main branch.
4. Add install/uninstall UI, permission review, package details, recovery status and user-visible error handling.
5. Only merge after V2.5 editor regression, project import/export and Minecraft game validation.

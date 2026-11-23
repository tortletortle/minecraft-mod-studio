# MMS Extension Engine V0.9 — rollback retention and multi-tab acceptance

Date: 2026-11-23  
Branch: `research/extension-engine`  
Status: implementation committed; automated execution evidence pending.

## Problem found

The V0.8 store journal retained previous package metadata, but `collectGarbage()` only considered currently installed packages when deciding which content-addressed blobs to keep. After uninstalling or upgrading a package, garbage collection could delete assets referenced by the previous package snapshot. A later rollback could therefore restore package metadata whose asset bytes no longer existed.

This was a real consistency defect in the rollback contract, not merely a missing UI feature.

## V0.9 changes

### 1. Bounded rollback retention

- Every newly committed transaction records `rollbackExpiresAt`, set to 24 hours after commit.
- Rollback remains subject to the existing revision check; a later catalog mutation makes the receipt stale.
- Rollback rejects expired receipts with `ROLLBACK_EXPIRED`.
- Before restoring prior package records, rollback verifies that all referenced content-addressed blobs still exist. Missing bytes fail closed with `ROLLBACK_BLOB_MISSING`.

### 2. Garbage-collection protection

- Garbage collection now scans package records, blob records and transaction journals in one IndexedDB read/write transaction.
- It protects assets referenced by the previous package snapshots only when the committed transaction still matches the current catalog revision and remains unexpired.
- A later catalog mutation makes an older receipt stale, so its historical assets stop being pinned immediately; after the rollback window expires, the current receipt's historical assets can also be reclaimed.
- This applies to uninstall and upgrade rollback, not just uninstall.

### 3. Regression coverage

Added `v09-rollback-retention.test.mjs` with cases for:
- uninstall → garbage collection → rollback restores package metadata and original asset bytes;
- upgrade → garbage collection → rollback restores the previous version and its assets;
- expiry → rollback is rejected and orphaned blobs become collectible;
- two plans prepared against one revision cannot both commit.
- stale rollback journals do not retain historical asset blobs after a later catalog commit.

Updated the existing persistent-store garbage-collection test to assert that assets are retained during the rollback window and collected after expiry.

### 4. Real-browser multi-tab acceptance

Added `v09-multitab-acceptance.mjs`. It launches two independent Chromium pages on the same origin, creates separate store instances over the same IndexedDB database, and tests:
1. both tabs prepare an uninstall against the same catalog revision;
2. the first commit succeeds;
3. the second commit fails with `STALE_PLAN`;
4. garbage collection retains the prior package's asset bytes;
5. rollback restores the package and its original asset bytes.

The V25 embedded browser runtime was synchronized with the source implementation, and the browser-acceptance workflow now includes both the V0.9 unit suite and the two-tab Chromium script.

### 5. User-facing uninstall undo

- The V25 manager now stores the most recent uninstall transaction ID in localStorage and exposes one compact `撤销最近卸载` control.
- The control is available only while the transaction remains within its 24-hour rollback window.
- A later catalog mutation clears the local undo record; a mutation from another tab is detected by the store revision check and rejected as `STALE_RECEIPT`.
- The V25 manager integration test now exercises uninstall → undo → restored package.
- The real Chromium V25 acceptance script now includes the same UI undo path, followed by a second uninstall.

## Verification status

### Local source-execution evidence (2026-11-23)

The changed source modules were loaded and executed in a V8 harness in this session:

- Existing persistent-store regression cases: **41/41 passed**.
- New V0.9 rollback-retention cases: **5/5 passed**.
- V25 manager integration scenario, including uninstall → undo → restored package: **1/1 passed**.
- Syntax parsing: passed for the changed store, runtime, manager, unit-test and browser-acceptance source files.

**Qualification:** the two store suites ran against `MemoryKVBackend` in a custom V8 harness; the manager test used its simulated DOM/IndexedDB harness. These results do not establish actual Node.js 22 execution, real-browser IndexedDB concurrency, or the two-tab Chromium acceptance.

### CI and real-browser status

**Not yet verified by GitHub Actions.** The workflow now runs the full extension regression set, the V0.9 rollback suite, the two-tab Chromium test and the V25 browser test. The available GitHub status/workflow queries returned no check results or run records for the latest push commits. Therefore the real-browser acceptance is still pending.

The previous V0.8 test evidence remains historical evidence only; it does not validate these V0.9 changes.

## Known limits

- The 24-hour rollback window is currently a fixed implementation constant, not a user-configurable setting.
- The UI exposes only the most recent uninstall undo, not a general transaction history or rollback browser. The undo transaction ID is stored in localStorage; if localStorage is unavailable, undo persistence is limited to the current page session.
- This does not yet prove quota handling, forced transaction abort recovery, abrupt browser termination recovery, or Firefox/WebKit behavior.
- The multi-tab script is an acceptance test, not proof until its CI run completes successfully.

## Next acceptance gates

1. Obtain a successful CI run for the existing persistent-store suite, the V0.9 rollback-retention suite, the two-tab Chromium acceptance, and the V25 browser regression.
2. Add explicit IndexedDB quota, abort, blocked-open and abrupt-termination tests.
3. Test stale prepared journals and recovery while another tab is active; do not treat manual recovery as concurrency-safe until verified.
4. Add a minimal, recoverable user-facing uninstall undo flow before presenting rollback retention as a user feature.
5. Only after these gates, proceed to more contribution adapters and SDK stabilization. Keep the branch isolated from `main`.

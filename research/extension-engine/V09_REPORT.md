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
- It protects assets referenced by the previous package snapshots of committed, unexpired transactions.
- After the rollback window expires, those historical references stop pinning blobs and normal garbage collection can reclaim them.
- This applies to uninstall and upgrade rollback, not just uninstall.

### 3. Regression coverage

Added `v09-rollback-retention.test.mjs` with cases for:
- uninstall → garbage collection → rollback restores package metadata and original asset bytes;
- upgrade → garbage collection → rollback restores the previous version and its assets;
- expiry → rollback is rejected and orphaned blobs become collectible;
- two plans prepared against one revision cannot both commit.

Updated the existing persistent-store garbage-collection test to assert that assets are retained during the rollback window and collected after expiry.

### 4. Real-browser multi-tab acceptance

Added `v09-multitab-acceptance.mjs`. It launches two independent Chromium pages on the same origin, creates separate store instances over the same IndexedDB database, and tests:
1. both tabs prepare an uninstall against the same catalog revision;
2. the first commit succeeds;
3. the second commit fails with `STALE_PLAN`;
4. garbage collection retains the prior package's asset bytes;
5. rollback restores the package and its original asset bytes.

The V25 embedded browser runtime was synchronized with the source implementation, and the browser-acceptance workflow now includes both the V0.9 unit suite and the two-tab Chromium script.

## Verification status

**Not yet verified by CI.** The scripts and workflow steps have been committed, but the available GitHub status/workflow queries returned no status checks or run records for the latest push commits. Therefore no V0.9 test is claimed as passing yet.

The previous V0.8 test evidence remains historical evidence only; it does not validate these V0.9 changes.

## Known limits

- The 24-hour rollback window is currently a fixed implementation constant, not a user-configurable setting.
- The manager does not yet expose a user-facing “undo uninstall” action; rollback is currently a store-level API capability.
- This does not yet prove quota handling, forced transaction abort recovery, abrupt browser termination recovery, or Firefox/WebKit behavior.
- The multi-tab script is an acceptance test, not proof until its CI run completes successfully.

## Next acceptance gates

1. Obtain a successful CI run for the existing persistent-store suite, the V0.9 rollback-retention suite, the two-tab Chromium acceptance, and the V25 browser regression.
2. Add explicit IndexedDB quota, abort, blocked-open and abrupt-termination tests.
3. Test stale prepared journals and recovery while another tab is active; do not treat manual recovery as concurrency-safe until verified.
4. Add a minimal, recoverable user-facing uninstall undo flow before presenting rollback retention as a user feature.
5. Only after these gates, proceed to more contribution adapters and SDK stabilization. Keep the branch isolated from `main`.

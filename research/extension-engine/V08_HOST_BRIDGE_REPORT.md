# MMS Extension Engine V0.8-A — V25 host bridge contract

Date: 2026-11-21  
Branch: research/extension-engine

## Delivered

Added `v25-host-bridge.mjs` as a narrow adapter contract between the extension engine and the V25 editor's private project state.

### Contract
- Receives the existing V25 `StudioCore` service and synchronous host callbacks for reading/replacing the live project, notifying the editor, and checking the feature flag.
- Feature flag defaults to disabled from the caller's perspective; all bridge operations fail closed unless `isEnabled()` returns true.
- Returns defensive project snapshots. Package code never receives a live mutable project reference.
- Stages host-owned mutations against a copied snapshot, runs `StudioCore.migrate` and `StudioCore.validate`, and keeps the live project unchanged until explicit commit approval.
- Commit revalidates the staged snapshot and compares the current encoded project with the staged base snapshot. It rejects stale plans and changes made directly by the editor while a plan is pending.
- Commit produces a one-use rollback receipt. Rollback requires explicit approval and is rejected if the project changed after commit.
- Rejects asynchronous host callbacks. The bridge contract is synchronous so a commit cannot be suspended halfway through a project mutation.
- Mutation callbacks are trusted host integration code only. They are not loaded from extension packages.

### Intended V25 binding
The eventual adapter will be created inside the V25 application scope, where the private `project`, `StudioCore`, and editor callbacks are available. The bridge will update in-memory editor state and mark the project dirty; it will not bypass the existing user-controlled localStorage save flow.

## Test evidence

17/17 scenarios passed in the V8 harness:
- feature flag disabled by default;
- defensive snapshots;
- stage-without-mutation;
- explicit approval;
- successful commit;
- validation at stage and commit;
- stale plans;
- direct editor mutation conflict;
- invalid tokens;
- rollback approval and restoration;
- stale rollback receipts;
- warning propagation;
- mutator exception containment;
- asynchronous callback rejection before mutation.

## Not yet implemented

- No change was made to `Minecraft_Mod_Studio_V25.html`.
- The bridge is not imported or instantiated by the actual V25 UI.
- No contribution type has been mapped to a V25 project schema yet.
- No extension catalog panel, permission dialog or publisher status UI exists.
- No real-browser test, localStorage save/restore test, IndexedDB test, Fabric build or Minecraft game test has been performed for this bridge.

## Next step

Integrate the bridge inside the V25 application closure behind a disabled-by-default feature flag. Start with read-only catalog visibility, then one deliberately narrow declarative contribution type. Do not expose the whole project object or enable arbitrary plugin execution.

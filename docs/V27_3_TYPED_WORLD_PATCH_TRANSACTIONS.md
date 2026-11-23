# V2.7.3 — Typed World Patch Transactions

## Goal

V2.7.2 retrieves live Brigadier commands, inspects their usage and produces a conservative syntax/risk preview. It deliberately does not execute command strings.

V2.7.3 adds a separate typed world-edit path for one narrow operation: placing ordinary full-cube blocks into air cells in a local single-player test world. It does not add a generic command executor and does not turn a mod command manifest into an authorization source.

This first milestone proves the transaction boundary—preview, explicit apply, post-state verification and conflict-aware rollback—before expanding the block-state language or supported operation types.

## MCP surface

| Tool | Bridge operation | Effect |
|---|---|---|
| `mms_preview_block_patch(placements)` | `block_patch_preview` | Read-only validation and snapshot |
| `mms_apply_block_patch(plan_id, confirm=true)` | `block_patch_apply` | Applies the exact previewed patch |
| `mms_rollback_block_patch(transaction_id, confirm=true)` | `block_patch_rollback` | Restores the captured pre-state if no conflict exists |

Each placement has four fields: integer `x`, `y`, `z`, and a fully qualified `block_id`, such as `minecraft:stone`. The MCP schema accepts 1–32 placements. The runtime validates the payload again; MCP-side validation is not a security boundary.

## Runtime contract

### Preview constraints

- Requires the current integrated single-player world and the local player's server-side identity.
- Preview and apply require the local player to be in Creative mode; rollback remains available if the player changes mode after a successful apply.
- At most 32 distinct block positions per patch.
- Each target must be inside world bounds and the world border, already loaded (the tool does not load or generate chunks), and within 16 blocks of the player.
- A target cell must currently be air. Overwriting non-air blocks is not supported.
- The position must not intersect the player or any loaded entity bounding box and must pass vanilla `ServerPlayer.mayInteract`.
- Target block IDs must resolve in the live block registry and use the `minecraft:` namespace. Third-party mod blocks default to denied until a reviewed per-mod placement adapter exists.
- Target states must be non-air, opaque full-cube states (`isSolidRender()`), non-fluid and have no block entity.
- Known hazardous/unstable blocks (including TNT, fire, redstone power blocks, portals, gravity blocks and anvils) are rejected.
- Only each block's default state is supported. Block-state properties, block-entity data, inventories, signs, containers and arbitrary NBT are not accepted.

Preview captures the exact current `BlockState` object for each air cell, the target default state, dimension, player UUID, expiry and a deterministic SHA-256 digest over dimension/coordinates/before IDs/target IDs. The plan ID is an opaque random UUID and expires after two minutes.

### Apply

Apply requires a separate `confirm=true` on the individual MCP call. Before writing anything, the integrated-server-thread handler rechecks:

1. The plan exists and has not expired.
2. The same integrated-server instance, player and dimension are still active.
3. Every target remains loaded, in range, permitted and outside player/entity bounding boxes.
4. Every cell still exactly equals its captured pre-state.
5. No block entity appeared at any target.

Only after all preflight checks pass does it call the typed `ServerLevel.setBlock` API. It does not parse or dispatch a command string. The initial adapter uses the client-update flag without neighbor notification to avoid triggering redstone/neighbor-update cascades during this first constrained milestone.

Every target state is read back after the batch. If a write or verification fails, the adapter attempts a compensating restore of the cells it changed and returns an explicit failure code; it never reports success without a verified post-state.

Successful apply returns a transaction UUID, the plan ID, placement count, snapshot digest, post-state verification and a rollback expiry.

### Rollback

Rollback also requires `confirm=true`. It is available for ten minutes while the current game session remains alive.

Before changing any cell, rollback checks that every patched cell still exactly equals the block state this transaction applied. If even one cell differs, the entire rollback is refused with `BLOCK_PATCH_ROLLBACK_CONFLICT`; it does not overwrite later player or mod changes.

If the preflight succeeds, the transaction restores the captured air states and verifies them. If restoration fails partway through, it attempts a compensating re-apply and returns an explicit error if compensation is incomplete.

## State and recovery boundaries

- Pending plans and rollback snapshots are held in the companion's in-memory maps. They are not durable across a Minecraft restart, client crash or companion reload.
- The initial transaction covers only patched block cells. It does not capture entities, scheduled ticks, inventories, block entities, neighboring block state changes or arbitrary mod side effects.
- Neighbor notifications are suppressed for the initial solid-block adapter, but this is not a general simulation or guarantee that every mod's hooks/protection rules are honored.
- Vanilla world-border, loaded-chunk, player/entity-intersection and `mayInteract` checks are enforced. Mod-specific claim/protection APIs are not universally integrated.
- Use a disposable Creative single-player test world. Do not use this first adapter as a general-purpose world repair or production-world migration tool.

## Why not use `/setblock` or `/fill`?

A Brigadier command string is an open-ended program surface: `execute`, datapack functions and mod commands can delegate to other logic. A typed patch contains only bounded coordinates and registry-backed block IDs. The runtime can validate every target, capture every pre-state, compare the world immediately before writing, and associate each write with a rollback record. Command discovery remains useful for understanding mod functionality, but it is not the execution transport for these block edits.

## Explicit live acceptance

The repository adds an opt-in round-trip check to `runtime_acceptance.py`:

```powershell
python runtime-companion/tools/runtime_acceptance.py `
  --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" `
  --exercise-block-patch --allow-world-mutation `
  --report artifacts\block-patch-acceptance.json
```

The helper searches nearby candidate cells for air, previews one stone placement, verifies that apply without confirmation is rejected, applies with confirmation, inspects the stone, rolls it back with confirmation and verifies the cell is air again. It is opt-in and must only be run in a disposable Creative world.

## Validation status

The branch includes MCP contract tests for preview/apply/rollback separation and confirmation guards, runtime acceptance helper tests using a fake bridge, the existing Python MCP/retrieval/policy suites, and a Fabric 26.2 / Java 25 build workflow targeting this branch and PR base.

A passing fake-bridge test does not establish that the Java companion compiles or that the patch round-trip works in a live Minecraft 26.2 client. The current GitHub Actions environment has been failing before job steps start (empty step lists); no successful build or in-game result is claimed until a runner-backed build and disposable-world acceptance complete.

## Next increments

1. Add block-state property schemas (facing, axis, waterlogged) with registry/property validation.
2. Add durable snapshot storage and recovery after restart.
3. Add explicit bounded replace operations with block-entity exclusion and a second approval tier.
4. Add mod-specific protection adapters and post-operation world-diff checks.
5. Add higher-level geometry primitives (cuboid, wall, tower, roof) that compile into the same typed patch format.
6. Only then expand from simple block patches into full structure construction.

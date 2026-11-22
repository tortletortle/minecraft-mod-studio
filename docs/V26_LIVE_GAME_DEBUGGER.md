# V2.6 — Live Game Debugger

Status: V2.6.1 added server-authoritative mob attribute tuning and animation triggering; V2.6.2 added confirmed reset to generated Rig defaults; V2.6.3 added the Python runtime acceptance helper and report validators; V2.6.4 adds a typed stdio MCP adapter for local AI agents. MCP tests verify the adapter and command mapping, but actual in-world movement, attribute synchronization, animation rendering and shutdown cleanup remain pending.

## Why this is a separate subsystem

V2.0's debugger executes the visual behavior graph in a browser preview. V1.5's trace viewer analyzes imported runtime logs. V2.5 adds isolated client and GameTest coverage. None of those is a bidirectional, live control channel to a running player session.

V2.6 adds an optional client-only Fabric companion mod. It is installed alongside a generated mod in a disposable Minecraft 26.2 test instance. It does not replace the editor, alter generated production sources, or claim that preview execution is gameplay.

## Architecture

```text
Local AI agent (MCP stdio client)
          |
          | typed tools; explicit confirmation for control operations
          v
runtime-companion/tools/live_debugger_mcp.py
          |
          | authenticated TCP JSON Lines
          | 127.0.0.1 + per-launch 256-bit bearer token
          v
LiveGameDebugger companion (client-only Fabric mod)
          |
          | Minecraft client thread: player input and reads
          | Integrated server thread: mob attribute writes and animation triggers
          v
Minecraft client + integrated single-player test world
          |
          +-- player input mappings (bounded movement/look)
          +-- loaded entity and block inspection
          +-- server-authoritative mob attributes
          +-- generated mob animation event broadcast
```

The bridge is local-only and has no LAN listener. It accepts one authenticated agent at a time. All world commands require an active integrated single-player world. Movement requests expire after at most 40 game ticks and are rejected if movement keys were already held when the request began.

## Implemented command contract

- `status`: player position, view, health, velocity, dimension and world tick.
- `move`: forward/strafe/jump/sprint/sneak input for 1–40 ticks.
- `look`: bounded yaw/pitch update.
- `stop`: release bridge-owned movement input immediately.
- `entities`: list up to 50 nearby loaded entities.
- `inspect_entity`: inspect one entity by UUID.
- `entity_attributes`: read server-authoritative base/effective values for max health, attack damage and movement speed.
- `set_entity_attribute`: write one allowlisted generated-mob base attribute; requires `confirm: true` and fixed numeric bounds.
- `reset_entity_attributes`: restore the generated mob's three supported base attributes from its `Rig` constants; requires `confirm: true`.
- `trigger_animation`: invoke the generated mob's fixed `triggerStudioAnimation(String)` method on the integrated server so the generated entity can broadcast its animation event.
- `block`: inspect one nearby block.

The companion exposes a fixed command allowlist. It does not expose chat/command dispatch, caller-controlled reflection, arbitrary Java, arbitrary filesystem operations, or multiplayer access. The animation adapter uses one fixed method name and signature; neither the method nor a class name is supplied by the caller.

## Security and mutation boundaries

- IPv4 loopback only; per-launch 256-bit token; one client at a time.
- Maximum 8 outstanding requests, 120 requests per minute and 8 KiB per JSON line.
- Every entity-control command targets a live mob in the player's current dimension and within 64 blocks.
- Only `max_health` (1–1024), `attack_damage` (0–256) and `movement_speed` (0–4) are writable. Unknown attribute keys are rejected.
- Attribute writes require explicit `confirm: true`. They change base attributes and may be persisted when the world is saved. Use a disposable test world only.
- No spawn/despawn, block placement/breaking, arbitrary commands, arbitrary code or multiplayer control.

## Acceptance gates

1. Python client tests: handshake, request/response correlation, invalid host/token rejection and reserved-field validation.
2. Fabric 26.2 Gradle build under JDK 25; inspect the resulting JAR manifest and expected class entries.
3. Launch the companion in an isolated client; verify the connection file is created and removed on shutdown.
4. From the Python agent, read player status, rotate the view, walk forward for a bounded tick count, stop, and read the changed position.
5. Spawn a known generated mob manually in a disposable Creative world; verify nearby entity listing, UUID inspection and block lookup.
6. Read the three supported attributes; write one value with `confirm: true`; verify the server-side base/effective value and the client-observed update.
7. Trigger a known generated animation ID; verify the server method accepts it and the client receives the animation event and visibly changes pose.
8. Disconnect the agent during movement; confirm the 40-tick cap releases inputs without a further command.
9. Confirm a multiplayer server is rejected with `SINGLEPLAYER_ONLY`.
10. Verify MCP tool discovery, confirmation gates, parameter bounds and the absence of generic command dispatch.

Do not mark gates 3–9 passed based on source inspection or a successful compile. Store the exact game version, mod/JAR hash, test world setup, command transcript and screenshots/logs.

## Build evidence

The initial 0.1.0 baseline passed GitHub Actions run [44912912833](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44912912833). The artifact was `mms-live-debugger-0.1.0.jar`; JAR SHA-256: `543771ab1daba173f3abded30d03e634f5b78a52c6d1786ffbd64c0834d8db1d`. This proves compilation and packaging only, not actual in-world control.

The 0.2.0 V2.6.1 build passed GitHub Actions run [44914031176](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914031176); artifact [14710788309](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914031176/artifacts/14710788309) contains `mms-live-debugger-0.2.0.jar`. JAR SHA-256: `f10018e5af2deca3e2d0fd424727fb85e2b803dba36f84c17b35b87b4776652b`. The six protocol-client tests pass; this still proves build/packaging only, not in-world behavior.

The 0.3.0 V2.6.2 build passed GitHub Actions run [44914638220](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914638220); artifact [14711415756](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914638220/artifacts/14711415756) contains `mms-live-debugger-0.3.0.jar`. Seven protocol-client tests passed. JAR SHA-256: `ffe1c5c7ba79ea785e4f557516ebfc999886fbfda9b25eae6063ca8562edb3f5`. This remains build/packaging evidence only. The tooling/build run [44915621433](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44915621433) passed 15 Python tests, Python compileall and Fabric 26.2 packaging; artifact [14711841388](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44915621433/artifacts/14711841388) contains a 0.3.0 JAR with SHA-256 `12c129000fb9bf7ef4fab76226b0935dad533e764cf3d80795699682072765d1`.

## Next milestones

- **V2.6.1 — integrated-server control plane:** in implementation; bounded mob attribute inspection/writes and generated animation trigger adapter. Controlled spawn/despawn is intentionally deferred.
- **V2.6.2 — live tuning:** runtime parameter overlays, reset-to-generated-defaults, before/after snapshots and reproducible experiment records.
- **V2.6.3 — runtime acceptance tooling:** added a Python smoke-test helper for protocol, player, entity, block, animation and reversible attribute checks; actual-game execution and evidence remain pending.
- **V2.6.4 — studio integration:** connect the editor to the local companion, show player/entity state and tuning controls without requiring the agent to operate the desktop UI.
- **V2.7 — test orchestration:** scenario definitions, checkpoints, replay, screenshots and comparison reports.

Keep the existing V2.5 browser preview debugger and V2.5 client GameTests intact. Runtime control must remain a separate, opt-in layer.


### Reproducibility note

Repeated 0.3.0 builds contained byte-identical class entries and the same Fabric metadata, but their JAR hashes differed because Loom emitted the `Fabric-Loom-Client-Only-Entries` manifest list in a different order. The latest artifact hash above is the one to use. Stable manifest ordering remains a build reproducibility follow-up; this observed difference did not involve class bytecode changes.

The PR-head build [44916013067](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916013067) passed the 15 Python tests, tool compilation and Fabric build. Its artifact [14711566988](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916013067/artifacts/14711566988) contains a 0.3.0 JAR with SHA-256 `ffe1c5c7ba79ea785e4f557516ebfc999886fbfda9b25eae6063ca8562edb3f5`.

The final PR-head validation run [44916284480](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916284480) passed the same 15 tests, tool compilation and Fabric build. Artifact [14712390413](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916284480/artifacts/14712390413) contains the inspected 0.3.0 JAR with SHA-256 `12c129000fb9bf7ef4fab76226b0935dad533e764cf3d80795699682072765d1`. The companion's classes are identical across the two manifest-order variants.
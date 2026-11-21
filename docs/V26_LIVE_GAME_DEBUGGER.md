# V2.6 — Live Game Debugger

Status: first runtime-bridge implementation added on branch `v2.6-live-game-debugger`; CI compilation and actual in-world control remain pending until their recorded checks pass.

## Why this is a separate subsystem

V2.0's debugger executes the visual behavior graph in a browser preview. V1.5's trace viewer analyzes imported runtime logs. V2.5 adds isolated client and GameTest coverage. None of those is a bidirectional, live control channel to a running player session.

V2.6 therefore adds an optional client-only Fabric companion mod. It is installed alongside a generated mod in a disposable Minecraft 26.2 test instance. It does not replace the editor, alter generated production sources, or claim that preview execution is gameplay.

## Architecture

```text
Local AI agent / Python client
          |
          | TCP JSON Lines, protocol v1
          | 127.0.0.1 + per-launch 256-bit bearer token
          v
LiveGameDebugger companion (client-only Fabric mod)
          |
          | main-thread dispatch through Minecraft.execute
          v
Minecraft client + integrated single-player test world
          |
          +-- player input mappings (bounded movement/look)
          +-- loaded entity and block inspection
```

The bridge is local-only and has no LAN listener. It accepts one authenticated agent at a time. All game commands require an active integrated single-player world. Movement requests expire after at most 40 game ticks and are rejected if movement keys were already held when the request began.

## Implemented command contract

- `status`: player position, view, health, velocity, dimension and world tick.
- `move`: forward/strafe/jump/sprint/sneak input for 1–40 ticks.
- `look`: bounded yaw/pitch update.
- `stop`: release bridge movement input immediately.
- `entities`: list up to 50 nearby loaded entities.
- `inspect_entity`: inspect one entity by UUID.
- `block`: inspect one nearby block.

The companion exposes a fixed command allowlist. It does not expose chat/command dispatch, reflection, arbitrary Java, file APIs, or network destinations beyond loopback.

## Acceptance gates

1. Python client tests: handshake, request/response correlation, invalid host/token rejection.
2. Fabric 26.2 Gradle build under JDK 25.
3. Launch the companion in an isolated client; verify the connection file is created and removed on shutdown.
4. From the Python agent, read player status, rotate the view, walk forward for a bounded tick count, stop, and read the changed position.
5. Spawn a known test mob manually in a disposable Creative world; verify nearby entity listing, UUID inspection and block lookup.
6. Disconnect the agent during movement; confirm the 40-tick cap releases inputs without a further command.
7. Confirm a multiplayer server is rejected with `SINGLEPLAYER_ONLY`.

Do not mark gates 3–7 passed based on source inspection or a successful compile. Store the exact game version, mod/JAR hash, test world setup, command transcript and screenshots/logs.

## Next milestones

- **V2.6.1 — integrated-server control plane:** entity attribute read/write with strict attribute allowlist and numeric bounds; controlled spawn/despawn; explicit opt-in world mutation; generated mob animation trigger adapter.
- **V2.6.2 — live tuning:** runtime parameter overlays, reset-to-generated-defaults, before/after snapshots and reproducible experiment records.
- **V2.6.3 — studio integration:** connect the editor to the local companion, show player/entity state and tuning controls without requiring the agent to operate the desktop UI.
- **V2.7 — test orchestration:** scenario definitions, checkpoints, replay, screenshots and comparison reports.

Keep the existing V2.5 browser preview debugger and V2.5 client GameTests intact. Runtime control must be a separate, opt-in layer.

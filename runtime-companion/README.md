# MMS Live Game Debugger — Runtime Companion

The runtime companion is an optional client-only Fabric mod that gives a local AI agent a narrow, authenticated control channel into a **single-player test world**. It is separate from the existing Mod Studio editor and does not modify generated production JARs.

## Runtime companion 0.5.0 — V2.7.0

- Starts a TCP JSON-lines bridge bound exclusively to `127.0.0.1`.
- Generates a fresh 256-bit bearer token each game launch and writes it to Fabric's config directory: `config/mms-live-debugger/connection.json`.
- Allows one local agent connection, authenticated by the token.
- Exposes fixed runtime control operations plus read-only Brigadier command discovery, inspection and syntax validation; arbitrary command execution, Java execution, file access, and remote/LAN connections are not exposed.
- Requires a local integrated single-player server for every world read/control command.
- Supports player status, one-call scene snapshots, bounded movement, camera look, emergency stop, nearby entity inspection, entity detail inspection, nearby block inspection, and read-only live command-tree discovery.
- Adds a fixed-path asynchronous render-target screenshot capture returned to MCP clients as PNG image content, with capture-ID and SHA-256 sidecar verification.
- Adds MCP-level movement verification and short-lived transient authorization for bounded movement, camera and animation controls.
- Adds server-authoritative mob attribute inspection and bounded attribute writes for max health, attack damage, and movement speed. Writes require `confirm: true`.
- Adds `reset_entity_attributes`, which restores the three supported base attributes from the generated mob's `Rig` constants. This also requires `confirm: true`.
- Adds a fixed generated-mob animation trigger adapter; it calls only the generated `triggerStudioAnimation(String)` method and broadcasts through the integrated server.
- Movement input is bounded to 1–40 game ticks and is automatically released. A new movement command is rejected while one is active or while movement keys are already held by the player.

## Build

Requirements: JDK 25, Gradle 9.5.1, internet access for the pinned Minecraft/Fabric dependencies.

From this directory:

```bash
gradle --no-daemon clean build
```

The mod JAR is produced under `build/libs/` (version `0.5.0`). It is a client-only companion and requires Fabric Loader 0.20.1+, Fabric API 0.161.0+26.2, Minecraft 26.2, and Java 25.

## Install

1. Build the JAR or obtain the `mms-live-debugger-jar` artifact from the V2.6 GitHub Actions run after it passes.
2. Copy the JAR into the `mods` directory of a **separate Minecraft 26.2 Fabric test instance**.
3. Launch a single-player test world.
4. Read the startup log line beginning `[MMS Live Debugger] READY`; it includes the exact connection-file path.
5. Give the connection file only to the local agent you intend to authorize. The token grants control of that local test client until the game closes.

## Local agent example

Run from the repository root:

```powershell
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --command status
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --command move --args "{\"forward\":1,\"strafe\":0,\"ticks\":20,\"sprint\":false}"
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --command stop
```

The Python client uses only the standard library. An AI agent can import `BridgeClient` and call `request(command, **arguments)` directly.

## Cursor integration — V2.6.5

Install the pinned MCP SDK:

    python -m pip install -r runtime-companion/requirements-mcp.txt

After launching Minecraft with the companion in a disposable single-player Creative world, install the workspace MCP configuration:

    python runtime-companion/tools/install_cursor_mcp.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --scope workspace --workspace .

The installer creates .cursor/mcp.json and preserves other servers. It does not alter approval policy by default. To additionally allow automatic execution of read-only inspection and the emergency stop tool, explicitly pass --allow-safe-tools-without-approval. That option writes .cursor/permissions.json; review existing Cursor permissions first because a permissions.json MCP allowlist takes precedence over the in-app allowlist. To also allow bounded movement, camera and animation tools after the agent has obtained a short-lived transient authorization, explicitly pass --allow-transient-actions-without-approval. The authorization tool and persistent attribute writes remain approval-gated. Review existing permissions first.

Restart Cursor, then verify the registration and live bridge:

    python runtime-companion/tools/diagnose_cursor_mcp.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --scope workspace --workspace .

See [V2.6.5 Agent Experience](../docs/V26_5_AGENT_EXPERIENCE.md) for tool semantics, authorization boundaries and acceptance checks.

## MCP integration for local AI agents

Install the optional pinned dependency:

    python -m pip install -r runtime-companion/requirements-mcp.txt

Register the stdio server with an MCP-compatible client:

    codex mcp add minecraft-live-debugger -- python -B runtime-companion/tools/live_debugger_mcp.py --connection-file "C:\\path\\to\\instance\\config\\mms-live-debugger\\connection.json"

The server exposes typed tools for scene snapshots, screenshots, entity/block inspection, bounded movement with verification, short-lived transient authorization, look, stop, generated-mob attribute tuning/reset, animation triggering, and read-only command search/inspection/syntax validation. It opens a short-lived authenticated connection per tool call and does not cache the per-launch token. Persistent attribute changes are restricted to disposable worlds and require Cursor host approval plus per-call confirm=true. See [V2.6.4 MCP Agent](../docs/V26_4_MCP_AGENT.md), [V2.6.5 Agent Experience](../docs/V26_5_AGENT_EXPERIENCE.md), and [V2.7.0 AI God Mode Command Intelligence](../docs/V27_AI_GOD_MODE_COMMAND_INTELLIGENCE.md) for the complete tool contract and safety boundaries.

## Live runtime acceptance helper

After installing the companion in a disposable single-player instance, run the repository-root helper:

```powershell
python runtime-companion/tools/runtime_acceptance.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --report artifacts\runtime-acceptance.json
```

Pass `--mob-uuid` to add generated-mob checks, `--animation-id` to trigger a known generated animation, or `--exercise-attribute attack_damage --allow-world-mutation` to temporarily change and restore one base attribute. The write probe is opt-in and should only run in a disposable world. The helper does not automatically run the full reset-to-Rig-defaults command; see `docs/V26_2_RUNTIME_TUNING.md`.

Full procedure: [V2.6 live runtime acceptance](../docs/V26_RUNTIME_ACCEPTANCE.md).

## Protocol v1

Every message is one UTF-8 JSON object followed by a newline. The first client message is:

```json
{"protocol":1,"token":"<64-hex-character-token>"}
```

The server replies with the negotiated protocol and capabilities. Subsequent requests have an ID:

```json
{"id":"request-1","command":"move","forward":1,"strafe":0,"ticks":20,"sprint":false}
```

A response echoes the request ID:

```json
{"id":"request-1","ok":true,"result":{"accepted":true,"remaining_ticks":20,"max_ticks":40}}
```

Supported commands:

| Command | Arguments | Effect |
|---|---|---|
| `status` | none | Player position, rotation, health, velocity, dimension, world tick |
| `scene_snapshot` | optional `radius` (1–32, default 16) | One client-thread snapshot of player state, nearby entities and blocks around the player |
| `capture_screenshot` | none | Captures the current render target to the fixed companion capture file and returns PNG image content to MCP |
| `move` | `forward`, `strafe` (-1..1), `ticks` (1..40), optional `jump`, `sprint`, `sneak` | Holds normal in-game movement mappings for a bounded duration |
| `look` | `yaw` (-180..180), `pitch` (-90..90) | Adjusts the local test player's view |
| `stop` | none | Releases bridge-owned movement mappings |
| `entities` | optional `radius` (1..32, default 16) | Lists up to 50 nearby entities |
| `inspect_entity` | `uuid` | Reads one nearby/loaded entity |
| `entity_attributes` | `uuid` | Reads server-authoritative base/effective values for the supported mob attributes |
| `set_entity_attribute` | `uuid`, `attribute`, `value`, `confirm: true` | Changes one allowlisted generated-mob base attribute; max health 1–1024, attack damage 0–256, movement speed 0–4 |
| `reset_entity_attributes` | `uuid`, `confirm: true` | Restores max health, attack damage and movement speed from the generated mob's static `Rig` defaults |
| `trigger_animation` | `uuid`, `animation_id` | Invokes the generated mob's fixed animation trigger on the integrated server |
| `block` | integer `x`, `y`, `z` | Reads one nearby block within 64 blocks of the player |
| `command_catalog` | `offset`, `limit` | Paginates the live integrated-server Brigadier root command catalog; read-only |
| `command_inspect` | `name` | Returns usage paths and child nodes for one command root; read-only |
| `command_validate` | `command` | Parses syntax only; never dispatches or executes the command |

## Security and limitations

- Bind address is hard-coded to IPv4 loopback; the server rejects non-loopback peers.
- The bearer token is random per launch and compared in constant time. The connection file is deleted when the client stops, if it still contains this launch's token.
- One client at a time; maximum 8 outstanding requests; maximum 120 requests per minute; maximum JSON line size 8 KiB.
- The bridge exposes only read-only inspection of the Brigadier dispatcher. It does not expose a generic command execution/dispatch operation, caller-controlled reflection, arbitrary code, arbitrary filesystem operations, or multiplayer access. The animation adapter invokes one fixed generated method signature; the reset adapter reads only the three fixed Rig constant fields. Callers cannot choose a class, method, or field name.
- Attribute writes change an entity's base attributes and may be persisted with the world save. Use only disposable test worlds; do not use a valuable survival world.
- The companion still does **not** spawn/despawn entities, place/break blocks, or save/replay sessions. Those remain later milestones.
- Do not use this companion in a valuable survival world. The intended target is a disposable creative test world. The command-intelligence prototype does not execute world-changing commands.

The 0.2.0 baseline passed GitHub Actions build [44914031176](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914031176). The 0.3.0 reset extension passed build [44914638220](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914638220); artifact [mms-live-debugger-0.3.0.jar](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914638220/artifacts/14711415756) has SHA-256 `12c129000fb9bf7ef4fab76226b0935dad533e764cf3d80795699682072765d1`. The final PR-head run [44916284480](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916284480) passed 15 Python tests, tool compilation and Fabric packaging; artifact [14712390413](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44916284480/artifacts/14712390413) contains the inspected 0.3.0 JAR. A successful compile still does not prove server-thread mutations, reset behavior or animation synchronization in an actual world; those require separate manual runtime acceptance.

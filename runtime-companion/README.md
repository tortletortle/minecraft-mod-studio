# MMS Live Game Debugger — Runtime Companion

The runtime companion is an optional client-only Fabric mod that gives a local AI agent a narrow, authenticated control channel into a **single-player test world**. It is separate from the existing Mod Studio editor and does not modify generated production JARs.

## Runtime companion 0.2.0

- Starts a TCP JSON-lines bridge bound exclusively to `127.0.0.1`.
- Generates a fresh 256-bit bearer token each game launch and writes it to Fabric's config directory: `config/mms-live-debugger/connection.json`.
- Allows one local agent connection, authenticated by the token.
- Exposes a fixed command allowlist; arbitrary Minecraft commands, Java execution, file access, and remote/LAN connections are not exposed.
- Requires a local integrated single-player server for every world read/control command.
- Supports player status, bounded movement, camera look, emergency stop, nearby entity inspection, entity detail inspection, and nearby block inspection.
- Adds server-authoritative mob attribute inspection and bounded attribute writes for max health, attack damage, and movement speed. Writes require `confirm: true`.
- Adds a fixed generated-mob animation trigger adapter; it calls only the generated `triggerStudioAnimation(String)` method and broadcasts through the integrated server.
- Movement input is bounded to 1–40 game ticks and is automatically released. A new movement command is rejected while one is active or while movement keys are already held by the player.

## Build

Requirements: JDK 25, Gradle 9.5.1, internet access for the pinned Minecraft/Fabric dependencies.

From this directory:

```bash
gradle --no-daemon clean build
```

The mod JAR is produced under `build/libs/` (version `0.2.0`). It is a client-only companion and requires Fabric Loader 0.20.1+, Fabric API 0.161.0+26.2, Minecraft 26.2, and Java 25.

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
| `move` | `forward`, `strafe` (-1..1), `ticks` (1..40), optional `jump`, `sprint`, `sneak` | Holds normal in-game movement mappings for a bounded duration |
| `look` | `yaw` (-180..180), `pitch` (-90..90) | Adjusts the local test player's view |
| `stop` | none | Releases bridge-owned movement mappings |
| `entities` | optional `radius` (1..32, default 16) | Lists up to 50 nearby entities |
| `inspect_entity` | `uuid` | Reads one nearby/loaded entity |
| `entity_attributes` | `uuid` | Reads server-authoritative base/effective values for the supported mob attributes |
| `set_entity_attribute` | `uuid`, `attribute`, `value`, `confirm: true` | Changes one allowlisted mob base attribute; max health 1–1024, attack damage 0–256, movement speed 0–4 |
| `trigger_animation` | `uuid`, `animation_id` | Invokes the generated mob's fixed animation trigger on the integrated server |
| `block` | integer `x`, `y`, `z` | Reads one nearby block within 64 blocks of the player |

## Security and limitations

- Bind address is hard-coded to IPv4 loopback; the server rejects non-loopback peers.
- The bearer token is random per launch and compared in constant time. The connection file is deleted when the client stops, if it still contains this launch's token.
- One client at a time; maximum 8 outstanding requests; maximum 120 requests per minute; maximum JSON line size 8 KiB.
- The bridge does not expose a command dispatcher, caller-controlled reflection, arbitrary code, arbitrary filesystem operations, or multiplayer access. The animation adapter invokes one fixed generated method signature only.
- Attribute writes change an entity's base attributes and may be persisted with the world save. Use only disposable test worlds; do not use a valuable survival world.
- The companion still does **not** spawn/despawn entities, place/break blocks, or save/replay sessions. Those remain later milestones.
- Do not use this companion in a valuable survival world. The intended target is a disposable creative test world.

The 0.2.0 source passed GitHub Actions build [44914031176](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914031176). The resulting [mms-live-debugger-0.2.0.jar](https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44914031176/artifacts/14710788309) has SHA-256 `f10018e5af2deca3e2d0fd424727fb85e2b803dba36f84c17b35b87b4776652b`. A successful compile still does not prove server-thread mutations or animation synchronization behave correctly in an actual world; those require the separate manual runtime acceptance.

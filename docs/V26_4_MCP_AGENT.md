# V2.6.4 — Live Debugger MCP Agent

## Purpose

The Fabric companion already exposes a narrow authenticated TCP protocol. This milestone adds a stdio MCP adapter so a compatible local AI agent can use that protocol as typed tools. The agent does not need to click Minecraft controls or operate the desktop UI.

This is separate from AI Debug Lab's /mms ask chat relay:

- /mms ask sends a player's question and a small read-only target/item context to a desktop or local-model responder.
- Live Debugger MCP gives an authorized local agent explicit status, inspection and bounded control tools.

Neither path implies unrestricted game access.

V2.6.5 builds on this typed MCP layer with one-call scene snapshots, a screenshot-to-image tool, movement with before/after verification, short-lived authorization for transient controls, and Cursor-specific installation/diagnostics. See [V2.6.5 Agent Experience](V26_5_AGENT_EXPERIENCE.md).

## Prerequisites

- Minecraft Java 26.2, Java 25, Fabric Loader 0.20.1+, Fabric API 0.161.0+26.2.
- The optional mms-live-debugger-0.3.0.jar installed in a separate Fabric client.
- A single-player Creative test world that contains no valuable builds or items.
- Python 3.12+ and the pinned MCP SDK dependency.

Install the optional MCP dependency from the repository root:

    python -m pip install -r runtime-companion/requirements-mcp.txt

Launch Minecraft and wait for the companion log entry:

    [MMS Live Debugger] READY

The companion creates:

    <instance>/config/mms-live-debugger/connection.json

This file contains a per-launch 256-bit bearer token. Treat it as a password. Do not paste it into chat, commit it, or share it with an untrusted process.

## Register the MCP server

For Codex CLI, run from the repository root and substitute the actual instance path:

    codex mcp add minecraft-live-debugger -- python -B runtime-companion/tools/live_debugger_mcp.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json"

Other MCP clients can launch the same Python script using stdio transport. The server reads the connection file on each tool call, so restarting the Minecraft client and regenerating its token does not require a permanently cached TCP session; update the configured path if the instance path changes.

## Tools

| MCP tool | Capability | Safety boundary |
|---|---|---|
| **mms_game_status** | Player position, health, rotation, velocity, dimension and tick | Read-only |
| **mms_get_scene_snapshot** | One coherent client-thread snapshot of player, nearby entities and surrounding blocks | Read-only |
| **mms_capture_screenshot** | Capture the current render target and return PNG image content | Read-only; fixed capture path, no arbitrary file reads |
| **mms_authorize_transient_controls** | Authorize bounded movement, camera and animation actions for 30–600 seconds | Requires explicit confirm=true; in-memory expiry |
| **mms_move_player_and_verify** | Execute bounded movement and return before/after state and observed displacement | Requires transient authorization or per-call confirm=true |
| **mms_list_nearby_entities** | Up to 50 loaded entities within 1–32 blocks | Read-only |
| **mms_inspect_entity** | Read one loaded entity by UUID | Read-only |
| **mms_inspect_block** | Read one block within 64 blocks | Read-only |
| **mms_read_entity_attributes** | Read generated mob base/effective attributes | Read-only |
| **mms_move_player** | Low-level bounded movement | Requires transient authorization or per-call confirm=true; 1–40 ticks; auto-release |
| **mms_look_player** | Change player yaw/pitch | Requires transient authorization or per-call confirm=true; bounded angles |
| **mms_stop_player** | Release debugger-owned movement keys | Emergency stop; no confirmation required |
| **mms_set_entity_attribute** | Set max health, attack damage or movement speed | Requires confirm=true; fixed numeric bounds; may persist in world save |
| **mms_reset_entity_attributes** | Restore the three generated Rig defaults | Requires confirm=true; may clamp current health |
| **mms_trigger_animation** | Trigger a generated mob animation by ID | Requires transient authorization or per-call confirm=true; does not prove rendered pose quality |

There is deliberately no generic command-dispatch tool, arbitrary Java execution, block placement/breaking, entity spawn/despawn, file access, LAN listener, or multiplayer control.

## Recommended agent procedure

1. Call mms_get_scene_snapshot for a one-call view of player, nearby entities and nearby blocks.
2. Use mms_list_nearby_entities only when a narrower or refreshed entity list is needed. Keep UUIDs tied to the current world session.
3. Inspect a target before acting.
4. Use read-only attribute inspection before considering any tuning.
5. Ask the operator before any persistent attribute change. Only use a disposable Creative world.
6. Prefer mms_move_player_and_verify for movement; inspect its before/after position and distinguish completed input from observed displacement. Call mms_stop_player immediately if movement is no longer needed.
7. Use mms_capture_screenshot when rendered appearance matters. Do not infer rendered animation success from a server-side trigger acknowledgement.

Transient movement, camera and animation controls can use a short-lived authorization granted by mms_authorize_transient_controls after explicit approval; alternatively, each action can carry confirm=true. Persistent attribute writes and resets always require per-call confirm=true. The transient authorization expires after 30–600 seconds or when the MCP server exits. It is not a substitute for operator judgment.

## Validation boundary

Automated tests use a local fake TCP peer to verify MCP tool discovery, argument validation, confirmation gates, command mapping and response forwarding. These tests do not launch Minecraft.

The Fabric build and Python protocol tests do not prove actual player movement, client/server attribute convergence, animation rendering or shutdown cleanup. Those remain separate real-game acceptance gates in V2.6 runtime acceptance. Do not mark the runtime debugger complete until those checks have evidence from the disposable Minecraft 26.2 instance.

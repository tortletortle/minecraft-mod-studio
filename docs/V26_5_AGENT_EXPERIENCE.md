# V2.6.5 — Cursor Agent Experience

## Goal

Reduce the number of decisions and tool calls Cursor must make to inspect and control a local Minecraft 26.2 single-player test world. This milestone improves the agent-facing layer without replacing the authenticated Fabric bridge from V2.6 or the typed MCP adapter from V2.6.4.

## What changed

### 1. One-call scene snapshot

**mms_get_scene_snapshot(radius=16)** returns, from one Minecraft client-thread capture:

- Player UUID, coordinates, rotation, health, velocity and movement state.
- Dimension and game tick.
- Up to 50 nearby loaded entities within the requested radius.
- Blocks below the feet, at the feet and near the player's head.
- Entity truncation and snapshot-consistency metadata.

This is a client-world observation. It is not a claim that every value is server-authoritative. Generated-mob attribute reads and writes retain their separate integrated-server execution path.

### 2. Movement with a verification loop

**mms_move_player_and_verify(...)** wraps the lower-level move command with:

1. A pre-action status snapshot.
2. A bounded movement request.
3. Polling until the requested game ticks have elapsed or movement is interrupted.
4. A final status snapshot.
5. Position delta, distance moved, completion state and a failure reason.

**movement_completed=true** means the requested movement duration completed and the bridge released its input. **movement_observed=true** means a position change greater than 0.05 blocks was observed. A completed input interval can still produce no displacement when the player is blocked by terrain. The tool does not claim pathfinding or obstacle avoidance.

### 3. Visual evidence

**mms_capture_screenshot()** asks the Fabric client to capture the current render target and returns a PNG as standard MCP image content. The file is fixed at:

    <instance>/config/mms-live-debugger/capture.png

It is overwritten by the next capture. The caller cannot choose an arbitrary path or read arbitrary files. The MCP adapter rejects symlinks, non-PNG data and images larger than 8 MiB.

Cursor's current MCP documentation supports image content from MCP tools. Actual inline rendering can still depend on the installed Cursor build; if the UI does not display the image, check whether the model receives the image content before treating it as a Fabric capture failure.

### 4. Short-lived transient authorization

**mms_authorize_transient_controls(confirm=true, duration_seconds=120)** creates an in-memory authorization window of 30–600 seconds for:

- Bounded player movement.
- Camera look.
- Generated animation triggers.

The authorization expires automatically and is lost when the MCP server process exits. The authorization tool itself must remain approval-gated. Persistent entity attribute writes and resets still require per-call confirm=true; the transient session does not authorize them.

**mms_stop_player()** remains available without application-level confirmation and releases debugger-owned movement keys.

### 5. Cursor installation and diagnosis

Install the pinned MCP dependency:

    python -m pip install -r runtime-companion/requirements-mcp.txt

Start Minecraft with the companion installed, enter a disposable single-player Creative world, and wait for [MMS Live Debugger] READY. Then run from the repository root:

    python runtime-companion/tools/install_cursor_mcp.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --scope workspace --workspace .

The installer:

- Writes a workspace .cursor/mcp.json stdio entry using the current Python interpreter.
- Preserves other MCP server entries.
- Stores only the connection-file path, never the bearer token.
- Does not overwrite malformed existing JSON.
- Does not change Cursor approval policy by default.

To opt into automatic approval for read-only inspection and the emergency stop only:

    python runtime-companion/tools/install_cursor_mcp.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --scope workspace --workspace . --allow-safe-tools-without-approval

This optional flag writes .cursor/permissions.json with an MCP allowlist for the read-only tools and mms_stop_player. Cursor's permissions.json MCP allowlist takes precedence over the in-app allowlist, so review any existing permissions policy before enabling it.

For a smoother but still bounded workflow, you may separately pass --allow-transient-actions-without-approval. This adds mms_move_player, mms_move_player_and_verify, mms_look_player and mms_trigger_animation to the allowlist. The mms_authorize_transient_controls tool itself remains approval-gated, so the agent must obtain explicit authorization before those tools work; persistent attribute writes and resets remain excluded. Do not enable this option unless you are comfortable with the agent carrying out transient movement and animation actions during an explicitly authorized short session.

Restart Cursor, then diagnose the installation:

    python runtime-companion/tools/diagnose_cursor_mcp.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --scope workspace --workspace .

The diagnostic reports Python/MCP availability, Cursor registration, optional safe-tool allowlisting, bridge connectivity and advertised capabilities. It never prints the bearer token.

Cursor MCP references:
- https://cursor.com/docs/mcp
- https://cursor.com/docs/reference/permissions

## Agent operating procedure

1. Call mms_get_scene_snapshot before planning a world interaction.
2. Use the returned UUIDs only for the current world session; inspect a target before modifying it.
3. Use mms_capture_screenshot when rendered appearance matters. A server-side animation acknowledgement is not visual proof.
4. For bounded player movement, obtain a transient authorization or explicit per-call confirmation, then prefer mms_move_player_and_verify over raw mms_move_player.
5. If movement is interrupted or cannot be verified, stop and report the observed reason. Do not repeat an action indefinitely.
6. Keep persistent attribute writes behind per-call confirmation and use a disposable world.
7. Call mms_stop_player immediately if movement should end.

## Validation boundaries

Automated MCP tests use a fake local TCP peer. They can prove tool discovery, input validation, confirmation/session gates, command mapping, polling behavior, response aggregation and image-content packaging. They do not launch Minecraft or prove that the Fabric screenshot callback, player physics, client/server synchronization or animation rendering works in a real client.

The Fabric Gradle build is a compile/package check. The real-game acceptance gates remain mandatory:

- [ ] Windows Minecraft 26.2 / Java 25 / Fabric instance starts with the exact candidate JAR.
- [ ] scene_snapshot returns plausible player, entity and block data in a disposable world.
- [ ] Screenshot capture returns a decodable PNG and the Cursor model can inspect the frame.
- [ ] A 5–10 tick move changes position in an unobstructed area and reports correct before/after evidence.
- [ ] A deliberately blocked move reports completion separately from observed displacement.
- [ ] Opening a screen or interrupting the client releases movement input safely.
- [ ] Transient authorization expires at its deadline and does not authorize persistent attribute writes.
- [ ] Multiplayer remains rejected and the connection file is removed on clean shutdown.

Do not mark V2.6.5 as fully accepted until these checks have Windows evidence. Do not merge this stacked draft automatically.

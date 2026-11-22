# V2.6 — Live runtime acceptance

The repository now includes a smoke-test client for the built companion JAR. This checks the live protocol against an actual Minecraft 26.2 client; it is not a substitute for observing movement or rendered animation in game.

## 1. Prepare a disposable instance

1. Use a separate Fabric 26.2 instance with Java 25.
2. Install the matching **mms-live-debugger-0.4.0.jar** candidate in its mods directory.
3. Launch a single-player Creative test world.
4. Wait for the log line **[MMS Live Debugger] READY**.
5. Keep the connection file private. Its token authorizes local control.

## 2. Run read-only smoke checks

From the repository root:

```powershell
python runtime-companion/tools/runtime_acceptance.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --report artifacts\runtime-acceptance.json
```

The script checks:
- protocol version and required command capabilities;
- player status and finite position values;
- one-call scene snapshot with nearby entities and blocks around the player;
- nearby entity listing;
- block inspection at the player's current block coordinates;
- asynchronous render-target screenshot capture, PNG signature/size validation and SHA-256 evidence.

A successful result is a JSON report with each check marked PASS. The screenshot is written to the fixed companion path config/mms-live-debugger/capture.png and is not copied to an arbitrary caller-selected location. A connection failure must produce a failing report and non-zero exit code.

## 3. Inspect a generated mob

Find a generated mob UUID from the nearby entity list, then run:

```powershell
python runtime-companion/tools/runtime_acceptance.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --mob-uuid "<mob-uuid>" --report artifacts\runtime-mob-acceptance.json
```

This adds entity identity and server-authoritative attribute reads.

## 4. Trigger a generated animation

Use an animation ID that actually exists in that mob's Rig:

```powershell
python runtime-companion/tools/runtime_acceptance.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --mob-uuid "<mob-uuid>" --animation-id "attack"
```

A PASS means the server method accepted the animation ID. It does not prove the rendered pose is correct. Observe the mob in game and retain a screenshot or short recording.

## 5. Exercise one reversible attribute write

Only do this in a disposable test world. The script intentionally limits the probe to **attack_damage** or **movement_speed**; it:
1. reads the original base value;
2. verifies that a write without confirmation is rejected;
3. writes a nearby in-range probe value with explicit confirmation;
4. reads the changed value;
5. restores the exact original base value in a finally path and verifies restoration.

```powershell
python runtime-companion/tools/runtime_acceptance.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --mob-uuid "<mob-uuid>" --exercise-attribute attack_damage --allow-world-mutation --report artifacts\runtime-write-acceptance.json
```

The process could still be interrupted between write and restore. The test world must therefore be disposable.

## 6. Test generated-default reset separately

Follow [V2.6.2 generated-default reset](V26_2_RUNTIME_TUNING.md). This operation resets all three supported base attributes to the generated Rig constants and may clamp current health. It is intentionally not run automatically by the reversible smoke test.

## 7. Cursor Agent checks

Install the Cursor MCP configuration using [V2.6.5 Agent Experience](V26_5_AGENT_EXPERIENCE.md). In the disposable world:
- call mms_get_scene_snapshot and compare its player/entity/block observations with the visible world;
- call mms_capture_screenshot and verify the Cursor model receives the current frame;
- obtain an explicitly approved transient authorization, then call mms_move_player_and_verify for 5–10 ticks in an unobstructed area;
- repeat against a wall and verify movement_completed is distinguished from movement_observed;
- verify the transient authorization expires and does not permit persistent attribute writes.

## 8. Manual player-control checks

The smoke script does not move the player. Verify these manually using the CLI:
- status before movement;
- move with a small 5–10 tick duration;
- stop;
- status after movement;
- open a screen during a move and confirm bridge input is released;
- disconnect the agent during movement and confirm the 40-tick cap releases input;
- connect to a multiplayer server and confirm world commands are rejected.

Record the exact game version, JAR SHA-256, world setup, commands, outputs, screenshots and any failures. Do not convert a compile pass into a runtime pass.

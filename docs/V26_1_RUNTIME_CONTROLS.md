# V2.6.1 — Integrated-server mob controls

This document defines the second runtime-companion slice. It is an optional, local-only development tool for a disposable Minecraft 26.2 single-player test world.

## Preconditions

1. Build and install the matching `mms-live-debugger` companion JAR into a separate Fabric 26.2 instance.
2. Launch a single-player Creative test world with a generated mob already spawned.
3. Read the connection-file path from the startup log line beginning `[MMS Live Debugger] READY`.
4. Use the exact UUID returned by the `entities` command or the generated mob's entity inspection output.

The connection file contains a bearer token that authorizes control of the local test client. Do not publish it or send it to an untrusted service.

## Read mob attributes

```powershell
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\\path\\to\\instance\\config\\mms-live-debugger\\connection.json" --command entity_attributes --args "{\\"uuid\\":\\"<mob-uuid>\\"}"
```

The response reports base and effective values for:

| Attribute key | Allowed base range |
|---|---:|
| `max_health` | 1–1024 |
| `attack_damage` | 0–256 |
| `movement_speed` | 0–4 |

`base` is the entity's base attribute value before modifiers; `effective` is the value after modifiers.

## Change one attribute

A write requires the explicit per-request field `confirm: true`:

```powershell
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\\path\\to\\instance\\config\\mms-live-debugger\\connection.json" --command set_entity_attribute --args "{\\"uuid\\":\\"<mob-uuid>\\",\\"attribute\\":\\"max_health\\",\\"value\\":80,\\"confirm\\":true}"
```

The server rejects:
- missing confirmation;
- unknown attribute names;
- values outside the fixed range;
- targets that are not living mobs, are dead/removed, are in another dimension, or are more than 64 blocks away;
- multiplayer sessions.

The command changes the entity's base attribute on the integrated-server thread. Base attribute changes may be written with the world save. Use disposable worlds only.

## Trigger a generated animation

Generated mob classes expose a fixed public `triggerStudioAnimation(String)` method. The companion calls this exact method on the integrated-server thread; the generated method broadcasts the animation event to the client.

```powershell
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\\path\\to\\instance\\config\\mms-live-debugger\\connection.json" --command trigger_animation --args "{\\"uuid\\":\\"<mob-uuid>\\",\\"animation_id\\":\\"attack\\"}"
```

The animation ID must exist in that mob's generated rig. A successful command response means the generated server method accepted the ID; it does not prove that the rendered pose looks correct. Confirm the visible pose change in the game and retain a screenshot or recording.

## Protocol safety

- These commands are added to the fixed protocol allowlist; they do not expose a Minecraft command dispatcher.
- The only reflective call is the fixed method name and signature above. Callers cannot choose a class, method, or parameter type.
- All entity-control commands are restricted to a live mob in the player's current dimension within 64 blocks.
- Server mutations are scheduled on the integrated-server thread. The local client waits at most three seconds for a response.
- No entity spawning/despawning, block placement/breaking, arbitrary code, filesystem access, or multiplayer control is implemented.

## Runtime acceptance checklist

- [ ] `entity_attributes` returns the expected values for a known generated mob.
- [ ] `set_entity_attribute` without `confirm: true` returns `CONFIRM_REQUIRED`.
- [ ] An unknown attribute returns `ATTRIBUTE_NOT_ALLOWED`.
- [ ] An out-of-range value is rejected before any world mutation.
- [ ] A valid max-health update changes the server base/effective value and clamps current health if necessary.
- [ ] The client observes the updated mob attributes after synchronization.
- [ ] A known animation ID triggers and visibly changes the mob pose.
- [ ] An unknown animation ID returns `ANIMATION_NOT_FOUND`.
- [ ] A non-generated mob returns `ANIMATION_CONTROL_UNSUPPORTED`.
- [ ] A target outside 64 blocks is rejected.
- [ ] Multiplayer remains rejected with `SINGLEPLAYER_ONLY`.

These are pending runtime checks until recorded against the actual 26.2 test instance. Source inspection and Gradle compilation do not satisfy them.

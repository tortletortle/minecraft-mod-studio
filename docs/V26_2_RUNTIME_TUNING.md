# V2.6.2 — Restore generated mob defaults

The 0.3.0 runtime companion adds a safe recovery operation for generated mob attribute tuning.

## Command

```powershell
python runtime-companion/tools/live_debugger_client.py --connection-file "C:\path\to\instance\config\mms-live-debugger\connection.json" --command reset_entity_attributes --args '{"uuid":"<mob-uuid>","confirm":true}'
```

The command restores only the three supported base attributes from the generated mob's matching **Rig** class:

| Attribute | Generated Rig field |
|---|---|
| max_health | MAX_HEALTH |
| attack_damage | ATTACK_DAMAGE |
| movement_speed | MOVEMENT_SPEED |

The adapter derives the Rig class from the generated entity class name by replacing the fixed **Entity** suffix with **Rig**. It reads only the three fixed public static final **double** fields. No class name or field name is supplied by the agent.

## Safety behavior

- Requires confirm=true.
- Requires a live generated Studio mob in the player's current dimension and within 64 blocks.
- Requires the mob's fixed generated animation marker method, used as the generated-entity identity check.
- Rejects missing or malformed generated Rig classes/fields and defaults outside the same allowlisted numeric bounds.
- Runs on the integrated-server thread.
- If current health exceeds the restored max health, current health is clamped to the restored maximum; it is not automatically refilled.
- Does not reset AI state, animation state, position, equipment, effects, or other modded attributes.

## Verification

The response includes each previous base value, the generated default, the effective value after modifiers, and final current health. The command's response confirms that the server-side method completed; it does not prove the client has rendered the updated mob yet.

## Pending runtime checks

- [ ] Tune all three attributes away from their generated defaults.
- [ ] Run the reset command with confirm=true.
- [ ] Verify the returned base values exactly match the generated Rig constants.
- [ ] Verify client-observed attributes converge to the server values.
- [ ] Verify max-health clamping does not refill health.
- [ ] Verify missing/invalid generated Rig metadata fails closed without partial writes.
- [ ] Verify omission of confirm=true causes no mutation.

Use a disposable Creative test world. Base attribute writes may persist with the world save.

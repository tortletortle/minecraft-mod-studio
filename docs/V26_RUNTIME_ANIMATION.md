# V2.6 runtime animation correction

Date: 2026-11-20

## Confirmed evidence from the previous client GameTest

The idle and walk screenshots were not identical. Their 100x160 mob-region crop had 1,286 pixels with a channel difference >= 10 (8.04%). However, the HUD/chat overlay obscured the lower body and the pose delta was not visually obvious at normal scale. This is why the next test uses a fixed 1280x720 window, hides the HUD, and compares idle with attack pose.

## Generator correction

The generated EntityModel previously computed the idle/walk locomotion blend and then unconditionally overlaid the active synchronized animation at weight 1.0. Since the state machine uses the same idle/walk clips, this could bypass the smooth locomotion blend.

The generator now skips the state-machine overlay when the active animation equals the configured idle or walk clip. Locomotion remains driven by walkAnimationSpeed and the generated smoothstep blend. Non-locomotion actions (for example attack) still overlay the corresponding bone tracks.

## New acceptance checks

- Source-generation regression asserts the locomotion exclusion guard exists.
- The real client GameTest spawns the mob in a disposable singleplayer world, hides HUD, captures idle and attack poses from a fixed camera, and verifies server-to-client attack animation sync.
- A Pillow visual-delta check requires at least 120 changed pixels and 0.1% of the central mob crop to change.
- Server-side registration, placement, spawn, attributes, melee damage/cooldown and out-of-range checks remain unchanged.

The screenshot delta only proves that two rendered poses differ. It does not prove animation smoothness, correct attack timing, material correctness or general gameplay quality.

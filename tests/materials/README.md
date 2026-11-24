# Specialized material and locomotion acceptance

Reproduce from the actual V2.5 HTML; first run the existing browser export test, then:

    python -m pip install playwright Pillow
    python -m playwright install chromium
    python tests/materials/material_fixture.py --html Minecraft_Mod_Studio_V19.html --baseline /tmp/mms-export/studio-project.json --out /tmp/mms-material
    python /tmp/mms-material/project/studio_build.py build

Actual local execution with Chromium, Node-independent Studio compiler in-browser, JDK 21 pure Rig harness: 9 pixel checks, 5 source wiring checks, 797 numerical assertions, source integrity PASS, expected JAR entries 48. The 797 are individual assertions over 61 ticks, five speeds and endpoint checks, not independent gameplay tests. Local output sourceSha256: 0e209bcdd2eaa870a718b39da8081544a3519c8832dd35e9720b86fc82959818. Baseline fixture UIDs vary per export. The dedicated source fixture includes translucent body pixels (alpha 128), cutout hole, emissive head, separate idle/walk clips and animation-state-machine mapping.

Observed design issue: the generated EntityModel computes a smoothstep idle/walk blend, then any active synced animation with a matching track overrides the same bone with weight 1, including locomotion clips when triggered by the state machine. This is a source-level design conflict; real client/world reproduction not yet performed, semantics not yet changed. ORM remains a sidecar. No EULA is accepted; no world is opened.

A separate workflow builds this fixture with the real Fabric toolchain. Its result must be read separately from the default fixture build and the running client boot probe.

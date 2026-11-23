# UMPD real-mod corpus plan v0.1

## Purpose

Measure protocol-discovery performance on real Minecraft Java mod JARs. The goal is not to show that a scanner can find strings in a few hand-picked examples; it is to estimate how often it identifies protocol evidence across a stratified set of real projects and to expose false positives and false negatives.

## Sampling frame

Use the most-downloaded Modrinth Fabric projects as the popularity frame, then stratify by function so the corpus is not dominated by performance mods and libraries.

A current third-party Modrinth-data tracker reported, on 2026-11-22, that 206 of the top 300 Fabric projects had a release build for Minecraft 26.2 (68.7%), with 15 pre-release-only, 3 available only on another loader, and 76 not yet updated. This is useful for planning a 26.2 cohort, but it is not a substitute for verifying each project's exact downloadable artifact: [Modshift Minecraft 26.2 readiness](https://modshift.app/version/26.2).

The candidate list is in [corpus/manifest.csv](../../experiments/umpd-scanner/corpus/manifest.csv). It deliberately spans:
- foundation APIs and libraries;
- configuration frameworks;
- performance and rendering;
- UI, inventory, and map tools;
- resource-pack and animation-heavy mods;
- world generation and content;
- technology, storage, and gameplay;
- server administration tools.

The manifest currently contains 42 candidates. It is a sampling frame only. Each row remains PENDING until an exact version/loader artifact and checksum have been recorded.

## Version namespace caveat

The primary 26.2 cohort is suitable for direct named class-reference scanning: Fabric's documentation says mappings are relevant for obfuscated games before 26.1, while 26.1+ is unobfuscated. Do not silently pool older Fabric JARs into the 26.2 precision/recall result. Historical artifacts commonly contain Intermediary names and need a version-specific mapping adapter before comparing class signatures. UMPD 0.1.0 has no such adapter yet.

References: [Fabric mappings guide](https://docs.fabricmc.net/develop/porting/mappings/index), [Fabric Loom remapJar](https://docs.fabricmc.net/develop/loom/).

## Cohort rules

1. **Primary cohort:** Fabric JARs with an explicitly published Minecraft 26.2-compatible file.
2. **Secondary cohort:** the latest stable Fabric JAR for projects without a 26.2 file. Keep these results separate; do not mix version cohorts in the headline 26.2 rate. For pre-26.1 artifacts, require a version-matched Tiny v2 mapping file and record the mapping SHA-256; otherwise label protocol scans as mapping-unresolved.
3. **Loader comparison cohort:** where a project publishes both Fabric and NeoForge artifacts for the same Minecraft version, keep them as separate artifacts and record the loader explicitly.
4. Include both library/API projects and end-user content mods. Avoid selecting only projects already known to use Codec.
5. Do not commit mod JARs to Git. Record source URL, version ID, file name, size, SHA-256, loader, and game version in the manifest.

## Ground-truth audit

For each sampled JAR, manually inspect at least:
- loader metadata;
- config resources and configuration API references;
- data/ and assets/ resource paths;
- class-file references to Codec, StreamCodec, NBT, Registry, DataComponentType, SavedData, and attachment APIs;
- nested JARs and relocated/shaded dependencies.

Label every protocol finding as:
- TRUE_POSITIVE: scanner signal corresponds to a real type/API reference in the artifact;
- FALSE_POSITIVE: signal is incidental, string-only, shaded metadata, or otherwise not evidence of actual protocol use;
- FALSE_NEGATIVE: manual audit finds a protocol reference the scanner missed;
- UNRESOLVED: insufficient evidence to decide.

A constant-pool type reference is still not proof that a method path executes. The ground truth should distinguish type presence, member reference, and confirmed call-site usage.

## Metrics

Report per protocol and overall:

- Detection precision = TP / (TP + FP)
- Detection recall = TP / (TP + FN)
- Artifact coverage = artifacts with at least one confirmed protocol / audited artifacts
- Field/schema recall is **not applicable** to v0.1.0 because the scanner does not infer schemas.
- Safe write success is **not applicable** because the scanner is read-only.

Publish the numerator, denominator, cohort size, version distribution, and unresolved count. Never report a percentage without its denominator.

## Acceptance gates

- Gate A: scanner builds and synthetic tests pass.
- Gate B: at least 30 real artifacts are pinned by version ID and SHA-256.
- Gate C: at least 10 artifacts have independent manual protocol audits, including negative and false-positive cases.
- Gate D: precision/recall are reported per protocol; false-positive causes are grouped and addressed.
- Gate E: only after Gate D should the signature set be expanded or a semantic bytecode analyzer be considered.

## Current status

- Scanner source: implemented on branch research/umpd-static-scanner.
- Local JDK 21 compilation: passed.
- Historical baseline synthetic self-tests: 4/4 passed. Current branch has 9 self-test cases; a fresh compile/run is pending.
- Gradle/GitHub Actions: pending; current GitHub job records show runner_id=0 and zero executed steps, so no Gradle task has run.
- Real JAR corpus: not yet downloaded or scanned.
- Manual ground truth: not yet established.

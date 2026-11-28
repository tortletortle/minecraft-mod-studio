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

The manifest currently contains 42 candidates. It is a sampling frame only. Each row remains PENDING until an exact version/loader artifact and checksum have been recorded. The PowerShell fetcher now resumes from the local version-specific manifest, reuses only hash-verified local files, and re-fetches missing/corrupt artifacts by the previously pinned Modrinth version ID rather than silently upgrading.

## Version namespace caveat

The primary 26.2 cohort is suitable for direct named class-reference scanning: Fabric's documentation says mappings are relevant for obfuscated games before 26.1, while 26.1+ is unobfuscated. Do not silently pool older Fabric JARs into the 26.2 precision/recall result. Historical artifacts commonly contain Intermediary names. UMPD accepts a version-matched Tiny v2 mapping file and normalizes exact class names plus descriptor types; it does not remap field or method names. Record the mapping file SHA-256 and both namespace names with every historical scan.

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
- exact-package class/member references and direct invoke instructions for Codec, StreamCodec/PacketCodec, NBT, Registry, DataComponentType, SavedData, and attachment APIs;
- nested JARs and relocated/shaded dependencies.

Label every protocol finding as:
- TRUE_POSITIVE: scanner signal corresponds to a real type/API reference in the artifact;
- FALSE_POSITIVE: signal is incidental, string-only, shaded metadata, or otherwise not evidence of actual protocol use;
- FALSE_NEGATIVE: manual audit finds a protocol reference the scanner missed;
- UNRESOLVED: insufficient evidence to decide.

A constant-pool type/member reference is not proof that a method is invoked. A BYTECODE_CALL_SITE finding confirms a direct invoke instruction in a method body, but not that the method is reachable or that the branch executes. Ground truth must distinguish type presence, member reference, direct call-site presence, and runtime reachability (the latter is outside v0.1.0).

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
- Gate E: only after Gate D should the signature set be expanded or a control-flow-aware semantic bytecode analyzer be considered.

## Current status

- Scanner source: implemented on branch research/umpd-static-scanner.
- Local JDK 21 compilation: passed.
- Historical baseline synthetic self-tests: 4/4 passed. Current branch has 11 acceptance scenarios. An independent local JDK 21 harness passed 11/11; GitHub Actions still fails before runner allocation, and the Gradle workflow remains unverified.
- Gradle/GitHub Actions: pending; current GitHub job records show runner_id=0 and zero executed steps, so no Gradle task has run.
- Corpus downloader: implemented with version-ID pinning, temporary-file verification, SHA-1/SHA-256/SHA-512 checks, and resumable local manifests; PowerShell execution on Windows remains pending.
- Report auditor: implemented and passed synthetic matched/missing-file checks; it cross-checks manifest, local JAR hashes/sizes, report input directory, scanner hashes, failures, and direct call-site evidence.
- Real JAR corpus: not yet downloaded or scanned.
- Manual ground truth: not yet established.

# UMPD Static Scanner 0.1.0 — implementation record

- Date: 2026-11-23
- Branch: research/umpd-static-scanner
- Target: Minecraft Java mod JARs; Fabric-first metadata support, with Forge/NeoForge metadata recognition
- Status: source implementation and local JDK 21 compile/self-test complete; GitHub Actions and real-mod corpus validation pending

## Scope

The first UMPD milestone is a static inventory scanner. It is intentionally separate from the CodecUI schema experiment and is not wired into the production Mod Studio editor.

It scans JAR archives without extracting them, defining classes, invoking mod callbacks, running static initializers, or modifying input files.

## Version and mapping boundary

The primary target is Minecraft 26.2. Fabric's current documentation states that mappings are relevant for obfuscated games, including pre-26.1 releases; Minecraft 26.1 and newer are unobfuscated. Therefore the 26.2 cohort can match Mojang class names directly. For older Fabric releases, production mod JARs commonly use Intermediary names and require mapping-aware normalization before named API signatures can be compared. UMPD now accepts a Tiny v2 class mapping and normalizes class names plus class types inside descriptors (default intermediary → named). It does not remap field or method names; historical results must record the exact mapping file, game version, and namespace pair.

References: [Fabric mappings guide](https://docs.fabricmc.net/develop/porting/mappings/index), [Tiny v2 format specification](https://wiki.fabricmc.net/documentation%3Atiny2), [Fabric Loom remapJar](https://docs.fabricmc.net/develop/loom/).

## Detection layers

1. **Loader metadata**: Fabric fabric.mod.json; Forge/NeoForge META-INF TOML metadata. Fabric metadata is parsed with a small JSON parser. TOML parsing is deliberately limited to primary [[mods]] sections; it is not a general TOML parser.
2. **Archive and resource inventory**: outer archive entry counts, file extension counts, asset/data namespaces, common resource path categories, config path samples, and nested-JAR entry names. Embedded JARs are recursively scanned for class references up to two levels.
3. **Class-file references**: inspect CONSTANT_Class entries, field/method descriptors, and CONSTANT_Fieldref/Methodref/InterfaceMethodref owners and names for DFU Codec, StreamCodec, NBT, JSON serializers, config frameworks, item components, data attachments, SavedData, and registries.
4. **Mapping adapter**: an optional Tiny v2 reader maps class names from a selected source namespace to a target namespace. It records mapping-file SHA-256 and mapping count in the report. Field/method names are not remapped yet.
5. **Evidence provenance**: each bytecode finding records the class path, matched signatures, and the evidence level CLASS_TYPE_OR_MEMBER_REFERENCE. It is not a semantic call-graph claim.

## Safety bounds

- Maximum 1,000 JAR files per input directory.
- Maximum 512 MiB per outer JAR and 8 GiB total outer input; embedded archives are limited to 100 per outer JAR, two nested levels, 64 MiB per archive/entry, 256 MiB total embedded archive bytes, and 512 MiB total nested uncompressed bytes.
- Maximum 100,000 non-directory entries per JAR.
- Maximum 8 MiB per class file and 128 MiB total class bytes per JAR.
- Maximum 2 MiB per loader metadata file.
- Tiny v2 mapping input is limited to 128 MiB per file and 1 MiB per line.
- Maximum 1,000 evidence rows per JAR; overflow is counted.
- Maximum 200 config path samples and 100 nested-JAR path samples per artifact.
- Symbolic-link files and directories are not followed; directory traversal does not leave the selected mods root.
- Report output is rejected if placed inside the scanned mods directory.

## Local verification

The previous scanner baseline was compiled with javac --release 21 -Xlint:all and passed 4/4 self-tests. The current branch adds symlink-boundary, recursive nested-JAR, lookalike-signature, malformed constant-pool, and Tiny v2 mapping tests (9 total); these new tests and the full current source revision still require a fresh compile before being marked passed:

- nested JSON parse/write round trip;
- Fabric metadata, config/resource paths, and synthetic class/type/member references;
- NeoForge primary mod ID extraction without confusing dependency mod IDs;
- rejection of a non-directory input;
- no traversal through symlinked directories (skipped only if OS permissions prohibit creating the test symlink);
- one- and two-level embedded JAR class-reference discovery with container provenance.

These tests use generated fixture JARs. They do not establish compatibility with real mod archives or measured ecosystem coverage.

## Important limitations

- Embedded JARs are scanned for class/type/member references up to two nested levels. Nested loader metadata and full resource inventory are not yet merged into the parent artifact.
- Tiny v2 class mappings do not yet remap field or method names; class-level protocol hits are available, but some mapped member-level evidence may be missed.
- No general TOML parser.
- Constant-pool indices are structurally validated, and dynamic/method-type descriptors are inspected. No instruction-level control-flow/call-site reachability analysis, Codec graph recovery, or runtime Registry enumeration.
- Obfuscated and relocated dependencies can hide signatures.
- API type references can be present without the corresponding protocol being actively used. Findings remain heuristic.
- The first scanner does not claim that a discovered object can safely be edited or written back.

## Report contract

The scanner emits `reportVersion: 1`; the JSON Schema contract is stored at `experiments/umpd-scanner/schemas/umpd-report-v1.schema.json`. The schema distinguishes successfully scanned artifacts from per-JAR failures and documents mapping provenance, nested-JAR counters, evidence records, and bounded warning overflow. The self-test suite includes an empty-directory report contract and JSON round-trip assertion.

## Current branch additions

- Fixed directory traversal to avoid following symbolic-link directories; added a regression test.
- Added bounded in-memory nested-JAR scanning (maximum 100 embedded archives, depth 2, 64 MiB per embedded archive/entry, 256 MiB total embedded archive bytes, 512 MiB total nested uncompressed bytes).
- Added a recursive nested-JAR fixture test that checks evidence paths preserve both container levels.
- Added a Tiny v2 class-name adapter with namespace selection, mapping SHA-256 provenance, bounded input, and a synthetic intermediary-to-named integration fixture.
- Current revision self-test count: 10 cases, including recursive nested-JAR provenance, lookalike-signature rejection, malformed constant-pool index rejection, symlink-boundary coverage, and Tiny v2 intermediary-to-named class normalization. The current revision still requires a fresh compile; do not inherit the old 4/4 result as proof for this revision.

## Next acceptance stages

1. Run the GitHub Actions workflow and fix any build or test failures.
2. Scan a user-supplied copy of a real mods directory, keeping the original directory read-only.
3. Build a version-pinned 30–50 mod corpus stratified by mod category.
4. Manually audit a sample of positives and negatives; label false positives and false negatives.
5. Add stronger package/version-aware signatures and instruction-level call-site analysis.
6. Only after ground-truth labels exist, publish precision, recall, and per-domain coverage.

# UMPD Static Scanner 0.1.0 — implementation record

- Date: 2026-11-23
- Branch: research/umpd-static-scanner
- Target: Minecraft Java mod JARs; Fabric-first metadata support, with Forge/NeoForge metadata recognition
- Status: source implementation and local JDK 21 compile/self-test complete; GitHub Actions and real-mod corpus validation pending

## Scope

The first UMPD milestone is a static inventory scanner. It is intentionally separate from the CodecUI schema experiment and is not wired into the production Mod Studio editor.

It scans JAR archives without extracting them, defining classes, invoking mod callbacks, running static initializers, or modifying input files.

## Version and mapping boundary

The primary target is Minecraft 26.2. Fabric's current documentation states that mappings are relevant for obfuscated games, including pre-26.1 releases; Minecraft 26.1 and newer are unobfuscated. Therefore the 26.2 cohort can match Mojang class names directly. For older Fabric releases, production mod JARs commonly use Intermediary names and require mapping-aware normalization before named API signatures can be compared. UMPD 0.1.0 does not yet perform that normalization, so historical-version results must remain a separate cohort until a mapping adapter is implemented.

References: [Fabric mappings guide](https://docs.fabricmc.net/develop/porting/mappings/index), [Fabric Loader MappingResolver](https://docs.fabricmc.net/develop/loader/), [Fabric Loom remapJar](https://docs.fabricmc.net/develop/loom/).

## Detection layers

1. **Loader metadata**: Fabric fabric.mod.json; Forge/NeoForge META-INF TOML metadata. Fabric metadata is parsed with a small JSON parser. TOML parsing is deliberately limited to primary [[mods]] sections; it is not a general TOML parser.
2. **Archive and resource inventory**: top-level archive entry counts, file extension counts, asset/data namespaces, common resource path categories, config path samples, and nested-JAR entry names.
3. **Class-file references**: inspect CONSTANT_Class entries, field/method descriptors, and CONSTANT_Fieldref/Methodref/InterfaceMethodref owners and names for DFU Codec, StreamCodec, NBT, JSON serializers, config frameworks, item components, data attachments, SavedData, and registries.
4. **Evidence provenance**: each bytecode finding records the class path, matched signatures, and the evidence level CLASS_TYPE_OR_MEMBER_REFERENCE. It is not a semantic call-graph claim.

## Safety bounds

- Maximum 1,000 JAR files per input directory.
- Maximum 512 MiB per JAR and 8 GiB total compressed input.
- Maximum 100,000 non-directory entries per JAR.
- Maximum 8 MiB per class file and 128 MiB total class bytes per JAR.
- Maximum 2 MiB per loader metadata file.
- Maximum 1,000 evidence rows per JAR; overflow is counted.
- Maximum 200 config path samples and 100 nested-JAR path samples per artifact.
- Symbolic-link files and directories are not followed; directory traversal does not leave the selected mods root.
- Report output is rejected if placed inside the scanned mods directory.

## Local verification

The implementation was compiled with javac --release 21 -Xlint:all. The dependency-free self-test harness passed 4/4 cases:

- nested JSON parse/write round trip;
- Fabric metadata, config/resource paths, and synthetic class/type/member references;
- NeoForge primary mod ID extraction without confusing dependency mod IDs;
- rejection of a non-directory input.

These tests use generated fixture JARs. They do not establish compatibility with real mod archives or measured ecosystem coverage.

## Important limitations

- No nested-JAR recursion yet. Embedded JAR paths are reported so coverage gaps are visible.
- No general TOML parser.
- No instruction-level control-flow/call-site reachability analysis, Codec graph recovery, or runtime Registry enumeration.
- Obfuscated and relocated dependencies can hide signatures.
- API type references can be present without the corresponding protocol being actively used. Findings remain heuristic.
- The first scanner does not claim that a discovered object can safely be edited or written back.

## Next acceptance stages

1. Run the GitHub Actions workflow and fix any build or test failures.
2. Scan a user-supplied copy of a real mods directory, keeping the original directory read-only.
3. Build a version-pinned 30–50 mod corpus stratified by mod category.
4. Manually audit a sample of positives and negatives; label false positives and false negatives.
5. Add nested-JAR recursion, stronger package/version-aware signatures, and instruction-level call-site analysis.
6. Only after ground-truth labels exist, publish precision, recall, and per-domain coverage.

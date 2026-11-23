# UMPD Static Scanner 0.1.0 — implementation record

- Date: 2026-11-23
- Branch: research/umpd-static-scanner
- Target: Minecraft Java mod JARs; Fabric-first metadata support, with Forge/NeoForge metadata recognition
- Status: source implementation and independent local JDK 21 verification complete (11 acceptance scenarios); GitHub Actions runner allocation and real-mod corpus validation pending

## Scope

The first UMPD milestone is a static inventory scanner. It is intentionally separate from the CodecUI schema experiment and is not wired into the production Mod Studio editor.

It scans JAR archives without extracting them, defining classes, invoking mod callbacks, running static initializers, or modifying input files.

## Version and mapping boundary

The primary target is Minecraft 26.2. Fabric's current documentation states that mappings are relevant for obfuscated games, including pre-26.1 releases; Minecraft 26.1 and newer are unobfuscated. Therefore the 26.2 cohort can match Mojang class names directly. For older Fabric releases, production mod JARs commonly use Intermediary names and require mapping-aware normalization before named API signatures can be compared. UMPD now accepts a Tiny v2 class mapping and normalizes class names plus class types inside descriptors (default intermediary → named). It does not remap field or method names; historical results must record the exact mapping file, game version, and namespace pair.

References: [Fabric mappings guide](https://docs.fabricmc.net/develop/porting/mappings/index), [Tiny v2 format specification](https://wiki.fabricmc.net/documentation%3Atiny2), [Fabric Loom remapJar](https://docs.fabricmc.net/develop/loom/).

## Detection layers

1. **Loader metadata**: Fabric fabric.mod.json; Forge/NeoForge META-INF TOML metadata. Fabric metadata is parsed with a small JSON parser. TOML parsing is deliberately limited to primary [[mods]] sections; it is not a general TOML parser.
2. **Archive and resource inventory**: outer archive entry counts, file extension counts, asset/data namespaces, common resource path categories, config path samples, and nested-JAR entry names. Embedded JARs are recursively scanned for class references up to two levels.
3. **Class-file references**: inspect CONSTANT_Class entries, field/method descriptors, CONSTANT_Fieldref/Methodref/InterfaceMethodref owners and names, method-type descriptors, and dynamic-constant descriptors for DFU Codec, StreamCodec/PacketCodec, NBT, JSON serializers, config frameworks, item components, data attachments, SavedData, and registries. Method Code instructions are not decoded in this milestone.
4. **Mapping adapter**: an optional Tiny v2 reader maps class names from a selected source namespace to a target namespace. It records mapping-file SHA-256 and mapping count in the report. Field/method names are not remapped yet.
5. **Evidence provenance**: each bytecode finding records the class path, matched signatures, and the evidence level CLASS_TYPE_OR_MEMBER_REFERENCE. It is not a semantic call-graph claim.

## Version-pinned signature audit

The scanner now uses fully qualified package/class boundaries for Minecraft and loader APIs. It no longer treats generic names such as `ValueInput`, `PacketByteBuf`, `SavedDataType`, `DeferredRegister`, or `RegistryBuilder` as matches outside their owning packages. Synthetic negative fixtures exercise these lookalike names.

| Family | Exact signature examples | Version/source basis |
|---|---|---|
| Fabric networking | `net/fabricmc/fabric/api/networking/v1/PayloadTypeRegistry` | Fabric API 0.155.2+26.2 API docs |
| Minecraft packet codecs | `net/minecraft/network/codec/PacketCodec`, `net/minecraft/network/codec/StreamCodec`, `net/minecraft/network/PacketByteBuf`, `net/minecraft/network/RegistryByteBuf` | Yarn 1.20.6–25w42a API docs; namespace normalization is required for intermediary artifacts |
| Persistence | `net/minecraft/world/level/saveddata/SavedData`, `net/minecraft/world/level/saveddata/SavedDataType`, `net/minecraft/world/level/storage/ValueInput`, `net/minecraft/world/level/storage/ValueOutput` | Minecraft 1.21.5–1.21.6 mappings and migration docs |
| NeoForge config/registration | `net/neoforged/neoforge/common/ModConfigSpec`, `net/neoforged/neoforge/registries/DeferredRegister` | NeoForge 26.2.x/26.3.x source and docs |
| Fabric registries | `net/fabricmc/fabric/api/event/registry/FabricRegistryBuilder`, `net/minecraft/registry/RegistryBuilder` | Fabric API 26.2 docs and Yarn 1.21.4 docs |

References: [Fabric PayloadTypeRegistry 26.2](https://maven.fabricmc.net/docs/fabric-api-0.155.2%2B26.2/net/fabricmc/fabric/api/networking/v1/PayloadTypeRegistry.html), [Yarn PacketCodec](https://maven.fabricmc.net/docs/yarn-25w42a%2Bbuild.2/net/minecraft/network/codec/PacketCodec.html), [Yarn PacketByteBuf](https://maven.fabricmc.net/docs/yarn-1.20.6-rc1%2Bbuild.1/net/minecraft/network/PacketByteBuf.html), [NeoForge ModConfigSpec](https://github.com/neoforged/NeoForge/blob/26.2.x/src/main/java/net/neoforged/neoforge/common/ModConfigSpec.java), [NeoForge DeferredRegister](https://github.com/neoforged/NeoForge/blob/26.3.x/src/main/java/net/neoforged/neoforge/registries/DeferredRegister.java), [SavedDataType 1.21.5](https://mappings.dev/1.21.5/net/minecraft/world/level/saveddata/index.html), [ValueInput 1.21.6](https://mappings.dev/1.21.6/net/minecraft/world/level/storage/TagValueInput.html), [FabricRegistryBuilder 26.2](https://maven.fabricmc.net/docs/fabric-api-0.149.1%2B26.2/net/fabricmc/fabric/api/event/registry/FabricRegistryBuilder.html).

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
- Report output is rejected if it resolves inside the scanned mods directory; parent-symlink aliases and symbolic-link output targets are rejected.

## Local verification

The earlier scanner baseline compiled with javac --release 21 -Xlint:all and passed 4/4 tests. The current branch contains 11 acceptance scenarios. An independent local JDK 21 verification harness mirroring the current scanner and test behavior compiled with `javac --release 21 -Xlint:all` and passed 11/11, including both symlink assertions on the Linux environment. This is not a GitHub Actions run or a Gradle execution; CI still fails before runner allocation (runner_id=0, zero steps), so the repository workflow remains unverified:

- nested JSON parse/write round trip and maximum-depth rejection;
- versioned empty-report contract and JSON serialization round trip;
- report-output path containment, including symlink aliases into the selected mods root;
- Fabric metadata, config/resource paths, and synthetic class/type/member references;
- exact-package negative fixtures for unrelated classes named ValueInput, PacketByteBuf, SavedDataType, DeferredRegister, PacketCodec, and other lookalikes;
- Tiny v2 mapping provenance, escaped-name decoding, duplicate-section rejection, exact namespace-column validation, and no inferred inner-class remapping;
- NeoForge primary mod ID extraction without confusing dependency mod IDs;
- rejection of a non-directory input;
- no traversal through symlinked directories (skipped only if OS permissions prohibit creating the test symlink);
- one- and two-level embedded JAR class-reference discovery with container provenance.

These tests use generated fixture JARs. They do not establish compatibility with real mod archives or measured ecosystem coverage.

## Important limitations

- Embedded JARs are scanned for class/type/member references up to two nested levels. Nested loader metadata and full resource inventory are not yet merged into the parent artifact.
- Tiny v2 class mappings do not yet remap field or method names; class-level protocol hits are available, but some mapped member-level evidence may be missed.
- No general TOML parser.
- Constant-pool indices are structurally validated, and dynamic/method-type descriptors are inspected. No control-flow reachability or call-graph analysis, Codec graph recovery, or runtime Registry enumeration. A detected invoke instruction may belong to a method that is never reached at runtime.
- Obfuscated and relocated dependencies can hide signatures.
- Constant-pool references can remain even when the corresponding method is never invoked or is unreachable. Findings remain heuristic.
- The first scanner does not claim that a discovered object can safely be edited or written back.

## Report contract

The scanner emits `reportVersion: 1`; the JSON Schema contract is stored at `experiments/umpd-scanner/schemas/umpd-report-v1.schema.json`. The schema distinguishes successfully scanned artifacts from per-JAR failures and documents mapping provenance, nested-JAR counters, evidence records, and bounded warning overflow. The self-test suite includes an empty-directory report contract and JSON round-trip assertion.

## Current branch additions

- Fixed directory traversal to avoid following symbolic-link directories; added a regression test.
- Bounded metadata JSON nesting to 128 levels to prevent stack-exhaustion inputs.
- Canonicalized report-output parent paths and rejected symbolic-link report targets so output cannot be redirected into the scanned mods root.
- Added bounded in-memory nested-JAR scanning (maximum 100 embedded archives, depth 2, 64 MiB per embedded archive/entry, 256 MiB total embedded archive bytes, 512 MiB total nested uncompressed bytes).
- Added a recursive nested-JAR fixture test that checks evidence paths preserve both container levels.
- Added a Tiny v2 class-name adapter with namespace selection, mapping SHA-256 provenance, streaming byte limits, strict namespace/column validation, escaped-name decoding, duplicate rejection, and a synthetic intermediary-to-named integration fixture.
- Replaced generic simple-name protocol matches with fully qualified API package signatures; added negative fixtures for lookalike classes to reduce false positives.
- Current revision self-test count: 11 cases. The independent local harness passed all 11 scenarios; GitHub Actions and Gradle validation remain blocked before the runner starts.

## Next acceptance stages

1. Run the GitHub Actions workflow and fix any build or test failures.
2. Scan a user-supplied copy of a real mods directory, keeping the original directory read-only.
3. Build a version-pinned 30–50 mod corpus stratified by mod category.
4. Manually audit a sample of positives and negatives; label false positives and false negatives.
5. Expand version-pinned signature coverage and, as a separate milestone, add instruction-level call-site analysis.
6. Only after ground-truth labels exist, publish precision, recall, and per-domain coverage.

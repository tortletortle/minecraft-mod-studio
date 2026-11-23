# UMPD Scanner 0.1.0 — static Minecraft mod protocol discovery

UMPD scans Minecraft Java mod JARs without loading classes, invoking mod code, or extracting archive entries. It creates a JSON report containing loader metadata, mod IDs, archive/resource counts, file-format signals, SHA-256 fingerprints, and heuristic protocol signatures found in Java class-file constant pools.

## Run

Requires JDK 21+ and Gradle 8.7+ (or a compatible Gradle wrapper).

Windows PowerShell (default .minecraft instance):

~~~powershell
.\scan-mods.ps1
~~~

Custom launcher instance:

~~~powershell
.\scan-mods.ps1 -ModsPath 'D:\Games\PrismLauncher\instances\MyPack\.minecraft\mods'
~~~

Linux/macOS:

~~~bash
mods="$HOME/.minecraft/mods"
gradle --no-daemon verifyScanner run --args="scan \"$mods\" --out \"./build/umpd-report.json\""
~~~

The scanner accepts a directory and recursively considers .jar files. It does not modify the input directory. The report output must be outside the scanned mods directory.

## What it detects

- Loader metadata: fabric.mod.json, META-INF/neoforge.mods.toml, META-INF/mods.toml.
- Resource/file signals: top-level archive entry counts and JSON, JSON5, TOML, properties, config text, NBT, PNG, and OGG counts.
- Resource namespaces and common path categories such as assets/lang, assets/models, data/recipes, data/loot_tables, and data/worldgen.
- Class constant-pool signatures: DFU Codec, StreamCodec/network payloads, NBT persistence, common config frameworks, item data components, data attachments, SavedData, and registries.
- Nested JAR entry names are recorded as known unscanned dependencies.

## Evidence semantics

A class constant-pool match is a **heuristic signature**, not proof that a protocol is actively used on a particular code path. A path/extension count is a file-presence observation, not proof that a JSON file is accepted by a specific Codec. The report deliberately does not claim read/write capability or ecosystem coverage percentages.

## Safety limits

- No class loading, reflection, static initializer execution, or mod callback invocation.
- No archive extraction or writes to scanned JARs.
- Limits: 1,000 JARs per scan, 100,000 entries per JAR, 8 MiB per class file, 2 MiB per metadata file, and 1,000 evidence records per JAR.
- Symlinked JAR files are not followed.
- Malformed class files and oversized metadata are reported as warnings or scan failures; the scanner does not attempt recovery by executing code.

## Known limitations in 0.1.0

- TOML metadata extraction is deliberately minimal and does not implement the full TOML grammar.
- Class analysis reads constant-pool UTF-8 entries only; it does not perform control-flow analysis, method-level call-site analysis, or infer schemas.
- Shaded/relocated dependencies and obfuscated names can hide signatures.
- Nested JARs are detected but not recursively scanned yet.
- File extension counts do not establish whether a JSON file is a config, datapack entry, or an internal resource unless its archive path is considered.
- NeoForge/Forge and older Fabric naming variants require continued signature-corpus expansion.

## Next milestone

Run against a curated, version-pinned 30–50 mod corpus. Compare scanner findings with manual source audits, add false-positive/false-negative labels, and only then report protocol recall/precision.

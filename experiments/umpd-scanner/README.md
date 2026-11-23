# UMPD Scanner 0.1.0 — static Minecraft mod protocol discovery

UMPD scans Minecraft Java mod JARs without loading classes, invoking mod code, or extracting archive entries. It creates a JSON report containing loader metadata, mod IDs, archive/resource counts, file-format signals, SHA-256 fingerprints, and static protocol evidence found in Java class/type/member references.

## Run

Requires JDK 21+ (a newer JDK is also acceptable). The convenience scripts compile the scanner and its self-tests directly with javac, so Gradle is not required for a local scan.

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
chmod +x ./scan-mods.sh
./scan-mods.sh "$HOME/.minecraft/mods"
~~~

The scanner accepts a directory and recursively considers .jar files. It does not modify the input directory. The report output must be outside the scanned mods directory.

For IDE/Gradle builds, run the Gradle check and build tasks from this directory.

## What it detects

- Loader metadata: fabric.mod.json, META-INF/neoforge.mods.toml, META-INF/mods.toml.
- Resource/file signals: top-level archive entry counts and JSON, JSON5, TOML, properties, config text, NBT, PNG, and OGG counts.
- Resource namespaces and common path categories such as assets/lang, assets/models, data/recipes, data/loot_tables, and data/worldgen.
- Class/type/member references: DFU Codec, StreamCodec/network payloads, NBT persistence, JSON serializers, common config frameworks, item data components, data attachments, SavedData, and registries.
- Nested JAR entry names are recorded as known unscanned dependencies.

## Evidence semantics

A class/type/member reference is stronger than a raw string match, but it is still static evidence: it does not prove that the referenced method is reached on a particular runtime code path. A path/extension count is a file-presence observation, not proof that a JSON file is accepted by a specific Codec. The report deliberately does not claim read/write capability or ecosystem coverage percentages.

## Safety limits

- No class loading, reflection, static initializer execution, or mod callback invocation.
- No archive extraction or writes to scanned JARs.
- Limits: 1,000 JARs per scan, 512 MiB per JAR, 8 GiB total compressed input, 100,000 entries per JAR, 8 MiB per class file, 128 MiB total class bytes per JAR, 2 MiB per metadata file, and 1,000 evidence records per JAR.
- Symlinked JAR files are not followed.
- Malformed class files and oversized metadata are reported as warnings or scan failures; the scanner does not attempt recovery by executing code.

## Known limitations in 0.1.0

- TOML metadata extraction is deliberately minimal and does not implement the full TOML grammar.
- Class analysis reads type/member references and field/method descriptors; it does not perform bytecode instruction-level reachability or control-flow analysis and does not infer Codec schemas.
- Shaded/relocated dependencies can hide signatures. Historical pre-26.1 Fabric JARs may use Intermediary names; mapping-aware normalization is not implemented in 0.1.0.
- Nested JARs are detected but not recursively scanned yet.
- File extension counts do not establish whether a JSON file is a config, datapack entry, or an internal resource unless its archive path is considered.
- NeoForge/Forge and older Fabric naming variants require continued signature-corpus expansion.

## Next milestone

Run against a curated, version-pinned 30–50 mod corpus. Compare scanner findings with manual source audits, add false-positive/false-negative labels, and only then report protocol recall/precision.

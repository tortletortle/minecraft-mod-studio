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

Historical pre-26.1 Fabric instance with an extracted Tiny v2 mapping file:

~~~powershell
.\scan-mods.ps1 -ModsPath 'D:\Games\PrismLauncher\instances\Legacy\.minecraft\mods' -MappingsPath 'D:\Mappings\mappings.tiny'
~~~

Linux/macOS:

~~~bash
chmod +x ./scan-mods.sh
./scan-mods.sh "$HOME/.minecraft/mods"
~~~

With a Tiny v2 mapping file (third argument):

~~~bash
./scan-mods.sh "$HOME/.minecraft/mods" "./build/umpd-report.json" "./mappings.tiny"
~~~

The scanner accepts a directory and recursively considers .jar files. It does not modify the input directory. The report output must be outside the scanned mods directory.

For IDE/Gradle builds, run the Gradle check and build tasks from this directory.

## What it detects

- Loader metadata: fabric.mod.json, META-INF/neoforge.mods.toml, META-INF/mods.toml.
- Resource/file signals: top-level archive entry counts and JSON, JSON5, TOML, properties, config text, NBT, PNG, and OGG counts.
- Resource namespaces and common path categories such as assets/lang, assets/models, data/recipes, data/loot_tables, and data/worldgen.
- Exact package/class and member references: DFU Codec, StreamCodec/network payloads, NBT persistence, JSON serializers, common config frameworks, item data components, data attachments, SavedData, and registries. Lookalike class names and arbitrary UTF-8 strings do not count as type references.
- Embedded JARs are scanned recursively up to two nested levels for class/type/member references; the report preserves container paths and applies strict archive, entry, and uncompressed-byte budgets.

## Evidence semantics

Class matching uses exact package/class boundaries and validates constant-pool indices; arbitrary text and lookalike class names are not treated as API references. A class/type/member reference is stronger than a raw string match, but it is still static evidence: it does not prove that the referenced method is reached on a particular runtime code path. A path/extension count is a file-presence observation, not proof that a JSON file is accepted by a specific Codec. The report deliberately does not claim read/write capability or ecosystem coverage percentages.

## Safety limits

- No class loading, reflection, static initializer execution, or mod callback invocation.
- No archive extraction or writes to scanned JARs; embedded archives are read in memory only.
- Limits: 1,000 outer JARs per scan, 512 MiB per outer JAR, 8 GiB total outer input, 100,000 outer entries per JAR, 8 MiB per class file, 128 MiB total outer class bytes per JAR, 100 nested archives per outer JAR, two nested levels, 64 MiB per embedded archive/entry, 256 MiB total embedded archive bytes, 512 MiB total nested uncompressed bytes, 2 MiB per metadata file, 128 MiB per Tiny mapping file, 1 MiB per mapping line, and 1,000 evidence records and 1,000 warning records per outer JAR (excess warnings are counted in warningOverflow).
- Symbolic-link files and directories are not followed; directory traversal does not leave the selected mods root.
- Malformed class files and invalid constant-pool references are reported as warnings or scan failures; the scanner does not attempt recovery by executing code.

## Known limitations in 0.1.0

- TOML metadata extraction is deliberately minimal and does not implement the full TOML grammar.
- Tiny v2 support currently normalizes class names and class types inside descriptors only; it does not remap field or method names. Use a mapping file matching the exact Minecraft version and namespace pair. Mapping files are user-supplied and are not bundled or redistributed by UMPD; check the mapping provider's license before sharing them (Mojang mappings have additional restrictions).
- Class analysis reads type/member references and field/method descriptors; it does not perform bytecode instruction-level reachability or control-flow analysis and does not infer Codec schemas.
- Shaded/relocated dependencies can hide signatures. Historical pre-26.1 Fabric JARs may use Intermediary names; supply the matching version's Tiny v2 mapping file with `--mappings` (default namespaces: intermediary → named). Yarn mapping artifacts are commonly distributed as JARs containing `mappings/mappings.tiny`; extract that file first. Only Tiny v2 is accepted.
- Nested JAR scanning is limited to two embedded levels and class references; nested loader metadata and full resource inventory are not yet merged into the parent artifact.
- File extension counts do not establish whether a JSON file is a config, datapack entry, or an internal resource unless its archive path is considered.
- NeoForge/Forge and older Fabric naming variants require continued signature-corpus expansion.

## Next milestone

Run against a curated, version-pinned 30–50 mod corpus. Compare scanner findings with manual source audits, add false-positive/false-negative labels, and only then report protocol recall/precision.

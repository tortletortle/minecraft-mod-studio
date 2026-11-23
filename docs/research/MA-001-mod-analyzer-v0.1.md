# MA-001 · Mod Analyzer V0.1

Date: 2026-11-23  
Branch: research/horizon-adapter  
Status: static prototype; not integrated into the Studio UI; no Horizon SDK/game runtime used.

## Objective

Build the first independent component of Java Mod Migration Assistant: a read-only JAR inventory that produces evidence suitable for later ModIR construction. V0.1 is a triage analyzer, not a converter.

## Repository scope

Adds only:
- research/java-analyzer/analyze_jar.py
- research/java-analyzer/test_analyze_jar.py
- research/java-analyzer/test_javac_integration.py
- research/java-analyzer/README.md
- docs/research/MA-001-mod-analyzer-v0.1.md

No changes to main, the V2.5 HTML editor, build dependencies, CI, or game instances. The analyzer is a Python CLI and is not yet wired into the browser UI.

## Processing pipeline

1. Hash the original JAR.
2. Inspect ZIP central-directory metadata without extracting files.
3. Enforce path, duplicate, symlink, encryption, compression-method, entry-size, total-expansion, and compression-ratio limits.
4. Read only metadata, selected resource names, service descriptors, and .class entries.
5. Parse class-file constant pools and method Code attributes.
6. Record class references and invocation instructions.
7. Detect metadata-declared entrypoints, dependencies, and Mixin configuration.
8. Emit JSON evidence and diagnostics.

The analyzer never loads or executes a class. It never launches a build tool, annotation processor, service provider, or mod entrypoint.

## Evidence taxonomy

| Evidence | Meaning | What it does not prove |
|---|---|---|
| Loader descriptor | A descriptor file exists and was parsed | The JAR loads on that loader |
| Dependency declaration | Metadata declares a dependency/range | The dependency is present or compatible |
| Class reference | A class symbol appears in a constant pool | The code path executes |
| Invocation instruction | A method invocation instruction was found in bytecode | Dynamic dispatch target or runtime outcome |
| Mixin config | A config and listed mixin targets were found | Injection point applies to the target game |
| Resource path | A resource entry exists | It is registered, valid, or used |
| Risk flag | A feature requiring review was observed | The feature is impossible to migrate |

No compatibility score is generated. mappingStatus remains unknown; verification remains NOT_RUN.

## V0.1 parser scope

- Java class-file constant-pool tags used by ordinary Java class files.
- Structural class metadata and method Code attributes.
- Invocation opcodes: invokevirtual, invokespecial, invokestatic, invokeinterface.
- invokedynamic instruction counts without resolving bootstrap behavior.
- Fabric and Quilt JSON descriptors; Forge and NeoForge TOML descriptors.
- Manifest unfolding, service-provider declarations, Mixin JSON, resource paths, native libraries, and access-widener/transformer path signals.

The bytecode reader is deliberately bounded and is not a full verifier. It does not perform stack-map verification, control-flow analysis, call-graph construction, reflection resolution, annotation-processor execution, or semantic reconstruction. A malformed/unrecognized class produces a visible CLASS_PARSE_FAILED diagnostic; the analyzer does not silently count it as successfully understood.

## Security limits

- Compressed archive: 128 MiB.
- Single entry: 16 MiB.
- Total uncompressed entries: 256 MiB.
- Entry count: 20,000.
- Class entries: 12,000.
- JSON metadata: 2 MiB.
- Compression ratio: 250:1 for entries larger than 1 KiB.
- ZIP methods: Stored and Deflate only.
- No extraction; path checks remain defense in depth for any future materialization layer.

These are prototype guardrails, not a complete hostile-file sandbox. Run on untrusted JARs in a low-privilege environment with normal OS resource limits.

## Test evidence

The V0.1 suite covers:
- Fabric metadata, dependencies, entrypoints, and Mixin target inventory.
- Invocation instruction extraction and symbol-level reflection/Minecraft API signals.
- Multi-release class paths and Java class-file major-version display.
- Invalid class-file diagnostics.
- ZIP path traversal rejection.
- Case-insensitive duplicate path rejection.
- Excessive compression-ratio rejection.
- Resource categorization and no-extraction behavior.
- tableswitch, lookupswitch, and wide instruction-length decoding.
- Windows drive-style archive path rejection.
- A real javac-generated class containing switch, lambda/invokedynamic, and reflection constructs.

Local result for this commit candidate: **11 tests passed, 0 failed, 0 errors, 0 skipped** on an environment with javac installed. Ten tests use synthetic JARs; one integration test compiles a self-authored Java sample. No third-party mod or Horizon game was run.

## Known gaps / next experiments

1. Add nested-JAR inventory and hash nested artifacts without executing them.
2. Parse access widener/transformer contents as evidence, retaining source line numbers.
3. Add annotation and bootstrap-method inspection.
4. Cross-check class parsing and invocation extraction against ASM on a licensed, self-authored fixture corpus.
5. Add malformed class-file fuzzing and ZIP edge-case tests.
6. Build a target-independent feature graph, then a version-pinned Horizon capability matrix.
7. Only after Java mainline game acceptance and the H1 admission gate, consider an isolated Horizon content-package pilot.

## Decision

V0.1 is a useful first evidence collector, not yet a production component. Do not merge it into the main branch or use it to auto-generate Rust. Next gate is parser cross-validation against ASM and an expanded security/fuzz test suite.

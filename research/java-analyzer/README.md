# Mod Analyzer V0.1

A read-only, standard-library Python prototype for inspecting Minecraft Java mod JARs.

## Safety contract

- Never extracts archive entries to disk.
- Never loads, initializes, or executes classes.
- Never runs Gradle, Maven, annotation processors, service providers, or mod code.
- Rejects unsafe paths, duplicate paths, encrypted entries, symlinks, unsupported ZIP methods, oversized entries, excessive total expansion, and suspicious compression ratios.
- Reports input SHA-256 so the analyzed artifact can be identified.
- Does not claim runtime compatibility or calculate a migration percentage.

## Requirements

- Python 3.11+ (for TOML metadata parsing).
- No third-party Python packages.
- Optional JDK for the javac integration test; that test is skipped when javac is unavailable.

## Run

    python analyze_jar.py /path/to/example-mod.jar --output report.json

Or print JSON to stdout:

    python analyze_jar.py /path/to/example-mod.jar

Exit codes:
- 0: analysis completed; inspect diagnostics and riskFlags.
- 2: input rejected or unreadable.

## V0.1 evidence collected

- Fabric, Quilt, Forge, and NeoForge metadata descriptors when present.
- Declared mod IDs, versions, entrypoints, dependencies, and declared Mixin configs.
- Manifest attributes and multi-release class variants.
- Class names, superclasses, interfaces, fields/method counts, class-file major versions.
- Class constants and invocation instructions: invokevirtual, invokespecial, invokestatic, invokeinterface.
- Mixin configuration targets, service-provider declarations, access widener/transformer paths.
- Resource path inventory and coarse categories.
- Native library entries, native methods, reflection, classloading, method-handle and invokedynamic signals.

## Evidence interpretation

Signals are symbol-level observations. Risk flags identify features that deserve review. Neither means a feature is supported or unsupported by Horizon. Every signal uses mappingStatus=unknown and verification=NOT_RUN.

The parser is a bounded research implementation, not a JVM verifier. It does not resolve dynamic dispatch, reflection targets, invokedynamic bootstrap graphs, generated classes, runtime class loading, nested JAR contents, annotations in full detail, or semantic behavior. It does not prove that a referenced API is actually executed on a particular game path.

The analyzer deliberately leaves migrationAssessment.overallStatus as UNASSESSED. A future version should cross-check class parsing against ASM and add target-profile capability mappings only after an exact Horizon release/API profile is pinned.

## Tests

    python -m unittest -v

The suite includes synthetic JAR tests and an optional javac integration test that compiles a Java sample containing switch, lambda/invokedynamic, and reflection constructs. The javac test is skipped if JDK tools are unavailable. Tests do not download or execute third-party mods and are not evidence of real-world compatibility.

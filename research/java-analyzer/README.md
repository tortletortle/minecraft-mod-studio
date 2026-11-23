# Mod Analyzer V0.2

A read-only research toolchain for inspecting Minecraft Java mod JARs, comparing class-file parsing against OW2 ASM, and building a provenance-first ModIR evidence graph.

## Safety contract

- Never extracts archive entries to disk.
- Never defines, initializes, loads, or executes classes from the input JAR.
- Never executes entrypoints, service providers, Mixin plugins, annotation processors, Gradle tasks, or mod code.
- Reads class bytes and streams them to the standalone ASM oracle over stdin.
- Rejects unsafe archive paths, duplicate paths, encrypted entries, symlinks, unsupported ZIP methods, oversized entries, excessive total expansion, and suspicious compression ratios.
- Reports the input SHA-256 and requires exact hash identity before joining ASM and static reports.
- Does not produce a compatibility percentage or generate target code.

## Requirements

- Python 3.11+.
- JDK 21+ for javac integration and ASM oracle tests.
- The analyzer runtime uses only the Python standard library.
- The test suite uses the pinned development-only validator in requirements-dev.txt.
- curl and sha256sum are required by the reproducible test runner.
- OW2 ASM 9.11.1 is downloaded only for the research oracle; see asm-oracle/NOTICE.md.

## 1. Static JAR inventory

From this directory:

    python analyze_jar.py /path/to/example-mod.jar --output report.json

Or print JSON to stdout:

    python analyze_jar.py /path/to/example-mod.jar

Exit codes:
- 0: analysis completed; inspect diagnostics and riskFlags.
- 2: input rejected or unreadable.

V0.2 metadata handling includes:
- Fabric, Quilt, Forge, and NeoForge descriptors.
- Fabric string/object entrypoints, preserving adapter and value separately.
- Mixin config path, environment, package, configured Mixin class names, plugin and refmap.
- Fabric nested-JAR declarations, provides aliases, conflicts, and language adapters.
- Mixin config plugin risk flags.
- Class-file structures, invocation instructions, resources, native libraries and service providers.

The static report deliberately sets Mixin targetClasses to an empty list and targetDiscoveryStatus to NOT_ANALYZED. The config's mixins/client/server arrays name Mixin classes, not the Minecraft target classes. Actual target classes require reading the CLASS-retained @Mixin annotation with the ASM oracle.

## 2. Build and run the ASM oracle

Download the pinned core artifact and verify its published checksum:

    mkdir -p asm-oracle/lib build/asm-oracle
    cd asm-oracle/lib
    curl -fsSL https://repo.maven.apache.org/maven2/org/ow2/asm/asm/9.11.1/asm-9.11.1.jar -o asm-9.11.1.jar
    curl -fsSL https://maven.fabricmc.net/org/ow2/asm/asm/9.11.1/asm-9.11.1.jar.sha256 -o asm-9.11.1.jar.sha256
    expected="$(tr -d '[:space:]' < asm-9.11.1.jar.sha256)"
    [[ "$expected" =~ ^[0-9a-fA-F]{64}$ ]]
    printf '%s  %s\n' "$expected" "asm-9.11.1.jar" | sha256sum --check -
    cd ../..

Compile the standalone visitor:

    javac -encoding UTF-8 \
      -cp asm-oracle/lib/asm-9.11.1.jar \
      -d build/asm-oracle \
      asm-oracle/AsmOracle.java

Set the classpath and compare a JAR:

    export ASM_ORACLE_CLASSPATH="$PWD/build/asm-oracle:$PWD/asm-oracle/lib/asm-9.11.1.jar"
    python asm_oracle.py /path/to/example-mod.jar --classpath "$ASM_ORACLE_CLASSPATH" --output asm-report.json

For a multi-release JAR whose manifest contains `Multi-Release: true`, pin the Java view explicitly:

    python asm_oracle.py /path/to/example-mod.jar --classpath "$ASM_ORACLE_CLASSPATH" --target-java-version 21 --output asm-report.json

The helper reads framed class-file bytes from stdin. It does not create a class loader or load classes from the JAR. The report compares:
- class identity, class-file version, superclass and interfaces;
- declared method signatures and access flags;
- invocation instruction multisets for the four invocation opcodes;
- invokedynamic instruction counts;
- CLASS-retained @Mixin target declarations, including both class literals and string targets;
- archive-path and class-internal-name identity before associating a configured Mixin class;
- effective multi-release class selection when the manifest enables it and a Java runtime version is pinned.

For a multi-release JAR without `--target-java-version`, Mixin target discovery remains unresolved whenever a configured Mixin class has versioned variants. With a pinned runtime, the oracle selects the highest versioned entry not newer than that runtime, falling back to the base entry. Versioned entries are ignored when the manifest does not enable multi-release behavior. This Java version pin controls only the class-file view used for Mixin evidence; it does not establish game/API compatibility.

Invocation comparison is explicitly skipped when the per-class 500-sample limit is exceeded. A skipped comparison prevents the overall result from being marked passed.

## 3. Build ModIR

ModIR preserves observed facts and their provenance. It is not a source-code translation format.

    from pathlib import Path
    from analyze_jar import analyze_jar
    from asm_oracle import compare_jar
    from modir import build_modir

    jar = Path("/path/to/example-mod.jar")
    static_report = analyze_jar(jar)
    asm_report = compare_jar(jar, ASM_ORACLE_CLASSPATH)
    modir_report = build_modir(static_report, asm_report)

The resulting document follows modir.schema.json. It includes:
- artifact identity and source loader profile;
- mods, dependencies, entrypoints, classes, Mixin configs and resources;
- evidence IDs with source archive path and SHA-256;
- parser cross-check state;
- a null target profile and empty mappings until a specific target runtime is pinned.

The builder rejects an ASM report whose input SHA-256 differs from the static report. Migration status remains UNASSESSED unless a target profile and explicit capability mappings are later supplied.

## 4. Tests

Run the reproducible suite from this directory:

    bash run-tests.sh

The script creates a local .venv, installs the pinned development validator, downloads and verifies ASM 9.11.1, compiles the read-only oracle, and runs all tests. Build outputs and downloaded JARs are ignored by the local .gitignore. It requires Python 3.11+, JDK 21+, curl, and sha256sum.

The suite includes synthetic archive and metadata tests, malformed class-file boundary tests, ModIR schema/provenance tests, Mixin path-identity and multi-release selection tests, and javac/ASM differential integration tests. The ASM integration tests run when the script sets ASM_ORACLE_CLASSPATH.

A GitHub Actions workflow is provided at .github/workflows/mod-analyzer-research.yml. A workflow run with no allocated runner or no job steps is not test evidence; inspect the actual Actions run before treating CI as passed.

## Evidence interpretation and limitations

- A class reference is not proof that the referenced API executes.
- A method invocation instruction is not a resolved dynamic call graph.
- Reflection, generated classes, invokedynamic bootstrap behavior, and runtime-loaded classes may remain unresolved.
- Mixin target extraction does not execute plugins, apply refmaps, or prove an injection succeeds.
- Nested JAR declarations are inventoried as metadata in this version; recursive child-JAR analysis is not yet implemented.
- Access widener and access transformer paths are detected, but directive parsing is not yet implemented.
- ASM parsing is an independent class-file observation, not a JVM verifier and not proof of runtime behavior.
- No Horizon SDK, game runtime, or behavior-equivalence test is run.

## License

The Python and Java research helpers are project code. The ASM dependency is BSD 3-Clause; retain the notice in asm-oracle/NOTICE.md if distributing the oracle or its binary dependency.

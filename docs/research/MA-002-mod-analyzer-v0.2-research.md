# MA-002 · Mod Analyzer V0.2 research: ASM oracle, Mixin semantics, nested artifacts, and ModIR

Date: 2026-11-23  
Branch: research/horizon-adapter  
Status: research and design decision; no ASM runtime has been added to the main application; no third-party JAR has been executed.

## Executive conclusion

V0.1 is a useful bounded inventory prototype, but it is not yet a dependable semantic extractor. The next version should not expand its hand-written class-file parser into a full JVM implementation. Use OW2 ASM as an independent parser oracle, retain the Python parser only as a lightweight metadata/security front end and differential baseline, and make all migration claims traceable to evidence.

The first useful ModIR should be an evidence graph, not a Java-to-Rust source translator. It must distinguish:
- direct observations from bytecode/metadata;
- interpretations derived from those observations;
- mappings to a pinned target-runtime profile;
- behavior that has actually passed runtime tests.

Unknown must remain a first-class result. Do not convert an unresolved Mixin, reflection path, dynamic language adapter, or runtime plugin into guessed code.

## 1. External research findings

### 1.1 ASM is the right independent bytecode parser

The official ASM release page lists ASM 9.11.1, dated 17 October 2026, as the latest release at the time of this research. ASM 9.11 added the Java 28 class-version constant and a group of parser/resource-safety improvements, including validation of BootstrapMethods length and Code length, recursion limits for signatures, ConstantDynamic values and annotations, and resource controls for analysis utilities. ASM 9.11.1 fixes a 9.11 regression and improves frame-computation performance.

Decision: pin **org.ow2.asm 9.11.1** for the research oracle. Do not use a floating latest version. Recheck the pinned version when the target Java class-file level changes.

ASM's ClassReader parses a JVMS ClassFile and drives a ClassVisitor across class structure, fields, methods and bytecode instructions. That is exactly the independent observation surface needed for differential testing.

ASM is released under the **3-Clause BSD License**. If later shipped inside Mod Studio, retain its copyright and license notice and include the license text in distribution notices.

Sources:
- https://asm.ow2.io/versions.html
- https://asm.ow2.io/javadoc/org/objectweb/asm/ClassReader.html
- https://asm.ow2.io/license.html
- https://docs.oracle.com/javase/specs/jvms/se25/html/jvms-4.html

### 1.2 Fabric metadata describes more than the current V0.1 extractor records

The current Fabric metadata guide documents:
- entrypoint declarations as either strings or objects containing both an adapter and a value;
- entrypoint references that may name a class, method or static field;
- nested JAR declarations under \`jars\`, each with a relative \`file\` path;
- Mixin config declarations as a string path or an object with \`config\` and \`environment\`;
- access-widener/class-tweaker paths;
- \`provides\` aliases and the \`conflicts\` dependency group.

Fabric Loader also documents nested mods as mods contained inside the parent JAR; nested mods may themselves contain nested children.

Consequences for V0.1:
1. Its generic \`flatten_strings()\` recursively collects every string in an entrypoint object. For \`{"adapter":"custom","value":"pkg.Entry"}\`, it can incorrectly report both strings as entrypoint values. This is a concrete schema-handling defect.
2. It does not record \`jars\`, \`provides\`, \`languageAdapters\`, or \`conflicts\`.
3. It records an access-widener path but does not validate the referenced file or parse its directives.
4. It loses the environment attached to an individual Mixin config.

Sources:
- https://docs.fabricmc.net/develop/loader/fabric-mod-json
- https://docs.fabricmc.net/develop/loader/
- https://github.com/FabricMC/fabric-loader/blob/master/src/main/java/net/fabricmc/loader/api/FabricLoader.java

### 1.3 Mixin config entries are not the same as Minecraft target classes

A Mixin config's \`mixins\`, \`client\`, and \`server\` arrays enumerate **Mixin class names**. The actual target class is declared by the Mixin class's \`@Mixin\` annotation, using class literals in \`value\` and/or string names in \`targets\`.

Therefore, V0.1's output field called \`targets\` is semantically misleading: it currently contains configured Mixin class names, not the target Minecraft classes. Rename this field to \`mixinClasses\`. Add actual \`targetClasses\` only after parsing the class annotations.

Mixin's \`@Mixin\` annotation has CLASS retention, so a reader that only scans runtime-visible annotations will miss it. The extractor must read both visible and invisible annotations.

A Mixin config may specify a companion \`plugin\`. The official \`IMixinConfigPlugin\` contract allows the plugin to:
- decide whether a mixin should apply to a target;
- add additional mixin class names;
- observe other targets and suppress its own targets;
- perform transformations before and after a mixin is applied.

That means a config with a plugin can have runtime-dependent behavior which a static inventory cannot fully enumerate. The analyzer must flag it as dynamic/unresolved and must never instantiate or execute the plugin.

A refmap is also important: injector declarations can contain soft string references which are remapped through the refmap. A config's mixin class list alone is not enough to reconstruct the final target method mapping.

Sources:
- https://github.com/SpongePowered/Mixin/blob/master/src/main/java/org/spongepowered/asm/mixin/Mixin.java
- https://github.com/SpongePowered/Mixin/blob/master/src/main/java/org/spongepowered/asm/mixin/transformer/MixinInfo.java
- https://github.com/SpongePowered/Mixin/blob/master/src/main/java/org/spongepowered/asm/mixin/extensibility/IMixinConfigPlugin.java
- https://github.com/SpongePowered/Mixin/wiki/Introduction-to-Mixins---Obfuscation-and-Mixins

### 1.4 Access wideners are structured semantic operations

Fabric's current class-tweaker documentation describes three principal directives:
- \`accessible\`: make classes/methods/fields accessible;
- \`extendable\`: remove final restrictions from classes/methods and adjust visibility;
- \`mutable\`: remove final restrictions from fields.

Entries can be prefixed with \`transitive-\`. Targets use internal class names; field and method entries also require names and bytecode descriptors. Access widening applies to vanilla Minecraft classes, unlike accessor mixins which can target other mods.

Decision: parse access-widener/class-tweaker files into typed operations with source line numbers, namespace, target kind, owner, member name, descriptor, and transitivity. Do not reduce them to a generic boolean "uses access transformer" flag.

Source:
- https://docs.fabricmc.net/develop/class-tweakers/access-widening

## 2. V0.1 implementation audit

The following are code-inspection findings, not claims from an executed new test run.

| Priority | Finding | Why it matters | V0.2 treatment |
|---|---|---|---|
| P0 | Mixin config \`targets\` currently means Mixin class names | Misstates the target graph and can mislead migration planning | Rename to \`mixinClasses\`; add annotation-derived \`targetClasses\` |
| P1 | Entrypoint parser recursively flattens adapter and value strings | Can invent an entrypoint from an adapter identifier | Parse string/object variants explicitly; preserve adapter and raw value separately |
| P1 | Declared nested JARs are not inventoried | Dependency code and mod metadata may be omitted from the analysis | Hash and inventory declared nested JARs with shared resource budgets |
| P1 | Mixin plugin presence is not a dedicated risk flag | Plugin can filter/add mixins and mutate target classes at runtime | Add \`MIXIN_CONFIG_PLUGIN_DYNAMIC\`; never execute plugin |
| P1 | \`provides\`, \`conflicts\`, and \`languageAdapters\` are omitted | Dependency identity and language-specific entrypoint interpretation can be incomplete | Parse with source provenance |
| P1 | Access widener path is not checked or parsed | Important class/member access changes are invisible | Parse and validate referenced file |
| P1 | Annotation and BootstrapMethods attributes are skipped | Misses Mixin targets, injectors, type metadata and invokedynamic bootstrap semantics | ASM visitor oracle and structured annotation extraction |
| P2 | \`read_json_member\` does not catch \`RecursionError\` | Pathological deeply nested JSON may abort the analysis instead of producing a diagnostic | Add bounded/depth-safe metadata parsing and failure diagnostics |
| P2 | V0.1 is a hand-written partial class-file reader | It is not a JVM verifier and may diverge on valid or malformed class files | Differential validation; retain only bounded fast-path responsibilities |

## 3. ASM differential experiment design

### 3.1 Oracle boundary

Build a separate helper under \`research/java-analyzer/asm-oracle/\`, pinned to ASM 9.11.1. It should accept class-file bytes and emit normalized JSON. It must not:
- call \`Class.forName\` for classes found in the input;
- construct a URLClassLoader over the input JAR;
- initialize mod classes;
- invoke ServiceLoader providers;
- execute annotation processors, Mixin plugins, entrypoints or static initializers.

Use \`ClassReader\` + \`ClassVisitor\` + \`MethodVisitor\` for the primary observation pass. Capture:
- class version, access flags, internal name, superclass and interfaces;
- fields and method signatures/access flags;
- method invocation tuples (caller method, opcode, owner, name, descriptor, interface flag);
- invokedynamic name/descriptor, bootstrap handle and argument inventory;
- class, field, method, parameter and type annotations (visible and invisible);
- generic signatures, declared exceptions, record components and permitted subclasses;
- source attribute names and unknown-attribute presence.

Do not use an ASM verifier result as the sole ground truth. A parser visitor, JVM verifier, and semantic/runtime test answer different questions.

### 3.2 Comparison rules

Compare only facts with the same definition on both sides. For V0.1, compare:
1. class internal name, class-file major/minor version, superclass, interfaces;
2. declared method name/descriptor/access tuple set;
3. invocation instruction multiset keyed by caller + opcode + owner + name + descriptor;
4. invokedynamic instruction count.

Do **not** compare V0.1's constant-pool class-reference count directly to a visitor's visited type references: those are different observation scopes. Define a separate constant-pool oracle if exact constant-pool parity is required.

Required metrics:
- class parse agreement = classes parsed by both / total class entries;
- class identity agreement;
- method signature precision/recall;
- invocation multiset precision/recall;
- invokedynamic count agreement;
- annotation discovery precision/recall;
- explicit mismatch and parser-failure counts.

Every mismatch must preserve the class entry path, SHA-256, method identity and the smallest relevant bytecode/attribute evidence. Never silently discard mismatches.

### 3.3 Fixture corpus

Start with self-authored, reproducible fixtures:
- basic classes, interfaces, enums, records, sealed classes;
- lambdas, method references, string concatenation, ConstantDynamic;
- tableswitch, lookupswitch, switch expressions, try/catch and finally;
- generic signatures, inner/anonymous classes, parameter/type annotations;
- module-info and multi-release JAR entries;
- Mixin stub annotations: \`@Mixin\`, \`@Inject\`, \`@Redirect\`, \`@ModifyArg\`, \`@ModifyVariable\`, \`@Overwrite\`, \`@Shadow\`, \`@Accessor\`, \`@Invoker\`;
- Mixin config with refmap and a plugin declaration (the plugin itself is never executed);
- malformed/truncated class files and adversarial attribute lengths.

After self-authored fixtures pass, add a small, license-reviewed corpus of real mod JARs. Record source URL, version, SHA-256, license/redistribution permission, Java target and loader version. Do not commit binaries unless redistribution rights are clear.

### 3.4 Acceptance gate

V0.2 is not accepted merely because the oracle runs. On the self-authored valid corpus:
- 100% class identity agreement;
- 100% method signature agreement for the overlapping supported set;
- 100% invocation multiset agreement for the four invocation opcodes V0.1 claims to parse;
- 100% invokedynamic count agreement;
- no unreported parser failures.

If a malformed fixture causes one parser to reject and the other to accept, record it as a discrepancy and inspect against the JVMS; do not automatically label either implementation wrong.

Run the ASM helper in a constrained child process with a fixed heap and wall-clock timeout. This is defense in depth for malformed input; it is not a substitute for OS isolation.

## 4. ModIR draft: evidence graph, not source translation

### 4.1 Core entities

| Entity | Minimum fields |
|---|---|
| Artifact | SHA-256, byte size, archive path, parent artifact ID, format |
| Mod metadata | loader, mod ID, version, environment, aliases, metadata source |
| Dependency | source mod, target ID, constraint, relation kind, source path |
| Entrypoint | key, adapter ID, raw value, resolved class/member if statically resolvable |
| Class | internal name, version, access, superclass, interfaces, source artifact |
| Member | owner, name, descriptor, access, annotations, source class |
| Invocation | caller member, opcode, owner, name, descriptor, bytecode offset |
| Mixin config | path, environment, package, required, plugin, refmap |
| Mixin class | class name, declared target classes, annotation evidence |
| Injection | injector annotation, handler member, target selector, injection point, remap flag, constraints |
| Access change | directive, transitive flag, target kind, owner/member/descriptor, namespace, source line |
| Resource | path, type, namespace, metadata declaration, hash where useful |
| Target mapping | source symbol, target symbol, mapping status, evidence, target profile |
| Verification | test ID, input hashes, environment, observed result, timestamp |

### 4.2 Evidence and mapping states

Each extracted fact must include:
- \`evidenceKind\`: metadata, class_header, annotation, bytecode_instruction, resource_path, access_directive, runtime_observation;
- \`source\`: artifact SHA-256 + entry path + class/member + line or bytecode offset where available;
- \`origin\`: direct, derived, heuristic;
- \`verification\`: not_run, parser_cross_checked, runtime_tested;
- \`confidence\`: high, medium, low, unknown, with a documented rule rather than an invented numeric score.

Each source-to-target mapping must separately use:
- \`supported\`
- \`partial\`
- \`unsupported\`
- \`unknown\`
- \`manual_required\`

"Unsupported" requires evidence that the pinned target profile lacks the capability. Lack of a mapping is \`unknown\`, not \`unsupported\`.

### 4.3 Target profile must be pinned

No compatibility result is meaningful without a profile containing at least:
- Minecraft/game version and build;
- source loader and loader version;
- source mapping namespace and mapping artifact/version;
- Java source class-file level and target Java level;
- target runtime/SDK release and API schema;
- target mapping namespace/version;
- relevant dependency versions.

A report without a complete target profile may inventory a mod, but must not produce a migration verdict.

### 4.4 Migration pipeline

1. Read-only archive inventory and SHA-256 provenance.
2. Parse metadata, declared nested artifacts, resource declarations and dependencies.
3. Parse classes/annotations/instructions with ASM.
4. Build Mixin and access-change subgraphs.
5. Build a target-independent ModIR evidence graph.
6. Resolve source symbols against the exact source mappings.
7. Map features against a pinned target capability matrix.
8. Generate code only for deterministic, verified mappings.
9. Route dynamic/unknown behavior to manual review or a behavior test.
10. Run isolated target-runtime tests and record evidence separately from static analysis.

Do not translate arbitrary Java bytecode to Rust as the default strategy. Preserve intent through a feature graph and target-native implementations. Bytecode translation may be investigated as a separate research line for bounded pure-Java libraries, not for arbitrary Minecraft mods.

## 5. Security and licensing rules

- Never execute uploaded mod code, nested JAR code, service providers, Mixin plugins or entrypoints during analysis.
- Treat every archive and metadata field as hostile input.
- Apply shared depth, entry-count, expanded-byte, compression-ratio and wall-clock budgets across nested archives; do not reset limits for every child JAR.
- Keep nested JAR contents in memory only for the inventory phase; do not extract to arbitrary filesystem paths.
- ASM parses class-file bytes; it does not need to load the classes being inspected.
- Keep ASM 9.11.1 pinned and retain its 3-Clause BSD license notice.
- Do not redistribute real mod JARs without confirming their licenses and redistribution terms.

## 6. V0.2 implementation order

1. Correct the Mixin schema semantics: \`mixinClasses\` vs annotation-derived \`targetClasses\`.
2. Correct Fabric entrypoint object parsing; retain adapter and raw value separately.
3. Add \`jars\`, \`provides\`, \`conflicts\`, and \`languageAdapters\` metadata.
4. Add direct declared nested-JAR hashing and bounded archive validation.
5. Parse access-widener/class-tweaker directives and source line numbers.
6. Add Mixin plugin and missing-refmap diagnostics.
7. Add ASM 9.11.1 differential oracle and the self-authored fixture corpus.
8. Version the output schema and add ModIR only after the evidence fields stabilize.

## 7. Decision

Proceed with a separate V0.2 research implementation on \`research/horizon-adapter\`. Keep Java/Fabric mainline unchanged. Do not merge, add dependencies to the production editor, or generate Rust migration output until the differential gate and the ModIR provenance rules pass.

This report is a design/research artifact. It does not claim that ASM differential tests, nested-JAR implementation, ModIR, or Horizon runtime validation have already been completed.

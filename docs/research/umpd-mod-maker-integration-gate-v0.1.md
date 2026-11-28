# UMPD → Minecraft Mod Maker integration gate v0.1

## Decision

Keep UMPD on the isolated `research/umpd-static-scanner` branch. Do not wire it into the production editor or main Java generation path yet.

UMPD currently provides **static protocol evidence**. It does not prove runtime reachability, reconstruct complete schemas, or establish that a data structure can be safely edited and written back.

## Intended integration boundary

Treat UMPD as a read-only analysis service with a versioned JSON contract:

```text
Mod JARs + target game version + loader + optional Tiny v2 map
                    |
                    v
             UMPD scan worker
                    |
                    v
       report-v1 JSON + evidence paths
                    |
                    v
         Mod Maker protocol inspector
```

The production editor should consume the report; it should not load untrusted mod classes to obtain the same information.

### Proposed UI states

| State | Meaning | Permitted editor behavior |
|---|---|---|
| File observed | Resource or metadata path exists | Show inventory only |
| Type reference | A class or descriptor references a known API | Show protocol candidate |
| Member reference | A constant-pool member reference matches a signature | Show stronger candidate |
| Bytecode call site | A direct invoke instruction references the API member | Show caller method and bytecode offset |
| Schema recovered | A serializer/schema has been reconstructed and validated | Show read-only structured preview |
| Round-trip validated | Decode → edit → encode passes versioned tests | Enable controlled write for that schema only |

Never collapse these states into a single “editable” badge. A type reference or call site is not sufficient evidence for a writable editor.

## Data the inspector should retain

- Outer JAR SHA-256, file name, size, loader, mod ID, and declared game compatibility.
- Exact Minecraft version and loader cohort used for validation.
- Tiny mapping source/target namespaces and mapping-file SHA-256, if applied.
- Protocol names, evidence level, class path, nested-container path, caller method, and bytecode offset.
- Scanner warnings and warning overflow count.
- Scanner version and report schema version.

The report must be tied to the JAR fingerprint. If the JAR or mapping fingerprint changes, invalidate cached analysis.

## Security boundary

- Keep analysis in a separate worker/process from the editor UI.
- Never class-load, reflect over, instantiate, or execute mod classes.
- Never extract nested archives to a shared filesystem.
- Preserve per-archive, per-class, total-input, nested-depth, and warning/evidence limits.
- Treat metadata, archive paths, mapping files, and report strings as untrusted input.
- The worker writes only its report to a designated output directory; scanned JARs remain read-only.
- Do not grant UMPD filesystem write access to the modpack directory.

## Release gates

### Gate A — reproducible build
- Current branch compiles with JDK 21.
- All repository self-tests pass in a clean environment.
- GitHub Actions obtains a runner and completes the workflow.
- Windows PowerShell helper is executed on Windows, not only syntax-reviewed.

### Gate B — real corpus
- At least 30 version-pinned real JARs; target 42.
- Each artifact records loader, exact Minecraft version, Modrinth version ID, download URL, file size, and SHA-256.
- Keep primary Minecraft 26.2 Fabric results separate from historical-version cohorts.
- Never commit third-party JAR files to this repository.

### Gate C — independent ground truth
- Manually audit at least 10 artifacts, including positive and negative cases.
- Label true positives, false positives, false negatives, and unresolved findings.
- Report precision and recall per protocol with explicit denominators.
- Audit nested JAR findings separately from outer JAR findings.
- For historical artifacts, record exact Tiny v2 mapping provenance; class-only mapping must not be represented as complete member remapping.

### Gate D — schema extraction
- Identify actual serializer construction paths, not just class references.
- Reconstruct field names, field types, optionality, defaults, bounds, and version conditions.
- Validate recovered schemas against known valid and invalid payloads.
- Keep unsupported or ambiguous schemas read-only.

### Gate E — controlled write
- Decode a known-good sample.
- Apply a minimal edit.
- Encode it again.
- Decode the output and compare semantic values.
- Preserve unknown fields and version-specific data.
- Verify deterministic round trips and failure behavior.
- Only then enable writing for the exact schema/version pair that passed.

## Immediate next work

1. Obtain a clean full-branch compile and run all 11 self-tests.
2. Resolve GitHub Actions runner allocation; current runs have zero executed steps.
3. Execute the Windows helper and download the local 26.2 Fabric candidate corpus.
4. Manually audit the first 10 artifacts and publish per-protocol precision/recall.
5. Do not start schema writing until Gate C is satisfied.

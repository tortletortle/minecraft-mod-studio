# V2.7.1 — Mod Command Manifests

## Goal

V2.7.0 discovers the command syntax actually registered in the live integrated server. V2.7.1 adds a separate descriptive layer so installed Fabric mods can explain their commands in Chinese and English without changing the live Brigadier tree or granting execution rights.

## Resource contract

Each Fabric mod may include one UTF-8 JSON resource at:

    mms/commands.json

The file is read from the mod container with Fabric Loader's `ModContainer.findPath`; it is not loaded from an arbitrary user-supplied filesystem path. Fabric Loader documents that `findPath` resolves resources inside a mod JAR or directory and returns a NIO path that may use a virtual JAR filesystem. See the [Fabric Loader ModContainer API](https://maven.fabricmc.net/docs/fabric-loader-0.19.3/net/fabricmc/loader/api/ModContainer.html) and [Fabric Loader API overview](https://docs.fabricmc.net/develop/loader/).

The authoritative schema is [mms-command-manifest-v1.schema.json](schemas/mms-command-manifest-v1.schema.json). A sample file is [mms-commands.json](examples/mms-commands.json).

### Required identity and compatibility checks

- `schemaVersion` must be exactly `1`.
- `modId` must equal the ID reported by the loaded Fabric mod container.
- `modVersion` must exactly equal the installed mod version.
- `minecraftVersions` must contain the current server version or the explicit wildcard `*`.
- The manifest is rejected if it contains unknown fields.
- Every declared command root must exist in the current live Brigadier dispatcher.
- If multiple mods claim the same root, the manifest binding for that root is removed as ambiguous.

This is a root-name existence check only. Brigadier does not expose reliable ownership provenance for every command node, so the implementation explicitly reports `ownership_verified=false`. It does not claim that the declaring mod registered the command.

## Authoring and packaging

For a typical Fabric Loom project, place the file at:

    src/main/resources/mms/commands.json

The built mod JAR should contain `mms/commands.json` at its resource root (not under `data/<namespace>/`). Client-only projects should use the resource source set that is packaged into their mod JAR. Fabric Loader's `findPath` also resolves development resource roots, so the same contract works in a development run.

Before packaging, validate the file against the V1 schema and check these identity fields:

- `modId`: exactly the value in the mod's `fabric.mod.json`.
- `modVersion`: exactly the installed version after Gradle resource expansion.
- `minecraftVersions`: list only versions actually supported by the command implementation; use `*` only when the mod intentionally supports all relevant versions.
- `root`: exact Brigadier root name, including any alias the mod wants to document.

A manifest does not register a command. The mod must still register its Brigadier command through its normal Fabric command-registration path. The runtime only adds descriptive metadata after it finds the same root in the live dispatcher.

## Manifest fields

Each command entry includes:

| Field | Meaning |
|---|---|
| `root` | Exact live Brigadier root name |
| `descriptions` | Locale-to-description map, e.g. `zh_cn`, `en_us` |
| `keywords` | Search terms in supported languages |
| `examples` | Documentation examples; never executed |
| `argumentDescriptions` | Human-readable descriptions keyed by argument path/name |
| `effects` | Declared effect categories such as blocks, entities or inventory |
| `executionContext` | Declared server/player/entity context |
| `advisoryRisk` | Mod author's advisory risk label |
| `advisoryReversibility` | Mod author's advisory reversibility claim |

The current effect and risk enums are deliberately coarse. They are descriptive hints, not a verified effect analysis.

## Runtime bounds

- At most 512 Fabric mod containers are scanned.
- Each manifest is limited to 64 KiB. The loader reads at most 64 KiB plus one detection byte and rejects malformed UTF-8 rather than decoding a partial or oversized resource.
- At most 64 command entries are accepted from one mod.
- At most 512 command entries are retained globally.
- Catalog pages contain at most eight command roots to leave headroom under the 8 KiB UTF-8 bridge response limit.
- Full manifests limit descriptions to two locales of 64 characters each, keywords to 3 entries of 16 characters, examples to 1 entry of 64 characters, and argument descriptions to 3 entries with 64-character keys and 48-character values. Catalog pages carry only one 64-character preferred description and up to three 16-character keywords per command.
- Invalid, stale, unsupported or conflicting entries are skipped and counted. `manifest_issue_count` reports the total; `manifest_issues` returns at most three representative diagnostic codes, and `manifest_issues_truncated` explicitly indicates whether additional issues were omitted.
- The validated registry is cached for one integrated-server instance, one Brigadier dispatcher identity and one snapshot of the live root-name set. It is rebuilt when the world server changes, the dispatcher is replaced, or command roots are added/removed in place. This avoids rescanning every mod for each catalog page while preventing stale root bindings and cross-world metadata leakage.

## Search and inspection

The existing MCP tools remain the only command-intelligence interface:

- `mms_search_commands` now ranks live command roots using root names, curated hints and compact manifest descriptions/keywords.
- `mms_inspect_command` returns the matching manifest metadata alongside live Brigadier usage and child-node information.
- `mms_validate_command` remains a parse-only Brigadier check.

The catalog returns only a compact manifest summary (one preferred localized description up to 64 characters and up to three keywords of up to 16 characters each) so paginated responses stay below the 8 KiB local bridge line limit. Catalog pages are capped at eight command roots. Full descriptions, examples and argument explanations are returned only by single-command inspection. Inspection lists are capped at three entries with 64-character usage strings, leaving over 2 KiB of headroom in the 8 KiB UTF-8 bridge response budget for worst-case Unicode manifest content. The search reports whether a result came from a mod manifest. It does not turn a manifest description into a trusted instruction.

## Trust and safety model

All mod-supplied manifest content is **untrusted descriptive data**:

- It is never executed, evaluated, imported as code or interpreted as an agent instruction.
- It cannot register MCP tools or commands.
- It cannot grant permissions or authorize a world mutation.
- The risk and reversibility fields are advisory claims only.
- A manifest root match does not prove command ownership or semantic correctness.
- The independent execution policy must later derive risk from the actual operation and live world context, not trust the manifest's label.

The companion remains read-only for command intelligence. There is still no generic command-dispatch endpoint.

## Acceptance checklist

- [ ] Fabric 26.2 / Java 25 build produces companion version 0.6.0.
- [ ] A test mod's valid manifest is discovered from its JAR resource path.
- [ ] A manifest with mismatched mod ID, mod version or Minecraft version is rejected.
- [ ] Unknown fields, oversized files, oversized arrays and invalid enum values are rejected.
- [ ] A command root absent from the live dispatcher is not exposed as a searchable command.
- [ ] Duplicate claims for one command root are reported and excluded.
- [ ] Chinese/English descriptions and keywords improve command search.
- [ ] Search and inspection mark manifest data as untrusted and ownership as unverified.
- [ ] Oversized or malformed UTF-8 resources are rejected with bounded reads.
- [ ] Total diagnostic counts remain accurate when only four diagnostic samples are returned.
- [ ] In-place additions/removals of Brigadier root names invalidate the manifest cache.
- [ ] Invalid manifests cannot prevent the game or bridge from starting.
- [ ] No command execution or world mutation is introduced by manifest loading.
- [ ] Windows Minecraft 26.2 test world confirms manifest discovery from at least one installed test mod.

Do not mark V2.7.1 accepted until the Fabric build and runtime checks pass.

# Schema Engine experiment — Minecraft 26.2

This is an isolated research module. It is intentionally not wired into the production editor, the existing resource library, or the V2.6 Live Game Debugger branches.

## Question being tested

Can Mod Studio use CodecUI as a runtime schema-discovery dependency, project the discovered schema into a stable editor-neutral format, and retain a safe fallback when inference cannot understand a codec?

The first experiment is deliberately narrow:

1. Load the pinned CodecUI Fabric library in a disposable Minecraft 26.2 client.
2. Ask it to infer schemas for primitive, list, map, record, and either codecs.
3. Project those schemas into a versioned editor-neutral JSON document.
4. Decode and encode fixed JSON fixtures through the original codecs.
5. Write an acceptance report under the Minecraft instance config directory.

The projection layer does not serialize Codec objects, invoke dispatched-map resolvers, or call enum label callbacks. Unsupported and opaque nodes remain explicit raw-JSON fallbacks.

## Pinned toolchain

- Minecraft: 26.2
- Java: 25
- Fabric Loader: 0.19.3
- Fabric API: 0.153.0+26.2
- Fabric Loom: 1.17.12
- CodecUI: 26.2-1.4.11

CodecUI is consumed as an external Maven dependency and nested as a separate mod JAR. Its source is not copied into this repository. Upstream README says it is intended to be included by mods and declares its license as MIT in mod metadata; the audited source tree did not contain a standalone LICENSE file. Preserve upstream attribution and re-check the publisher's license terms before redistributing a production build.

## Build and run

From this directory, with Gradle 9.5.1 and JDK 25 available:

    gradle --no-daemon test build

Launch the client in a disposable Minecraft 26.2 instance:

    gradle runClient

After the client initializes, inspect:

    <instance>/config/mms-schema-engine/codecui-26.2-smoke.json

The report records the actual loaded CodecUI version, CodecUI inference mode, each inferred root kind, bounded schema projection, and codec decode/encode round-trip results.

## Acceptance criteria

The automated build must compile the mod and pass the projection unit tests.

The in-game smoke report passes only if:

- CodecUI is present and reports exactly version 26.2-1.4.11.
- primitive, list, map, record, and either fixtures resolve to the expected schema kinds;
- every fixture decodes and encodes successfully;
- the encoded JSON equals the fixture JSON;
- projection completes within its depth, node, and collection budgets.

The report separates a structural smoke pass from a full-fidelity pass. Full fidelity additionally requires CodecUI's `MIXIN` inference mode and successful recovery of RecordCodecBuilder field names, optionality, and defaults. `REFLECTION` is a reduced-fidelity mode: it may recover nested structure and numeric bounds but loses optional-field defaults.

A successful Gradle build is not evidence that the mod loaded in Minecraft. A successful smoke report is not evidence that arbitrary third-party mods are editable. Those remain separate acceptance stages.

See [the 26.2 mod protocol landscape and adapter strategy](../../docs/research/mod-protocol-landscape-26.2.md) for the wider ecosystem survey and proposed adapter architecture.

## Explicit non-goals

- No changes to the production HTML editor or its IndexedDB resource library.
- No arbitrary class loading, reflection over third-party mod objects, or arbitrary Java execution by the future AI agent.
- No direct writes into a user's existing world or installed mod JAR.
- No claims that all Codec shapes can be inferred. Opaque/unsupported nodes must remain visibly non-editable until a safe handler or explicit schema is available.
- No merge into main or PRs #14–#16 from this experiment.

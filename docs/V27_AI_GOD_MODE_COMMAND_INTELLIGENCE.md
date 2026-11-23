# V2.7.0 — AI God Mode: Command Intelligence (Read-only Prototype)

## Goal

Introduce an AI operator identity that can discover and understand the commands registered in the currently running Minecraft Java 26.2 integrated server. The first milestone is deliberately read-only: discover, search, inspect and syntax-validate commands, but do not execute them.

The design replaces a growing list of one-off MCP tools with a small command-intelligence surface. It does **not** add a generic command-execution endpoint in this version.

## Architecture

```text
Cursor / local AI agent
        |
        | 3 typed MCP tools
        v
MMS Command Intelligence
  - natural-language command search
  - command inspection
  - syntax-only validation
        |
        | authenticated loopback JSON-lines
        v
Fabric runtime companion
        |
        | integrated-server thread
        v
Minecraft Commands.getDispatcher()
        |
        v
Live Brigadier command tree
```

The implementation reads the live dispatcher from `MinecraftServer.getCommands().getDispatcher()`. This is the actual command tree for the current integrated server, including commands registered by Fabric server command callbacks and installed server-side mods. The tree is not reconstructed from a hard-coded Vanilla command list.

## Virtual operator identity

The prototype creates a non-player `CommandSourceStack` named `MMS_AI_OPERATOR` / `MMS AI Operator`:

- Its position and dimension are anchored to the local player's current location.
- It has no backing player/entity. Commands that require an entity executor are therefore not guaranteed to be executable by this identity.
- `PermissionSet.ALL_PERMISSIONS` is used only to see the widest command tree and parse command syntax in this read-only milestone.
- Its output sink is `CommandSource.NULL`.
- No command execution path is exposed. The source's broad permission view must not be mistaken for authorization to execute world changes.

A later execution milestone must add a separate policy layer. It must not turn this discovery identity into an unrestricted executor by accident.

## MCP surface

| MCP tool | Function | World mutation |
|---|---|---|
| `mms_search_commands(query, limit)` | Search the live command catalog using root names plus curated Chinese/English intent hints | None |
| `mms_inspect_command(name)` | Inspect a command root, usage paths, smart usage and immediate child nodes | None |
| `mms_validate_command(command)` | Parse one command with the live Brigadier dispatcher and report syntax validity | None |

The tools are intentionally few. The AI does not receive one MCP tool per Minecraft command.

### Catalog protocol

The local bridge exposes three read-only protocol operations:

- `command_catalog`: paginated root-command inventory; page size 1–10.
- `command_inspect`: bounded usage and child-node metadata for one root.
- `command_validate`: syntax parsing only, with a 512-character input limit.

The catalog reports the current live server command tree, total count, pagination state, source identity and the fact that execution is disabled.

### Search semantics

Search is a hybrid of:

1. Runtime command names and their presence in the live tree.
2. Curated Chinese/English keyword hints for common Vanilla commands (for example, “批量替换方块” can find `fill`; “生成村民” can find `summon`).

This is lexical/keyword retrieval, not embeddings, an LLM-generated description, or proof that a command's side effects are understood. Unknown mod commands can still be discovered and inspected by name, but their semantics need a trusted manifest or documentation adapter in a later milestone. The search index is rebuilt from the live dispatcher on each search rather than persisted offline; it reads up to 1,000 command roots per search and reports `catalog_truncated=true` if more are registered. This keeps datapack/mod reloads visible without serving a stale catalog, at the cost of several short local bridge requests for large command trees.

## Brigadier behavior and validation boundary

Brigadier exposes the live command tree and supports usage extraction, parsing and completion. This prototype uses:

- `getRoot()` and child nodes to enumerate registered command roots.
- `getAllUsage(node, source, true)` for executable usage paths.
- `getSmartUsage(node, source)` for concise child syntax.
- `parse(input, source)` and Minecraft's `Commands.validateParseResults(...)` for syntax validation.

A parse result is not command execution. The implementation never calls `dispatcher.execute(...)`, `Commands.performPrefixedCommand(...)`, or a command node's executor.

Important qualification: custom argument parsers belong to installed mod code. Parsing does not invoke the command executor, but the parser itself is not a sandbox and could contain arbitrary mod-defined logic. Treat syntax validation as a parser check, not a security proof.

## Next stage: command manifests and domain packs

Live Brigadier discovery answers "what is registered and what syntax exists?". It does not answer "what does this mod command mean, what side effects does it have, or when should an agent choose it?". V2.7.1 should add a descriptive manifest layer without replacing the live dispatcher as the source of truth.

### MMS Command Manifest

V2.7.1 implements one fixed resource per Fabric mod:

    mms/commands.json

The companion resolves this resource through Fabric Loader's `ModContainer.findPath`, verifies the declaring mod ID/version and current Minecraft version, and binds each declared root only when that exact root exists in the live Brigadier dispatcher. See [V2.7.1 Mod Command Manifests](V27_1_MOD_COMMAND_MANIFESTS.md) and the [manifest schema](schemas/mms-command-manifest-v1.schema.json).

Each manifest entry should contain:

- Schema version, namespace/mod ID, mod version and supported Minecraft versions.
- One or more exact Brigadier root names; the loader must verify each root exists in the live dispatcher.
- Human description, Chinese/English keywords, categories and examples.
- Argument explanations and execution-context requirements.
- Declared effect categories (blocks, entities, inventory, world rules, server lifecycle, etc.).
- Advisory risk and reversibility metadata, plus documentation references.

Manifests are descriptive data only. They cannot contain executable scripts, Java class names, method names, reflection instructions, MCP tool definitions or instructions that override agent/system policy. A manifest's risk label is not trusted authorization; the independent command policy must classify effects itself.

### MMS domain command packs

For capabilities missing from Vanilla or installed mods, MMS can register a small number of high-level, typed Brigadier command families through Fabric's \`CommandRegistrationCallback\`:

- \`/mms inspect ...\` — inspect blocks, entities, registries and runtime state.
- \`/mms world ...\` — bounded world/time/weather/terrain operations.
- \`/mms build ...\` — blueprint, structure and region operations.
- \`/mms entity ...\` — spawn, configure and animate supported generated entities.
- \`/mms debug ...\` — create test scenes, run bounded probes and collect evidence.

The goal is not hundreds of overlapping wrapper commands. Use a compact, typed command tree with composable subcommands and reusable operation primitives. The live dispatcher automatically makes these commands discoverable; their manifest adds semantics for search and planning.

Server commands registered through \`CommandRegistrationCallback\` and client-only commands registered through \`ClientCommandRegistrationCallback\` are separate command environments. The current prototype indexes only the integrated-server dispatcher. See the [Fabric command registration guide](https://docs.fabricmc.net/develop/commands/basics).

## Current scope and limitations

- Minecraft Java 26.2, Fabric client companion, single-player integrated server.
- Reads the server-side dispatcher actually registered in this world.
- Dedicated-server-only commands are not present in an integrated-server command tree.
- Client-only commands are not included.
- Root command discovery does not prove that a command can run without an entity/player context.
- The command tree provides syntax and argument node structure, not reliable natural-language descriptions, risk labels, reversibility, or semantic meaning.
- Datapack function contents and macro parameters are not indexed as first-class searchable commands yet.
- No generic command execution, command chaining, arbitrary Java, file access, or multiplayer control is added.

## Safety boundary

The bridge remains loopback-only and authenticated. The new operations are read-only. The AI operator's all-permissions view is scoped to discovery and parsing only. There is no MCP method that dispatches the supplied command to the Minecraft server.

Any later command execution milestone must introduce:
- Per-command risk classification and default-deny behavior for unknown commands.
- Separate preview/plan and execution operations.
- Explicit approval for destructive or persistent changes.
- Bounded command count, execution time, affected block/entity limits and rate limits.
- Captured command feedback and post-action world-state verification.
- Undo only when a reliable inverse or snapshot exists; never claim every command is reversible.

## Acceptance checklist

- [ ] Fabric 26.2 / Java 25 companion builds and packages as version 0.5.0.
- [ ] The live integrated-server catalog contains Vanilla commands such as `fill`, `summon` and `weather` when those commands are registered in the world.
- [ ] Pagination returns no duplicate or skipped root commands.
- [ ] Inspecting `fill` returns syntax paths and child metadata from the live dispatcher.
- [ ] Valid and invalid command strings are distinguished by Brigadier parsing.
- [ ] MCP tool discovery exposes only search, inspect and validate for command intelligence.
- [ ] Tests prove that these calls map only to `command_catalog`, `command_inspect` and `command_validate`; no execution command is sent.
- [ ] A disposable-world manual check confirms the prototype does not change blocks, entities, inventory, gamerules or world time.
- [ ] Cursor receives useful search results for Chinese and English queries.
- [ ] The runtime acceptance helper verifies the live command catalog, `fill` inspection, one valid parse and one invalid parse without executing either input.

Do not mark V2.7.0 as fully accepted until the Fabric build and real 26.2 runtime checks pass.

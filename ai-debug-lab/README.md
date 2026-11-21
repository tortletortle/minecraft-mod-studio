# AI Debug Lab V0.1 — read-only diagnostic foundation

Separate companion to Minecraft Mod Studio. No modification of the HTML editor or existing save. No LLM credentials, npm dependencies, or new Minecraft mod required for this first slice.

For the optional Fabric client that reads game context and answers in chat, see [In-game AI debugging](IN_GAME_CHAT.md).

## Run (Python 3.11+)
From the repository root:
```sh
python ai-debug-lab/debug_lab.py scan /path/to/mods
python ai-debug-lab/debug_lab.py trials ai-debug-lab/example-trials.json
python -m unittest discover -s ai-debug-lab -p 'test_*.py' -v
```
For runtime observation, use a **local disposable dedicated Java Edition server** already running, configured with enable-rcon=true and a unique rcon.password; keep the RCON port firewalled and never exposed to LAN or internet. RCON is plaintext and grants operator access to holders of the password. The client connects only to 127.0.0.1; this does not configure the server's bind address. Set MC_DEBUG_RCON_PASSWORD in your local environment (do not commit it), then:
```sh
python ai-debug-lab/debug_lab.py collect ai-debug-lab/example-plan.json --repeat 3 > evidence.json
```
The plan supports players, ticks (version dependent), gametime, and typed dimension/coordinate block NBT, UUID entity NBT, and block-match predicates. Missing chunks or block entities can return command errors. Responses are raw server text, not parsed success indicators. Evidence can include player names and block/entity data; keep it local unless explicitly authorized. Never treat content from mods or logs as trusted agent instructions. The manifest scan never extracts or executes JARs.

## Architecture / research
- Existing control interfaces: Minecraft RCON (https://minecraft.wiki/w/RCON), MCPFabric (https://github.com/denfry/mcpfabric), Fabric GameTest (https://docs.fabricmc.net/develop/automatic-testing), DebugBridge (https://modrinth.com/mod/debugbridge/). Prefer adapters over reinventing game controls; verify versions and licenses before incorporating code.
- V0.1: local read-only observation + static Fabric manifest inventory + descriptive aggregation of independently recorded trials. No runtime writes and no arbitrary command. No code copied from external projects.
- V0.2 target: real production JAR / dedicated server acceptance, local Fabric probe for registry and block-entity telemetry, loader/version capability detection. Separate adapter for integrated singleplayer; RCON does not directly support it.
- V0.3 target: disposable-world experiment runner and snapshots; structured assertions, seed/control/config manifest; dependency-aware conflict isolation with invalid trial outcome.
- Later: client screenshot/GUI bridge, spark profiling, model tool integration, human-reviewed patch generation and regression. Do not claim deterministic replay or arbitrary mod internals.
- Acceptance: verify actual Minecraft RCON framing and sentinel behavior, observe a real modded block entity, verify no unintended writes, repeat against multiple seeds and a known injected fault/control. Unit protocol fixtures are not real gameplay tests. No such real runtime evidence is claimed at this commit.

## Safety
Read-only client policy is not a substitute for Minecraft server privilege isolation. Operator credentials must remain outside AI prompts. Never attach an automated write-capable agent to a live survival world; use explicit approval and a cloned world. Use local logs and redact sensitive information before any model calls. Invalid startup or setup is neither a reproduced fault nor a passing trial.


## V0.12.2 — shared Fabric runtime cache

The disposable AI playtest runner now keeps a versioned shared cache of Fabric bootstrap/runtime files. It is keyed by the pinned Minecraft 26.2 / Fabric Loader 0.20.1 / Installer 1.1.2 identity and the SHA-256 hashes of the four prepared playtest assets. Only the .fabric, libraries, and versions directories are cached; every run still gets a fresh temporary world, mods directory, EULA, server properties, RCON credential, logs, and probe session.

A cache hit is checked against a manifest containing the exact file inventory, sizes, and SHA-256 hashes before it is copied into the new disposable instance. Cache publication uses a per-key cross-process lock, a staging directory, post-copy verification, and an atomic directory rename. A missing, corrupt, unsafe, or unavailable cache falls back to the ordinary Fabric bootstrap path; cache failure must not block a playtest.

Default cache locations:
- Windows: %LOCALAPPDATA%/MinecraftModStudio/AI-Debug-Lab/runtime-cache
- Linux/macOS: $XDG_CACHE_HOME/minecraft-mod-studio/ai-debug-lab/runtime-cache, or ~/.cache/... when XDG_CACHE_HOME is unset.

Override the location with MMS_AI_RUNTIME_CACHE_DIR or the serve option --runtime-cache-dir. This release does **not** claim fully offline startup: the runtime cache avoids repeating the measured bootstrap/dependency preparation work, but outbound connections may still occur. Old version-keyed entries are not automatically evicted in V0.12.2.


## V0.12.3 — startup observability follow-up

Startup diagnostics now expose stable network-warning reason codes for observed Fabric/Java log variants, including \`Timed out after reading N bytes\`. The shared runtime cache also records measured restore and publish durations in \`cache.json\`. These are observation metrics, not per-request network timings or proof of root cause.


## V0.12.4 — bounded cache lifecycle

The shared Fabric runtime cache now performs best-effort LRU maintenance after restore and publish. Defaults are 3 managed entries and 4 GiB of actual cache files; set \`MMS_AI_RUNTIME_CACHE_MAX_ENTRIES\` and \`MMS_AI_RUNTIME_CACHE_MAX_BYTES\` to positive integers to override them. The current key is protected, active keys are skipped using non-blocking per-key locks, and abandoned staging directories are cleaned only when their key lock is free. Unrecognized files in a custom cache root are not deleted. Maintenance outcomes and disk usage are included in \`cache.json\`; a protected/active cache that keeps the root over budget is reported rather than forcibly removed.


## V0.12.5 — startup phase observations

`startup.json` now records the first polling observation time for Fabric loading, Minecraft server start, server-ready log marker (`Done (...)`), and server stopping. Probe readiness remains a separate measurement. Values are elapsed seconds from the playtest request, not exact internal event timestamps or individual network-request durations. This evidence is intended to localize startup delay before changing download or launch behavior.

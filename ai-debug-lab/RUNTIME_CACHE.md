# AI Debug Lab V0.12.2 — shared Fabric runtime cache

## Scope

This cache optimizes the measured startup cost in the separate AI Debug Lab companion. It is not a cache of user projects or modpacks. It is currently pinned to Minecraft 26.2, Fabric Loader 0.20.1, and Fabric Installer 1.1.2.

The cache contains only these runtime directories from a completed temporary Fabric instance:

- .fabric
- libraries
- versions

It never stores or restores the temporary world, mods, server.properties, EULA, RCON password, logs, probe session, or user saves. Those are recreated for every playtest.

## Cache identity and integrity

The cache key is SHA-256 over a canonical identity containing the cache schema version, Minecraft/Loader/Installer versions, and all four prepared asset hashes (fabric-server.jar, server.jar, fabric-api.jar, probe.jar). Changing any of those values selects a different entry.

Each entry contains cache-manifest.json, listing every runtime file's relative path, byte size, and SHA-256. A cache hit is accepted only when:
- the manifest identity matches the current runtime identity;
- the exact file inventory matches;
- every file size and SHA-256 matches;
- runtime paths contain no symlinks or junctions.

A missing, incomplete, corrupt, or unsafe entry is rejected and removed where safe. The launcher then proceeds through its normal Fabric bootstrap path. Cache errors do not fail the playtest.

## Concurrency and publication

Each cache key has a cross-process lock. Writers copy the runtime into a staging directory under the cache root, write and fsync the manifest, verify the staged copy, then atomically rename the staging directory into place. Readers take the same lock while validating and copying into a new instance. Each playtest receives its own copied runtime tree; it does not mutate the shared cache.

The lock prevents concurrent readers from observing a partially published entry and prevents competing writers from replacing one another's cache. Two first-time launches may both miss before either publishes; the first valid publisher wins and the later publisher reuses the verified entry.

## Locations

- Windows default: %LOCALAPPDATA%/MinecraftModStudio/AI-Debug-Lab/runtime-cache
- Linux/macOS default: $XDG_CACHE_HOME/minecraft-mod-studio/ai-debug-lab/runtime-cache, falling back to ~/.cache/minecraft-mod-studio/ai-debug-lab/runtime-cache.
- Override: MMS_AI_RUNTIME_CACHE_DIR or playtest.py serve --runtime-cache-dir PATH.

V0.12.2 does not automatically evict old version-keyed entries. Users can remove the runtime-cache directory while no playtest is running; the next launch will bootstrap a new entry.

## Security and limits

SHA-256 validation detects accidental corruption and incomplete writes; it is not a defense against a local attacker who can modify both cached files and their manifest. The cache is not a security sandbox. Runtime JARs are still loaded by the local Java process. Cache files are local and are not sent to the model by this code.

A verified runtime cache is **not** an offline-startup guarantee. Fabric may still make network requests for metadata or other reasons. V0.12.2 does not block network access and does not claim offline support. The cache also does not change the current RCON boundary, write allowlist, fixed disposable-world scope, or action budget.

## Verification

Unit coverage includes cache key invalidation, publish/restore, content corruption, incomplete runtime rejection, symlink rejection when supported, and cross-process lock exclusion. The real MCP smoke launches two disposable Minecraft servers against an isolated cache: run one must report miss then stored; run two must report hit then not_needed. The smoke records ready times and call transcripts. Windows unit CI is enabled on pull requests targeting ai-debug-lab-v0.1; the real MCP workflow runs the two-launch smoke on Linux CI.

Local external-AI acceptance should additionally measure at least three sequential cold-to-warm launches on Windows, confirm no world/mod/config leakage, test cache corruption recovery, and separately test network-disconnected startup before making any offline claim.

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

Before V0.12.4, old version-keyed entries were not automatically evicted. V0.12.4 adds bounded LRU maintenance; manual removal remains available when no playtest is running.

## Security and limits

SHA-256 validation detects accidental corruption and incomplete writes; it is not a defense against a local attacker who can modify both cached files and their manifest. The cache is not a security sandbox. Runtime JARs are still loaded by the local Java process. Cache files are local and are not sent to the model by this code.

A verified runtime cache is **not** an offline-startup guarantee. Fabric may still make network requests for metadata or other reasons. V0.12.2 does not block network access and does not claim offline support. The cache also does not change the current RCON boundary, write allowlist, fixed disposable-world scope, or action budget.

## Verification

Unit coverage includes cache key invalidation, publish/restore, content corruption, incomplete runtime rejection, symlink rejection when supported, cross-process lock exclusion, LRU ordering, byte limits, and preservation of unmanifested user data. The real MCP smoke launches four disposable Minecraft servers against an isolated cache using three probe-JAR identities: A cold, B cold, A warm (to refresh recency), then C cold. With a two-entry limit, it must evict B while retaining recently used A; a direct restore check must then miss for B. The probe variants differ only in ZIP archive comments, and the test verifies that every uncompressed JAR member remains byte-identical. Both Linux and Windows CI run this real MCP/Fabric lifecycle smoke.

Local external-AI acceptance should additionally measure at least three sequential cold-to-warm launches on Windows, confirm no world/mod/config leakage, test cache corruption recovery, and separately test network-disconnected startup before making any offline claim.


### Empty optional runtime folders

The runtime root and Fabric server bootstrap directory must exist, and .fabric must contain files. The libraries and versions folders are preserved in the cache layout but may be empty for a valid installer/runtime layout; the manifest still records the exact file inventory.


## V0.12.3 startup observability follow-up

The \`restore\` and \`publish\` result objects include \`elapsed_ms\`. A cache hit reports publish as \`not_needed\` with zero elapsed time; the measured restore duration remains available. The real MCP smoke asserts both timing fields are present and non-negative.

Startup diagnostics classify recognized log messages into stable reason codes: \`read_timeout\`, \`connection_timeout\`, \`socket_timeout_exception\`, and \`proxy_failure\`. Both \`Read timed out\` and Fabric's \`Timed out after reading N bytes\` are recognized. Generic application startup timeout messages are deliberately not classified as network failures. These are log-observation signals, not proof of the exact request or root cause.


## V0.12.4 — bounded cache lifecycle

The cache root is now maintained automatically after restore and publish:

- Default bound: at most **3 managed entries** and **4 GiB** of actual cache files (including each manifest).
- Least-recently-used entries are evicted first. A successful restore updates the entry directory modification time as a best-effort last-used signal; cache correctness does not depend on timestamps.
- The current cache key is protected during the operation that uses it.
- The maintenance pass uses a root-level non-blocking lock, then non-blocking per-key locks. Entries in active use are skipped rather than deleted. If protected or active entries prevent the limits from being met, the result is \`over_budget\`; the active entry is preserved.
- Abandoned \`.{key}.tmp-*\` staging directories are removed only after the matching per-key lock can be acquired.
- Only directories with a valid app-owned cache manifest are candidates. Unrecognized files and directories in a custom cache root are left untouched.
- Before eviction, the manifest identity is recomputed and the on-disk file set is checked against the manifest inventory. An entry containing any unlisted file or an unexpected top-level item is treated as unmanaged and left untouched. Consequently, the entry/byte limits apply to managed cache entries; preserving user-added data can leave the physical cache root above the configured budget.
- Per-key lock files and the maintenance lock file are intentionally retained: deleting lock files can split OS file locks across different inodes/handles and break mutual exclusion.

Override the defaults with positive integer environment variables:

- \`MMS_AI_RUNTIME_CACHE_MAX_ENTRIES\` (default \`3\`)
- \`MMS_AI_RUNTIME_CACHE_MAX_BYTES\` (default \`4294967296\`)

Invalid environment values fall back to defaults. Explicit invalid constructor values are rejected. Each \`cache.json\` restore/publish record now includes a separate \`maintenance\` object with entry counts, bytes before/after, removed entries/staging directories, skipped active entries, status, and maintenance duration. Cache maintenance is best-effort: a busy lock or filesystem error is reported and does not invalidate a verified cache hit or block normal Fabric bootstrap.

This is a bounded local cache policy, not a time-to-live guarantee. A version entry remains while it is within the limits and used more recently than eviction candidates.


## V0.12.5 startup phase timing evidence

StartupTracker records the first poll at which it observes Fabric loading, Minecraft server start, the server Done marker, server stopping, and native probe readiness separately. Values are polling-observation times, not exact internal event times or per-request download durations. Use the measurements to identify which phase warrants further optimization; do not infer network latency or promise a fixed startup time.

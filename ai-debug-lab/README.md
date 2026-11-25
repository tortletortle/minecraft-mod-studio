# AI Debug Lab V0.1 — read-only diagnostic foundation

Separate companion to Minecraft Mod Studio. No modification of the HTML editor or existing save. No LLM credentials, npm dependencies, or new Minecraft mod required for this first slice.

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

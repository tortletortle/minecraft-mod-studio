# AI real playtest / V0.12 RC
Status: V0.12 external AI Windows smoke passed (PR #3); V0.12.1 fixes require new external acceptance. Startup status includes measured elapsed time, observed log stage, and a 600-second startup deadline. Slow startup is not yet optimized; repeat cold starts before claiming a performance improvement. Use a trusted Windows/Linux computer with Python 3.12+, Java 25 on PATH, Git, and an MCP-capable AI host. The demo runs a new temporary Fabric 26.2 server; no personal world or external model API key required by the tool. Download native-probe-evidence from https://github.com/tortletortle/minecraft-mod-studio/actions/runs/44754531844 (signed-in repo access) and extract the probe JAR. Alternatively build gradle -p ai-debug-lab/probe build with Gradle 9.5.1.

From branch ai-debug-lab-v0.1:
```sh
python -m pip install -r ai-debug-lab/requirements-mcp.txt
python ai-debug-lab/playtest.py prepare --assets playtest-assets --probe /absolute/path/to/mms-debug-probe-0.3.0.jar
```
Use a NEW assets directory. After reading and accepting https://www.minecraft.net/eula, configure your AI client's MCP stdio server (generic syntax; replace all paths including Python):
```json
{"mcpServers":{"minecraft-playtest":{"command":"/path/to/python","args":["/absolute/path/ai-debug-lab/playtest.py","serve","--assets","/absolute/path/playtest-assets","--evidence","/absolute/path/playtest-results","--accept-eula"]}}}
```
Use Windows absolute paths with JSON escaped backslashes or forward slashes. Do not run serve manually in a second terminal if the host starts it. World is discarded on normal close; logs/actions persist. A forcible host crash can bypass cleanup; stop orphan Java process if needed. Fresh demo only, no third-party pack support. Asset hashes protect against later drift, not malicious initial JARs. Local interface is not an OS sandbox. Allowlisted writes at a fixed coordinate and bounded tick steps, max 24 active calls; no arbitrary commands. Only this launcher exposes write tools. No model credentials, no external transmissions initiated by the launcher. The AI host may send evidence to its own service; use trusted host.

## Give the external AI this task
You are testing Minecraft Mod Studio, not reviewing code. Use MCP tools in a live disposable server. First call playtest_status; if starting, retry later; use the actual session returned. Independently discover available tools, inspect mod inventory and recipe evidence, verify a valid recipe output, then place two different allowed blocks and observe whether the snapshots reflect them (sampling may lag). Run tick-step experiments with at least two distinct step counts, verify exact deltas and recovery. Attempt one invalid tool argument to check the permission boundary. Do not use shell/console commands as a substitute; do not assume success. Report evidence from actual calls, observed vs inferred, failure, expected vs actual, and reproduction instructions. Never claim model success from scripted CI. Save transcripts if host supports it; launcher logs are in playtest-results.

The CI client is scripted and checks the real MCP-to-Java path; external AI model testing remains a separate acceptance gate. General modpack packaging, user UI and autonomous cross-mod minimization through MCP are not exposed here yet.

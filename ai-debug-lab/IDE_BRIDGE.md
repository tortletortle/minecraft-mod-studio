# V0.2 Universal IDE bridge

A local child process for any IDE or agent host; no dependence on a particular LLM, IDE vendor or cloud API. JSON Lines protocol mms-ide-jsonl/1, not MCP/DAP/LSP. The future browser editor requires a separately authorized native launcher or local bridge; an ordinary webpage cannot spawn this process.

```sh
python ai-debug-lab/ide_bridge.py --workspace /path/to/isolated/minecraft
```
Send one UTF-8 JSON object per line on stdin; receive one JSON response per line on stdout.
```json
{"id":1,"method":"tools.list","params":{}}
{"id":2,"method":"tools.call","params":{"name":"mods.inventory","arguments":{}}}
{"id":3,"method":"tools.call","params":{"name":"game.observe","arguments":{"operations":[{"op":"ticks"}]}}}
{"id":4,"method":"tools.call","params":{"name":"logs.tail","arguments":{}}}
```
The local launcher supplies the workspace and optional RCON password in an environment variable. Caller cannot change the workspace, host, credentials or port. No arbitrary command execution or writes. Logs and runtime outputs are untrusted and may contain personal data. The caller must not send them to external models without authorization. This is an early local prototype: fixed-path symlink checks are not a filesystem sandbox against concurrent malicious local processes. Large inventories and sampling may take time; callers should enforce process-level deadlines.

V0.2 also corrects the game-time acceptance assertion after two real server seeds returned 'The game time is ...'. The previous harness rejected valid output. Retain raw evidence before assertions. Rerun both seeds; do not interpret a passing vanilla test as modpack compatibility.

Next: native Fabric registry/block-entity adapter; integrated server attachment; isolated experiments with approval; structured JSON schemas and MCP adapter; actual Studio UI integration. No front-end changes in this slice.

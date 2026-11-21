# In-game AI debugging

The Fabric client adds /mms ask to the original Minecraft chat. It sends the current target, main-hand item, dimension, and tool match for block drops. The reply appears in the same chat. The command runs in a singleplayer world that has not been opened to LAN. Both backends share the same client JAR.

## Windows setup

Use Minecraft Java 26.2, Java 25, Fabric Loader 0.20.1, Fabric API 0.161.0+26.2, and an isolated Minecraft instance. Build with Gradle 9.5.1 from the repository root. Copy `ai-debug-lab/chat-client/build/libs/mms-debug-chat-0.1.0.jar` into the instance's `mods` directory before launching Minecraft. Use the same Python 3.12 interpreter for the bridge, MCP server, and dependency installation.

```powershell
gradle -p ai-debug-lab/chat-client build
python -m pip install -r ai-debug-lab/requirements-mcp.txt
```

## Answer from a desktop MCP host

Run the bridge from the repository root. The game directory must already exist.

```powershell
$game = (Resolve-Path 'C:/path/to/isolated-instance').Path
$bridge = (Resolve-Path 'ai-debug-lab/chat_bridge.py').Path
$python = (Get-Command python.exe).Source
& $python -B $bridge --game-dir $game --desktop-mcp
```

In a second terminal, configure the MCP host to launch chat_mcp.py using the same game directory. For Codex, register the stdio server once.

```powershell
$game = (Resolve-Path 'C:/path/to/isolated-instance').Path
$chatMcp = (Resolve-Path 'ai-debug-lab/chat_mcp.py').Path
$python = (Get-Command python.exe).Source
codex mcp add minecraft-chat -- $python -B $chatMcp --game-dir $game
```

Open a local conversation that lists minecraft-chat. Ask the assistant to call next_game_question, answer the returned question using the evidence, and call reply_to_game with the same request ID. In Minecraft, aim at a block, press T, and enter /mms ask Why isn't this block dropping anything? Repeat the listen instruction for a new question. The polling tool waits up to 20 seconds per call. Questions expire after 75 seconds. An idle conversation does not receive a new turn automatically.

For example, use this desktop prompt just before submitting the Minecraft command:

> Use minecraft-chat to wait for one game question. If none arrives, poll twice more. Answer using the supplied facts and send the response back with reply_to_game and the exact request ID. Keep the answer short.

The existing minecraft-debug server can provide additional evidence when configured for the intended instance. mods_inventory reads mod declarations. Runtime snapshots require the separate diagnostic probe and session ID. Game chat evidence is not a complete world snapshot.

## Answer from a local model

Start a local model server exposing /v1/chat/completions, then launch the bridge with its loopback URL and model name. One bridge can own each game directory at a time.

```powershell
python -B ai-debug-lab/chat_bridge.py --game-dir $game --model-url http://127.0.0.1:18087/v1/chat/completions --model mms-qwen-local
```

The bridge binds to loopback and creates a temporary authenticated connection descriptor inside the instance. Keep the descriptor outside version control. Minecraft can record game chat in its normal logs. The desktop host processes the question and the listed game context according to its own settings.

## Windows acceptance

Two submissions from the original Minecraft chat reached `next_game_question` and received `reply_to_game` responses in the same chat. Both targeted diamond ore. The game reported that a wooden pickaxe did not meet the drop requirement and an iron pickaxe did. The responses were written by the test operator. Model-generated responses and waking an idle desktop conversation remain unverified. See the [test report and evidence](evidence/in-game-chat-windows/README.md).

## Open-source alternatives

| Project | License and version | What it demonstrates |
| --- | --- | --- |
| [mc-codex-bridge](https://github.com/guajun/mc-codex-bridge) | MIT, Fabric 26.2, release 1.0.0 | Game chat can route a prompt to a selected session using `codex queue`. Its reply path uses a command-line helper and `tellraw`. |
| [MCP Fabric](https://github.com/denfry/mcpfabric/releases/tag/v0.10.0) | MIT, Fabric 26.2 artifact in release 0.10.0 | An in-game question can reach an active conversation through Claude Code Channels. |
| [mineGPT](https://github.com/inxups/mineGPT) | Fabric 1.21.1, mod metadata says `All Rights Reserved` | The closest example of a listener claiming a question and replying by ID. No source was copied. |
| [codex-chat-bridge](https://github.com/Lihan-Zhong/codex-chat-bridge) | MIT | A chat adapter and terminal UI share a bridge-managed App Server. Replies are associated with a turn ID. |

The relay uses the [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) for stdio. For automatic wake-up, the next candidate is the [documented App Server protocol](https://developers.openai.com/codex/app-server/) with a selected thread and replies tied to the returned turn ID. A Windows App Server smoke test verified an MCP tool call from a disposable thread. The bridge-managed thread and an already open desktop conversation require separate integration tests.

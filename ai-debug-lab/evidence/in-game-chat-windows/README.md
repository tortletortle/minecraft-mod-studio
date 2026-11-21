# In-game chat acceptance on Windows

Test date November 21, 2026. The test used Windows 11 build 26200, Minecraft Java 26.2, Temurin 25.0.5+8, Fabric Loader 0.20.1, Fabric API 0.161.0+26.2, Python 3.12.10 and MCP Python SDK 2.3.0. The mod was built with Gradle 9.5.1 and Loom 1.17.12. The tested JAR's SHA-256 was `9f686be17e3ba54a007053da056698b9917e494e7f197299c68ff40ec5c78ddf`.

## Procedure and results

1. Start the [desktop MCP relay](../../IN_GAME_CHAT.md#answer-from-a-desktop-mcp-host) and connect to `minecraft-chat` over stdio. Use an isolated client instance and a disposable singleplayer world. Place diamond ore in reach and equip a wooden pickaxe in survival mode. Keep LAN sharing off.
2. Call `next_game_question` while entering `/mms ask 为什么这块矿用现在的镐挖不掉落？` in Minecraft's original chat. Record the evidence and send an operator-written response with `reply_to_game` using the claimed ID. Verify the reply appears on screen and in the client log.
3. Repeat with an iron pickaxe aimed at the same block. The held item is the controlled variable.

| Trial | Observed target | Exact tool match for drops | Poll start to claim (s) | Claim to reply acknowledgement (s) | Reply shown in original chat |
| --- | --- | --- | ---: | ---: | --- |
| [Wooden pickaxe](wooden_pickaxe.json) | Diamond ore | False | 13.740 | 0.032 | Yes |
| [Iron pickaxe](iron_pickaxe.json) | Diamond ore | True | 15.565 | 0.008 | Yes |

The poll was started before the game input and includes operator input time. The reply acknowledgement measures the test driver's operator-written reply and does not include model inference. Client log messages use a clock with one-second resolution. These samples cannot establish end-to-end latency.

## Evidence and limits

- In both trials the Fabric client sent evidence from the real game, the MCP call returned it, and the matching Chinese reply appeared in the client window. The observed tool match supports the drop diagnosis. Measuring item drops would require a separate mining test.
- The raw client log also had Mojang account and Realms warnings. The isolated singleplayer test proceeded to the fixture and successfully displayed both responses. Account services were outside this test.
- A separate disposable Windows App Server thread returned `fabric-api` and `mms_debug_chat` via `minecraft-debug.mods_inventory`. This exercised direct MCP RPC. Automatic wake-up and model-written replies in an already open desktop conversation remain unverified.
- The Windows Python suite ran 98 tests with 96 passes and 2 skips. The 3 new chat MCP tests and the 4 existing MCP compatibility checks passed. The game round trips above are separate Windows client tests.

Two exploratory turns in a separate App Server process reached the existing local inference service. The first received HTTP 400 because the request had 16,611 tokens and the service allowed 4,096. After reducing instructions and tools, the model requested a nonexistent tool named `minecraft-server` and the expected MCP call did not complete. These attempts leave the model-driven path unverified. The desktop process used stdio and a connection to the default Windows daemon endpoint was refused. A follow-up client test could not activate the isolated window, so it contributed no new round trip.

[Minecraft log excerpt](minecraft-chat.log) retains the startup, fixture and chat lines. The evidence JSON records contain only the disposable fixture data and test replies. [SHA-256 checksums](SHA256SUMS) cover the published log excerpt and both evidence files. The full client log snapshot and original JSON are retained locally.

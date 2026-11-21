"""Actual MCP client exercising two fresh Java Fabric servers and the shared runtime cache."""
import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

from mcp import Client, StdioServerParameters


async def run_once(assets, evidence, cache_dir, run_name, expected_cache_state):
    run_evidence = evidence / run_name
    run_evidence.mkdir(parents=True, exist_ok=False)
    args = [
        str(Path(__file__).with_name("playtest.py").resolve()),
        "serve",
        "--assets", str(assets.resolve()),
        "--evidence", str(run_evidence.resolve()),
        "--runtime-cache-dir", str(cache_dir.resolve()),
        "--accept-eula",
    ]
    params = StdioServerParameters(command=sys.executable, args=args)
    transcript = []
    async with Client(params) as client:
        names = {tool.name for tool in (await client.list_tools()).tools}
        assert {"playtest_status", "playtest_set_block", "playtest_tick_steps", "game_recipe_status"} <= names, names

        async def call(name, arguments):
            answer = await client.call_tool(name, arguments)
            assert not answer.is_error, (name, answer)
            data = answer.structured_content["evidence"]
            transcript.append({"tool": name, "arguments": arguments, "result": data})
            return data

        deadline = time.monotonic() + 660
        while True:
            status = await call("playtest_status", {})
            if status["status"] == "ready":
                break
            assert status["status"] in ("starting", "waiting_for_probe"), status
            assert time.monotonic() < deadline, "startup timeout"
            await asyncio.sleep(2)

        session = status["session"]
        inventory = await call("mods_inventory", {})
        assert any(jar.get("id") == "mms_playtest" for jar in inventory["data"]["jars"]), inventory
        recipe = await call("game_recipe_status", {"session": session})
        assert recipe["data"]["recipe"]["experiment"]["output"] == "minecraft:emerald", recipe
        diagnosis = await call("mods_diagnose_recipe", {"session": session, "recipe": "mms_playtest:gem"})
        data = diagnosis["data"]
        assert data["in_memory_experiment"]["output"] == "minecraft:emerald", data
        assert "tag_resolution_unknown" not in [item["kind"] for item in data["hypotheses"]], data
        assert set(data["plan"]["covered_by_configured_snapshot"]) == {"query_active_recipe", "query_active_tag_members"}, data

        for block in ("minecraft:chest", "minecraft:stone"):
            result = await call("playtest_set_block", {"block": block})
            assert result["status"] == "verified", result
        result = await call("playtest_tick_steps", {"steps": [1, 5]})
        assert result["status"] == "passed" and result["cleanup"] == "verified_running", result
        assert [event["delta"] for event in result["events"] if event["kind"] == "step_verified"] == [1, 5]

        bad_steps = await client.call_tool("playtest_tick_steps", {"steps": [101]})
        assert bad_steps.is_error and "total at most 200" in str(bad_steps.content), bad_steps
        bad_block = await client.call_tool("playtest_set_block", {"block": "minecraft:tnt"})
        assert bad_block.is_error, "invalid block accepted"

    logs = list(run_evidence.glob("playtest-*/server.log"))
    assert len(logs) == 1, logs
    log = logs[0]
    assert "No key layers in MapLike" not in log.read_text(errors="replace"), "flat generator configuration error"
    startup = json.loads((log.parent / "startup.json").read_text())
    assert startup["ready_elapsed_s"] is not None, startup

    cache_report = json.loads((log.parent / "cache.json").read_text(encoding="utf-8"))
    assert cache_report["restore"]["status"] == expected_cache_state, cache_report
    if expected_cache_state == "miss":
        assert cache_report["publish"]["status"] in ("stored", "already_valid"), cache_report
    else:
        assert cache_report["publish"]["status"] == "not_needed", cache_report

    (run_evidence / "mcp-transcript.json").write_text(json.dumps(transcript, indent=2))
    return {
        "run": run_name,
        "cache_restore": cache_report["restore"]["status"],
        "cache_publish": cache_report["publish"]["status"],
        "ready_elapsed_s": startup["ready_elapsed_s"],
        "tool_calls": len(transcript),
    }


async def main(assets, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    # Isolate this CI experiment so its first run is guaranteed to miss and its
    # second run proves a real cache hit. The cache itself is not uploaded.
    with tempfile.TemporaryDirectory(prefix="mms-runtime-cache-ci-") as cache_tmp:
        cache_dir = Path(cache_tmp)
        first = await run_once(assets, evidence, cache_dir, "run-1-cache-miss", "miss")
        second = await run_once(assets, evidence, cache_dir, "run-2-cache-hit", "hit")
    summary = {"runs": [first, second], "cache_hit_verified": True}
    (evidence / "runtime-cache-smoke.json").write_text(json.dumps(summary, indent=2))
    print("MMS_REAL_MCP_PLAYTEST_AND_RUNTIME_CACHE_PASS", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.assets, args.evidence))

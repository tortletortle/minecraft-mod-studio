"""Actual MCP client exercising Fabric startup, warm hits, and bounded LRU eviction."""
import argparse
import asyncio
import hashlib
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

from mcp import Client, StdioServerParameters
from runtime_cache import RuntimeCache


def file_sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def jar_member_hashes(path):
    with zipfile.ZipFile(path) as archive:
        assert archive.testzip() is None, f"invalid probe JAR: {path}"
        return {
            item.filename: hashlib.sha256(archive.read(item)).hexdigest()
            for item in archive.infolist()
        }


def make_probe_variant(source_assets, target_assets, marker):
    """Change only the ZIP comment so the real probe JAR remains executable."""
    shutil.copytree(source_assets, target_assets)
    source_probe = Path(source_assets) / "probe.jar"
    variant_probe = target_assets / "probe.jar"
    original_members = jar_member_hashes(source_probe)
    with zipfile.ZipFile(variant_probe, "a") as archive:
        archive.comment = marker.encode("ascii")
    assert jar_member_hashes(variant_probe) == original_members, "probe JAR payload changed"
    hashes = {name: file_sha256(target_assets / name) for name in (
        "fabric-server.jar", "server.jar", "fabric-api.jar", "probe.jar"
    )}
    (target_assets / "hashes.json").write_text(
        json.dumps(hashes, indent=2), encoding="utf-8"
    )
    return target_assets


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
    for phase in ("restore", "publish"):
        elapsed_ms = cache_report[phase].get("elapsed_ms")
        assert isinstance(elapsed_ms, (int, float)) and elapsed_ms >= 0, (phase, cache_report)
        maintenance = cache_report[phase].get("maintenance")
        assert isinstance(maintenance, dict), (phase, cache_report)
        maintenance_status = maintenance.get("status")
        assert maintenance_status in ("clean", "pruned", "skipped"), (phase, maintenance)
        if maintenance_status == "skipped":
            assert maintenance.get("reason") == "maintenance_lock_busy", (phase, maintenance)
        assert maintenance.get("entry_count_after", -1) >= 0, (phase, maintenance)
        assert maintenance.get("bytes_after", -1) >= 0, (phase, maintenance)
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
        "cache_key": cache_report["cache_key"],
        "restore_maintenance": cache_report["restore"]["maintenance"],
        "publish_maintenance": cache_report["publish"]["maintenance"],
    }


async def main(assets, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    previous_limit = os.environ.get("MMS_AI_RUNTIME_CACHE_MAX_ENTRIES")
    os.environ["MMS_AI_RUNTIME_CACHE_MAX_ENTRIES"] = "2"
    try:
        # Two semantically identical probe JAR variants create distinct asset
        # identities without changing any class/resource payload. This makes
        # the real-server smoke exercise LRU ordering, not just cache hits.
        with tempfile.TemporaryDirectory(prefix="mms-runtime-cache-ci-") as cache_tmp:
            root = Path(cache_tmp)
            cache_dir = root / "cache"
            cache_dir.mkdir()
            variant_b = make_probe_variant(assets, root / "assets-b", "mms-cache-variant-b")
            variant_c = make_probe_variant(assets, root / "assets-c", "mms-cache-variant-c")

            first = await run_once(assets, evidence, cache_dir, "run-1-a-cold", "miss")
            second = await run_once(variant_b, evidence, cache_dir, "run-2-b-cold", "miss")
            third = await run_once(assets, evidence, cache_dir, "run-3-a-lru-hit", "hit")
            fourth = await run_once(variant_c, evidence, cache_dir, "run-4-c-cold", "miss")

            assert len({first["cache_key"], second["cache_key"], fourth["cache_key"]}) == 3
            eviction = fourth["publish_maintenance"]
            assert eviction["status"] == "pruned", eviction
            assert second["cache_key"] in eviction["removed_entries"], eviction
            assert first["cache_key"] not in eviction["removed_entries"], eviction

            # Independently verify that the evicted B key can no longer hit.
            with tempfile.TemporaryDirectory(prefix="mms-cache-eviction-recheck-") as target:
                recheck = RuntimeCache(variant_b, cache_dir).restore(Path(target))
            assert recheck["status"] == "miss", recheck

            summary = {
                "runs": [first, second, third, fourth],
                "cache_hit_verified": second["cache_restore"] == "miss" and third["cache_restore"] == "hit",
                "lru_eviction_verified": True,
                "max_entries": 2,
                "evicted_key": second["cache_key"],
                "retained_recent_key": first["cache_key"],
                "evicted_key_recheck": recheck["status"],
                "probe_jar_variants_preserve_member_hashes": True,
            }
            assert summary["cache_hit_verified"], summary
            (evidence / "runtime-cache-smoke.json").write_text(json.dumps(summary, indent=2))
            print("MMS_REAL_MCP_PLAYTEST_AND_LRU_CACHE_PASS", summary)
    finally:
        if previous_limit is None:
            os.environ.pop("MMS_AI_RUNTIME_CACHE_MAX_ENTRIES", None)
        else:
            os.environ["MMS_AI_RUNTIME_CACHE_MAX_ENTRIES"] = previous_limit

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(main(args.assets, args.evidence))

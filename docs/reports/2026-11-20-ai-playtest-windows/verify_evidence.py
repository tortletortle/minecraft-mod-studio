"""Offline consistency checks for captured evidence; this does NOT run Minecraft."""
import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / "evidence"

def read(name):
    return json.loads((EVIDENCE / name).read_text(encoding="utf-8"))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    checks = []
    def check(name, condition):
        checks.append({"name": name, "passed": bool(condition)})

    calls = [json.loads(line) for line in (EVIDENCE / "mcp-transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    by_id = {row["id"]: row for row in calls}
    def evidence(ident):
        return by_id[ident]["response"]["structuredContent"]["evidence"]
    def snapshot(ident):
        return evidence(ident)["data"]
    expected_tools = {"mods_inventory", "game_native_snapshot", "game_recipe_status", "mods_diagnose_recipe",
        "trials_summarize", "game_tick_observe", "playtest_status", "playtest_set_block", "playtest_tick_steps"}
    discovered = {tool["name"] for tool in read("host-ready.json")["tools"]["tools"]}
    check("20 ordered interactive MCP responses", [r["id"] for r in calls] == [f"{i:03}" for i in range(1, 21)])
    check("nine tools discovered and each invoked", discovered == expected_tools == {r["request"]["name"] for r in calls})
    check("no host exception", all("host_exception" not in r for r in calls))
    check("only three intended negative calls returned isError", {r["id"] for r in calls if r["response"].get("isError")} == {"014", "015", "016"})
    check("ready session obtained before gameplay", evidence("005")["status"] == "ready")
    session = evidence("005")["session"]
    check("snapshots belong to returned session", all(snapshot(i)["session"] == session for i in ("007", "009", "011", "017")))
    check("initial unforced chunk state recorded honestly", snapshot("007")["block"]["status"] == "chunk_not_loaded")
    recipe = evidence("006")["data"]["recipe"]
    experiment = recipe["experiment"]
    check("target recipe present and exact memory experiment matched", recipe["id"] == "mms_playtest:gem" and recipe["status"] == "present" and experiment["status"] == "matched")
    check("stone plus oak planks yielded one emerald", experiment["inputs"] == ["minecraft:stone", "minecraft:oak_planks"] and experiment["output"] == "minecraft:emerald" and experiment["count"] == 1)
    tag = evidence("006")["data"]["item_tag"]
    check("complete planks tag includes oak", tag["complete"] and "minecraft:oak_planks" in tag["members"])
    check("two block actions verified", all(evidence(i)["status"] == "verified" for i in ("008", "010")))
    chest, stone, after = [snapshot(i) for i in ("009", "011", "017")]
    check("chest and its block entity observed", chest["block"]["id"] == chest["block"]["block_entity_type"] == "minecraft:chest")
    check("stone observed without stale chest entity", stone["block"]["id"] == "minecraft:stone" and "block_entity_type" not in stone["block"])
    check("snapshot callback counters strictly advance", snapshot("007")["tick_callbacks"] < chest["tick_callbacks"] < stone["tick_callbacks"] < after["tick_callbacks"])
    check("snapshot timestamps strictly advance", snapshot("007")["at"] < chest["at"] < stone["at"] < after["at"])
    ticks = evidence("012")
    steps = [e for e in ticks["events"] if e["kind"] == "step_verified"]
    negatives = [e for e in ticks["events"] if e["kind"] == "negative_control"]
    check("frozen negative control stayed constant", len(negatives) == 1 and negatives[0]["passed"] and negatives[0]["before"] == negatives[0]["after"])
    check("requested steps exactly two and seven", ticks["steps"] == [2, 7] and [s["requested"] for s in steps] == [2, 7])
    check("measured step deltas exactly two and seven", [s["delta"] for s in steps] == [2, 7] and all(s["after"] - s["before"] == s["delta"] for s in steps))
    check("tick experiment passed and restored running", ticks["status"] == "passed" and ticks["cleanup"] == "verified_running")
    measurements = evidence("013")["data"]["measurements"]
    statuses = [m["raw_response"] for m in measurements if m["operation"]["op"] == "ticks"]
    times = [int(re.search(r"game time is (\d+)", m["raw_response"]).group(1)) for m in measurements if m["operation"]["op"] == "gametime"]
    check("independent follow-up observation reports running", len(statuses) == 2 and all("running normally" in s for s in statuses))
    check("follow-up game time increased", len(times) == 2 and times[1] > times[0])
    check("negative cases actually supplied TNT bool and 101", by_id["014"]["request"]["arguments"] == {"block": "minecraft:tnt"} and by_id["015"]["request"]["arguments"] == {"steps": [True]} and by_id["016"]["request"]["arguments"] == {"steps": [101]})
    check("negative cases left observed block unchanged", after["block"] == stone["block"])
    actions = [json.loads(line) for line in (EVIDENCE / "actions.jsonl").read_text(encoding="utf-8").splitlines()]
    check("only three valid writes consumed action budget", [a["sequence"] for a in actions] == [1, 2, 3] and [a["action"] for a in actions] == ["set_block", "set_block", "tick_steps"])
    check("diagnostic hypotheses remained unverified", evidence("018")["data"]["status"] == "hypotheses_only")
    check("single-seed trial summary correctly insufficient", evidence("019")["conditions"]["single_server_exact_tick_2_7"]["label"] == "insufficient")
    check("server remained ready through final call", evidence("020")["status"] == "ready")
    cleanup = read("cleanup-check.json")
    check("owned processes exited and temporary world removed", cleanup["host_closed"] and not any(cleanup[k] for k in ("owned_java_alive", "owned_host_alive", "owned_mcp_alive", "temporary_world_exists")))
    check("MCP context closed normally", read("host-closed.json")["status"] == "MCP_CONTEXT_CLOSED")
    server_log = (EVIDENCE / "server.log").read_text(encoding="utf-8")
    check("server log contains normal stop and world save", "Stopping the server" in server_log and "All dimensions are saved" in server_log and "Thread RCON Listener stopped" in server_log)
    unit, mcp = read("unit/result.redacted.json"), read("unit/mcp-result.redacted.json")
    check("unit results accurately preserve environment error", unit["testCount"] == 65 and unit["passedCount"] == 64 and unit["errorCount"] == 1 and unit["failureCount"] == 0 and unit["returnCode"] == 1)
    check("MCP compatibility three passed", mcp["testCount"] == 3 and mcp["returnCode"] == 0)
    check("actual probe build successful", "BUILD SUCCESSFUL in 1m 3s" in (EVIDENCE / "probe-build.log").read_text(encoding="utf-8"))
    hashes = json.loads((ROOT / "evidence-sha256.json").read_text(encoding="utf-8"))
    check("published evidence hash manifest matches every evidence file", set(hashes) == {p.relative_to(ROOT).as_posix() for p in EVIDENCE.rglob('*') if p.is_file()} and all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest for name, digest in hashes.items()))
    result = {"scope": "offline consistency of already captured live evidence; not another gameplay trial",
        "passed": all(c["passed"] for c in checks), "checks": checks, "call_count": len(calls),
        "tool_count": len(discovered), "valid_write_actions": len(actions), "independent_world_runs": 1}
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered)
    raise SystemExit(0 if result["passed"] else 1)

if __name__ == "__main__":
    main()

"""Offline checks of captured round-two evidence; does not run the game."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EV = ROOT / "evidence"

def load(name):
    return json.loads((EV / name).read_text(encoding="utf-8"))

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    rows = [json.loads(x) for x in (EV / "mcp-transcript.jsonl").read_text(encoding="utf-8").splitlines()]
    byid = {r["id"]: r for r in rows}
    results = []
    def check(name, value):
        results.append({"name": name, "passed": bool(value)})
    def e(i):
        return byid[i]["response"]["structuredContent"]["evidence"]
    def snap(i):
        return e(i)["data"]
    ready = e("006")
    session = ready["session"]
    check("46 ordered MCP responses", [r["id"] for r in rows] == [f"{i:03}" for i in range(1, 47)])
    discovered = {t["name"] for t in load("host-ready.json")["tools"]["tools"]}
    invoked = {r["request"]["name"] for r in rows}
    check("all nine discovered tools; eight intentionally invoked", len(discovered) == 9 and invoked == discovered - {"trials_summarize"})
    check("only five expected inputs rejected", {r["id"] for r in rows if r["response"].get("isError")} == {"015", "016", "017", "018", "042"})
    check("server ready with the actual returned session", ready["status"] == "ready" and bool(session))
    startup = ready["startup"]
    check("startup telemetry contains bounded elapsed observations", startup["timeout_s"] == 600 and startup["ready_elapsed_s"] == 372.828 and startup["stage"] == "ready" and startup["network_warning_observed"] is True and startup["transitions"] == [{"observed_stage":"waiting_for_probe","elapsed_s":337.093},{"observed_stage":"ready","elapsed_s":372.828}])
    check("startup timeout path not claimed as exercised", load("run-metadata.json")["live_startup"]["timeout_branch_exercised"] is False)
    recipe = e("007")["data"]["recipe"]
    exp = recipe["experiment"]
    tag = e("007")["data"]["item_tag"]
    check("runtime recipe and complete 12-member tag observed", recipe["id"] == "mms_playtest:gem" and recipe["status"] == "present" and tag["status"] == "present" and tag["complete"] and tag["total"] == 12 and len(tag["members"]) == 12 and "minecraft:oak_planks" in tag["members"])
    check("actual server memory experiment matches emerald x1", exp["scope"] == "in_memory_exact_recipe_only" and exp["status"] == "matched" and exp["output"] == "minecraft:emerald" and exp["count"] == 1)
    diag = e("009")["data"]
    plan = diag["plan"]
    check("diagnostic joins exact recipe/tag evidence without hypotheses", diag["session"] == session and diag["runtime_recipe"]["status"] == "present" and diag["runtime_item_tag"]["complete"] and diag["in_memory_experiment"]["status"] == "matched" and diag["hypotheses"] == [])
    check("configured evidence capabilities reported precisely", set(plan["covered_by_configured_snapshot"]) == {"query_active_recipe","query_active_tag_members"} and plan["in_memory_check_status"] == "matched" and "test_recipe_in_disposable_instance" in plan["required_capabilities_not_implemented"])
    unrelated = e("010")["data"]
    check("unconfigured recipe cannot inherit runtime gem evidence", unrelated["runtime_recipe"] is None and unrelated["runtime_item_tag"] is None and unrelated["in_memory_experiment"] is None and unrelated["plan"]["covered_by_configured_snapshot"] == [])
    check("initial unloaded chunk state reported as unknown", snap("008")["block"]["status"] == "chunk_not_loaded")
    check("chest write verified with matching native snapshot", e("011")["status"] == "verified" and snap("012")["block"]["id"] == "minecraft:chest" and snap("012")["block"]["block_entity_type"] == "minecraft:chest")
    check("air write verified with native snapshot and no block entity", e("013")["status"] == "verified" and snap("014")["block"]["id"] == "minecraft:air" and "block_entity_type" not in snap("014")["block"])
    tick = e("019")
    verified_steps = [x for x in tick["events"] if x["kind"] == "step_verified"]
    negative = [x for x in tick["events"] if x["kind"] == "negative_control"]
    check("tick freeze negative control stayed constant", len(negative) == 1 and negative[0]["passed"] and negative[0]["before"] == negative[0]["after"] == 7031)
    check("distinct tick steps measured exactly", tick["steps"] == [3,9] and [(x["before"],x["after"],x["delta"]) for x in verified_steps] == [(7031,7034,3),(7034,7043,9)] and tick["status"] == "passed" and tick["cleanup"] == "verified_running")
    obs = e("020")["data"]["measurements"]
    times = [int(x["raw_response"].split("game time is ")[1].split()[0]) for x in obs if x["operation"]["op"] == "gametime"]
    check("follow-up server observed running with advancing game time", len(times) == 2 and times == [7048,7053] and all("running normally" in x["raw_response"] for x in obs if x["operation"]["op"] == "ticks"))
    error_text = {i:"".join(x.get("text","") for x in byid[i]["response"].get("content",[])) for i in ("015","016","017","018","042")}
    exact_message = "Step budget exceeded: 1–10 entries, each integer 1–100, total at most 200."
    check("numeric and aggregate step budgets give stable actionable text", all(exact_message in error_text[i] for i in ("015","016","017")))
    check("strict integer schema rejects bool before a world action", "valid integer" in error_text["018"] and byid["018"]["request"]["arguments"] == {"steps":[True]})
    check("25th write is rejected with recorded generic error", error_text["042"] == "Error executing tool playtest_set_block" and byid["042"]["request"]["arguments"] == {"block":"minecraft:stone"})
    actions = [json.loads(x) for x in (EV / "actions.jsonl").read_text(encoding="utf-8").splitlines()]
    check("exactly 24 successful actions and no 25th ledger row", [a["sequence"] for a in actions] == list(range(1,25)) and len(actions) == 24 and all(a["data"]["status"] in ("verified","passed") for a in actions))
    check("post-budget read-only tools and status still work", e("043")["status"] == "ready" and snap("044")["block"]["id"] == "minecraft:air" and "running normally" in e("045")["data"]["measurements"][0]["raw_response"] and e("046")["status"] == "ready")
    check("configured flat-world ERROR message absent", "No key layers in MapLike[{}]" not in (EV / "server.log").read_text(encoding="utf-8") and "Read timed out" in (EV / "server.log").read_text(encoding="utf-8"))
    cleanup = load("cleanup-check.json")
    check("normal context close and temporary instance cleanup verified", cleanup["host_closed"] and cleanup["temporary_world_exists"] is False and all(not p["alive"] for p in cleanup["processes"]))
    check("server saved worlds and closed RCON normally", "Stopping the server" in (EV / "server.log").read_text(encoding="utf-8") and "All dimensions are saved" in (EV / "server.log").read_text(encoding="utf-8") and "Thread RCON Listener stopped" in (EV / "server.log").read_text(encoding="utf-8"))
    unit = load("unit/result.redacted.json")
    mcp = load("unit/mcp-result.redacted.json")
    check("unit outcomes preserve explicit symlink skip and junction coverage", unit["testCount"] == 72 and unit["passedCount"] == 71 and unit["skippedCount"] == 1 and unit["errorCount"] == 0 and unit["failureCount"] == 0 and unit["returnCode"] == 0)
    check("MCP compatibility suite 4 of 4 passed", mcp["testCount"] == 4 and mcp["passedCount"] == 4 and mcp["returnCode"] == 0)
    build = load("probe-build.json")
    check("probe built from unchanged source with stable SHA256", build["status"] == "BUILD_SUCCESS" and build["exitCode"] == 0 and build["probeDiffFromBaselineBefore"] == "" and build["probeDiffFromBaselineAfter"] == "" and build["artifacts"][0]["sha256"] == "f64b35f34739a65737d107989489b0beefcc69c19d2a3e2da1206f091c57298c" and build["javaTestAssessment"].startswith("NO-SOURCE"))
    ci = [x for x in load("github-ci.json") if x["headSha"] == "092f5656c51ea66016ee313630ec1807c49e2255"]
    check("latest commit GitHub CI runs shown as success", len(ci) >= 5 and all(x["status"] == "completed" and x["conclusion"] == "success" for x in ci))
    hashes = json.loads((ROOT / "evidence-sha256.json").read_text(encoding="utf-8"))
    actual_files = {p.relative_to(ROOT).as_posix() for p in EV.rglob("*") if p.is_file()}
    check("evidence hashes match every captured evidence file", set(hashes) == actual_files and all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == digest for name,digest in hashes.items()))
    report = {"scope":"offline consistency audit of one captured live server session; not another gameplay trial",
        "passed":all(x["passed"] for x in results),"checks":results,"mcp_calls":len(rows),"tools_discovered":len(discovered),"valid_actions":len(actions),"independent_worlds":1}
    rendered=json.dumps(report,ensure_ascii=False,indent=2)+"\n"
    if args.output: args.output.write_text(rendered,encoding="utf-8",newline="\n")
    print(rendered)
    raise SystemExit(0 if report["passed"] else 1)

if __name__ == "__main__":
    main()

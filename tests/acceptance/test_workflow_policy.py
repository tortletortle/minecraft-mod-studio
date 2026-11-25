#!/usr/bin/env python3
"""Guard CI trigger and Minecraft EULA authorization policy against regression."""
import json
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"


def load(name):
    # BaseLoader preserves the literal GitHub Actions key "on" and scalar values.
    path = WORKFLOWS / name
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    world = load("v25-world-test.yml")
    world_events = world.get("on", {})
    require(set(world_events) == {"workflow_dispatch"},
            f"World tests must be manual-only; found events: {sorted(world_events)}")

    dispatch = world_events["workflow_dispatch"]
    approval = dispatch["inputs"]["accept_eula"]
    require(approval.get("type") == "boolean", "EULA approval input must be boolean")
    require(approval.get("required") == "true", "EULA approval must be required")
    require(approval.get("default") == "false", "EULA approval must default to false")

    job = world["jobs"]["world-test"]
    guard = job.get("if", "")
    require("github.event_name == 'workflow_dispatch'" in guard,
            "World test job must require a manual workflow_dispatch event")
    require("inputs.accept_eula == true" in guard,
            "World test job must require explicit EULA approval")
    prepare = next((step for step in job["steps"]
                    if step.get("id") == "prepare"), None)
    require(prepare is not None, "Isolated world preparation step is missing")
    require("--accept-eula" in prepare.get("run", ""),
            "The isolated test setup must receive its explicit approval flag")

    required_pr_workflows = {
        "v25-acceptance.yml": "browser/Fabric acceptance",
        "v25-material-fixture.yml": "material fixture acceptance",
        "v26-resource-library.yml": "resource-library acceptance",
    }
    checked = {}
    for filename, label in required_pr_workflows.items():
        workflow = load(filename)
        events = workflow.get("on", {})
        require("workflow_dispatch" in events, f"{filename}: manual trigger missing")
        push = events.get("push")
        require(isinstance(push, dict) and push.get("branches") == ["main"],
                f"{filename}: push checks must run on main only; PRs cover feature branches")
        pr = events.get("pull_request")
        require(isinstance(pr, dict), f"{filename}: pull_request trigger missing")
        require("main" in pr.get("branches", []),
                f"{filename}: pull_request must target main")
        require("paths" in pr and pr["paths"],
                f"{filename}: PR path filters must be explicit")
        require(workflow.get("permissions", {}).get("contents") == "read",
                f"{filename}: contents permission must remain read-only")
        checked[filename] = label

    manual_eula_workflows = {
        "ai-debug-lab-conflict.yml": "conflict",
        "ai-debug-lab-live.yml": "smoke",
        "ai-debug-lab-playtest.yml": "live_mcp",
        "ai-debug-lab-probe.yml": "native",
    }
    for filename, job_name in manual_eula_workflows.items():
        workflow = load(filename)
        events = workflow.get("on", {})
        require(set(events) == {"workflow_dispatch"},
                f"{filename}: live Minecraft tests must be manual-only")
        approval = events["workflow_dispatch"]["inputs"]["accept_eula"]
        require(approval.get("type") == "boolean", f"{filename}: EULA approval must be boolean")
        require(approval.get("required") == "true", f"{filename}: EULA approval must be required")
        require(approval.get("default") == "false", f"{filename}: EULA approval must default to false")
        job = workflow["jobs"][job_name]
        guard = job.get("if", "")
        require("github.event_name == 'workflow_dispatch'" in guard,
                f"{filename}: live test must require manual dispatch")
        require("inputs.accept_eula == true" in guard,
                f"{filename}: live test must require explicit EULA approval")
        commands = "\n".join(step.get("run", "") for step in job["steps"])
        require("--accept-eula" in commands, f"{filename}: explicit EULA flag missing")

    for filename in ("ai-debug-lab.yml", "ai-debug-lab-mcp.yml", "ai-debug-lab-windows.yml"):
        workflow = load(filename)
        events = workflow.get("on", {})
        require(events.get("push", {}).get("branches") == ["main"],
                f"{filename}: unit-test pushes must target main only")
        require(events.get("pull_request", {}).get("branches") == ["main"],
                f"{filename}: unit tests must run on PRs targeting main")
        require(workflow.get("permissions", {}).get("contents") == "read",
                f"{filename}: contents permission must remain read-only")

    playtest_cli = (ROOT / "ai-debug-lab" / "playtest_check.py").read_text(encoding="utf-8")
    require("--accept-eula" in playtest_cli,
            "AI Debug Lab playtest CLI must expose explicit EULA approval")
    require("if not args.accept_eula" in playtest_cli,
            "AI Debug Lab playtest CLI must reject missing EULA approval")

    result = {
        "status": "PASS",
        "world_test_events": sorted(world_events),
        "eula_required": approval["required"],
        "eula_default": approval["default"],
        "manual_guard": guard,
        "pull_request_workflows": checked,
        "assertions": 65,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

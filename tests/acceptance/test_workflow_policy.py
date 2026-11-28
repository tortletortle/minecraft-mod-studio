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
    v01_world = load("v01-creature-world-test.yml")
    v01_events = v01_world.get("on", {})
    require(set(v01_events) == {"workflow_dispatch"},
            f"V0.1 world tests must be manual-only; found events: {sorted(v01_events)}")
    v01_approval = v01_events["workflow_dispatch"]["inputs"]["accept_eula"]
    require(v01_approval.get("type") == "boolean", "V0.1 EULA approval input must be boolean")
    require(v01_approval.get("required") == "true", "V0.1 EULA approval must be required")
    require(v01_approval.get("default") == "false", "V0.1 EULA approval must default to false")
    v01_guard = v01_world["jobs"]["world-test"].get("if", "")
    require("inputs.accept_eula == true" in v01_guard,
            "V0.1 world test job must require explicit EULA approval")

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

    result = {
        "status": "PASS",
        "world_test_events": sorted(world_events),
        "eula_required": approval["required"],
        "eula_default": approval["default"],
        "manual_guard": guard,
        "pull_request_workflows": checked,
        "assertions": 30,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Guard CI triggers and Minecraft EULA authorization policy against regression."""
import json
import re
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


def eula_true_writes(value, location=""):
    """Find explicit eula: true or shell-style eula=true in workflow content."""
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_location = f"{location}.{key}" if location else str(key)
            if str(key).casefold() == "eula" and (
                child is True or str(child).casefold() == "true"
            ):
                found.append(child_location)
            found.extend(eula_true_writes(child, child_location))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(eula_true_writes(child, f"{location}[{index}]"))
    elif isinstance(value, str):
        if re.search(r"(?i)\beula\s*=\s*true\b", value):
            found.append(location or "<string>")
    return found


def main():
    checked = {}

    v01_world_name = "v01-creature-world-test.yml"
    v01_world = load(v01_world_name)
    v01_events = v01_world.get("on", {})
    require(set(v01_events) == {"workflow_dispatch"},
            f"{v01_world_name} must be manual-only; found events: {sorted(v01_events)}")
    v01_dispatch = v01_events["workflow_dispatch"]
    v01_approval = v01_dispatch.get("inputs", {}).get("accept_eula", {})
    require(v01_approval.get("type") == "boolean",
            f"{v01_world_name}: EULA approval input must be boolean")
    require(v01_approval.get("required") == "true",
            f"{v01_world_name}: EULA approval must be required")
    require(v01_approval.get("default") == "false",
            f"{v01_world_name}: EULA approval must default to false")
    v01_guard = v01_world["jobs"]["world-test"].get("if", "")
    require("inputs.accept_eula == true" in v01_guard,
            f"{v01_world_name}: job must require explicit EULA approval")
    checked[v01_world_name] = "manual-only; required accept_eula; default false"

    world = load("v25-world-test.yml")
    world_events = world.get("on", {})
    require(set(world_events) == {"workflow_dispatch"},
            f"v25-world-test.yml must be manual-only; found events: {sorted(world_events)}")
    dispatch = world_events["workflow_dispatch"]
    approval = dispatch.get("inputs", {}).get("accept_eula", {})
    require(approval.get("type") == "boolean", "V2.5 EULA approval input must be boolean")
    require(approval.get("required") == "true", "V2.5 EULA approval must be required")
    require(approval.get("default") == "false", "V2.5 EULA approval must default to false")
    job = world["jobs"]["world-test"]
    guard = job.get("if", "")
    require("github.event_name == 'workflow_dispatch'" in guard,
            "V2.5 world test job must require a manual workflow_dispatch event")
    require("inputs.accept_eula == true" in guard,
            "V2.5 world test job must require explicit EULA approval")
    prepare = next((step for step in job["steps"] if step.get("id") == "prepare"), None)
    require(prepare is not None, "V2.5 isolated world preparation step is missing")
    require("--accept-eula" in prepare.get("run", ""),
            "V2.5 isolated test setup must receive its explicit approval flag")
    checked["v25-world-test.yml"] = "manual-only; required accept_eula; default false"

    required_pr_workflows = {
        "v25-acceptance.yml": "browser/Fabric acceptance",
        "v25-material-fixture.yml": "material fixture acceptance",
        "v26-resource-library.yml": "resource-library acceptance",
    }
    for filename, label in required_pr_workflows.items():
        workflow = load(filename)
        events = workflow.get("on", {})
        require("workflow_dispatch" in events, f"{filename}: manual trigger missing")
        push = events.get("push")
        require(isinstance(push, dict) and push.get("branches") == ["main"],
                f"{filename}: push checks must run on main only")
        pr = events.get("pull_request")
        require(isinstance(pr, dict), f"{filename}: pull_request trigger missing")
        require("main" in pr.get("branches", []),
                f"{filename}: pull_request must target main")
        require("paths" in pr and pr["paths"],
                f"{filename}: PR path filters must be explicit")
        require(workflow.get("permissions", {}).get("contents") == "read",
                f"{filename}: contents permission must remain read-only")
        checked[filename] = label

    # No workflow that runs automatically on push/PR may silently accept the EULA.
    for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        events = workflow.get("on", {}) if isinstance(workflow, dict) else {}
        if isinstance(events, dict) and ({"push", "pull_request"} & set(events)):
            violations = eula_true_writes(workflow)
            require(not violations,
                    f"{path.name}: automatic workflow must not write eula=true: {violations}")

    result = {
        "status": "PASS",
        "checked_workflows": checked,
        "v01_world_test_events": sorted(v01_events),
        "v01_eula_required": v01_approval["required"],
        "v01_eula_default": v01_approval["default"],
        "v25_world_test_events": sorted(world_events),
        "v25_eula_required": approval["required"],
        "v25_eula_default": approval["default"],
        "automatic_workflow_eula_true_writes": [],
        "pull_request_workflows": required_pr_workflows,
        "assertions": 38,
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

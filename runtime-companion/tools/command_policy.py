"""Conservative, preview-only policy for Minecraft command operation plans.

This module classifies command intent from the live Brigadier command string.
It never executes commands and never trusts mod-supplied manifest risk labels.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

POLICY_VERSION = "mms-command-policy-v1"
MAX_COMMAND_LENGTH = 512
MAX_PLAN_STEPS = 8

_READ_ONLY_ROOTS = {"help", "list", "locate", "seed"}
_WORLD_EDIT_ROOTS = {"fill", "clone", "place", "structure", "forceload", "setblock"}
_ENTITY_EDIT_ROOTS = {"summon", "kill", "spreadplayers"}
_PLAYER_EDIT_ROOTS = {
    "give", "clear", "item", "loot", "experience", "xp", "effect", "enchant", "recipe",
    "tp", "teleport", "gamemode", "defaultgamemode",
}
_WORLD_STATE_ROOTS = {
    "weather", "gamerule", "difficulty", "worldborder", "setworldspawn", "spawnpoint",
}
_SERVER_CONTROL_ROOTS = {
    "reload", "stop", "save-all", "save-off", "save-on", "op", "deop", "ban", "ban-ip",
    "pardon", "pardon-ip", "kick", "whitelist", "publish", "perf", "jfr",
}


def normalize_command(command: str) -> str:
    if not isinstance(command, str):
        raise ValueError("COMMAND_MUST_BE_STRING")
    if len(command) > MAX_COMMAND_LENGTH:
        raise ValueError("COMMAND_TOO_LONG")
    if any(ord(char) < 32 or ord(char) == 127 for char in command):
        raise ValueError("COMMAND_CONTAINS_CONTROL_CHARACTER")
    normalized = command.strip()
    if normalized.startswith("/"):
        normalized = normalized[1:]
    normalized = normalized.strip()
    if not normalized:
        raise ValueError("COMMAND_EMPTY")
    if len(normalized) > MAX_COMMAND_LENGTH:
        raise ValueError("COMMAND_TOO_LONG")
    return normalized


def _policy(
    category: str,
    risk: str,
    risk_level: str,
    effects: list[str],
    reversibility: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "category": category,
        "risk": risk,
        "risk_level": risk_level,
        "effects": effects,
        "reversibility": reversibility,
        "policy_reason": reason,
    }


def classify_command(command: str) -> dict[str, Any]:
    normalized = normalize_command(command)
    tokens = normalized.split()
    root = tokens[0].casefold()
    sub = [token.casefold() for token in tokens[1:4]]

    if root in _READ_ONLY_ROOTS:
        return _policy(
            "read_only", "read_only", "none", [], "no_state_change",
            "该命令属于明确列出的查询/帮助命令；本工具仍只生成预览，不执行命令。",
        )
    if root == "time" and sub[:1] == ["query"]:
        return _policy(
            "read_only", "read_only", "none", [], "no_state_change",
            "time query 只读取世界时间；本工具仍只生成预览，不执行命令。",
        )
    if root == "data" and sub[:1] == ["get"]:
        return _policy(
            "read_only", "read_only", "none", ["entity_or_block_data_read"], "no_state_change",
            "data get 是只读数据查询；其他 data 子命令默认按修改操作处理。",
        )
    if root == "attribute" and len(sub) >= 3 and sub[2] == "get":
        return _policy(
            "read_only", "read_only", "none", ["entity_attribute_read"], "no_state_change",
            "attribute get 是只读属性查询；属性 base/modifier 写入不属于此白名单。",
        )
    if root == "scoreboard" and sub[:2] == ["players", "get"]:
        return _policy(
            "read_only", "read_only", "none", ["scoreboard_read"], "no_state_change",
            "scoreboard players get 只读取分数；其他记分板操作不属于只读白名单。",
        )
    if root == "team" and sub[:1] == ["list"]:
        return _policy(
            "read_only", "read_only", "none", ["team_read"], "no_state_change",
            "team list 只读取队伍信息。",
        )
    if root == "bossbar" and sub[:1] == ["list"]:
        return _policy(
            "read_only", "read_only", "none", ["bossbar_read"], "no_state_change",
            "bossbar list 只读取 BossBar 列表。",
        )

    # Generic dispatchers and datapack functions can hide arbitrary nested
    # commands. Never infer their safety from the outer command name.
    if root in {"execute", "function", "trigger"}:
        return _policy(
            "unknown", "unknown", "unknown", ["delegated_or_scripted_operation"], "unknown",
            "该命令可以委派或运行其他逻辑，当前策略无法可靠推断其完整副作用，默认拒绝。",
        )
    if root in _WORLD_EDIT_ROOTS:
        return _policy(
            "world_edit", "persistent_mutation", "high", ["blocks", "world"], "snapshot_required",
            "该命令可能永久修改世界方块；需要计算影响范围、保存前态快照和独立审批。",
        )
    if root in _ENTITY_EDIT_ROOTS:
        return _policy(
            "entity_edit", "destructive", "critical", ["entities", "world"], "context_dependent",
            "该命令会生成、移除或移动实体；必须验证目标范围、数量和世界状态。",
        )
    if root in _PLAYER_EDIT_ROOTS:
        return _policy(
            "player_or_inventory_edit", "persistent_mutation", "high", ["player_state", "inventory_or_effects"], "context_dependent",
            "该命令会改变玩家状态、物品栏或效果，不能作为只读操作处理。",
        )
    if root in _WORLD_STATE_ROOTS or root == "time":
        return _policy(
            "world_state_edit", "persistent_mutation", "high", ["world_rules", "world_state"], "context_dependent",
            "该命令会改变世界规则、时间、天气或出生点等持久状态。",
        )
    if root in _SERVER_CONTROL_ROOTS:
        return _policy(
            "server_control", "destructive", "critical", ["server_state", "world_lifecycle"], "unknown",
            "该命令可能影响服务器生命周期、权限或存档状态，操作规划器默认拒绝。",
        )

    return _policy(
        "unknown", "unknown", "unknown", ["unknown"], "unknown",
        "命令根未进入独立审核的策略白名单；模组清单描述和风险标签不构成执行授权，默认拒绝。",
    )


def build_command_plan(commands: list[str], validations: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(commands, list) or not 1 <= len(commands) <= MAX_PLAN_STEPS:
        raise ValueError("PLAN_STEP_COUNT_OUT_OF_RANGE")
    if not isinstance(validations, list) or len(validations) != len(commands):
        raise ValueError("PLAN_VALIDATION_COUNT_MISMATCH")

    steps: list[dict[str, Any]] = []
    for index, (raw_command, validation) in enumerate(zip(commands, validations), start=1):
        command = normalize_command(raw_command)
        if not isinstance(validation, dict):
            raise ValueError("COMMAND_VALIDATION_RESPONSE_INVALID")
        if validation.get("syntax_only") is not True or validation.get("execution_enabled") is not False:
            raise ValueError("COMMAND_VALIDATION_SCOPE_INVALID")
        if type(validation.get("valid")) is not bool:
            raise ValueError("COMMAND_VALIDATION_RESULT_INVALID")
        if validation.get("command") != command:
            raise ValueError("COMMAND_VALIDATION_ECHO_MISMATCH")

        assessment = classify_command(command)
        syntax_valid = validation["valid"]
        if not syntax_valid:
            decision = "syntax_invalid"
        elif assessment["risk"] == "unknown":
            decision = "blocked_by_default"
        elif assessment["risk"] == "read_only":
            decision = "preview_only"
        else:
            decision = "operator_review_required"

        steps.append({
            "index": index,
            "command": command,
            "root": command.split()[0].casefold(),
            "syntax_valid": syntax_valid,
            "syntax_error_code": str(validation.get("error_code", ""))[:80] if not syntax_valid else "",
            "decision": decision,
            "requires_operator_approval": decision in {"operator_review_required", "blocked_by_default"},
            "execution_allowed": False,
            **assessment,
        })

    if any(not step["syntax_valid"] for step in steps):
        overall_status = "invalid"
    elif any(step["decision"] == "blocked_by_default" for step in steps):
        overall_status = "blocked_unknown"
    elif any(step["decision"] == "operator_review_required" for step in steps):
        overall_status = "operator_review_required"
    else:
        overall_status = "read_only_preview"

    plan_payload = {"policy_version": POLICY_VERSION, "steps": steps}
    canonical = json.dumps(plan_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    plan_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return {
        "plan_schema_version": 1,
        "plan_id": plan_id,
        "policy_version": POLICY_VERSION,
        "mode": "preview_only",
        "overall_status": overall_status,
        "step_count": len(steps),
        "all_syntax_valid": all(step["syntax_valid"] for step in steps),
        "execution_enabled": False,
        "commands_executed": 0,
        "manifest_risk_labels_used_for_authorization": False,
        "validation_scope": "live_brigadier_parse_only; custom mod argument parsers are not sandboxed",
        "steps": steps,
    }

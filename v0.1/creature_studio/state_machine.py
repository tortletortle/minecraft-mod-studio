from __future__ import annotations

import copy
import re
from typing import Any, Mapping

CONDITIONS = (
    "always", "has_target", "target_in_range", "health_below", "moving",
    "no_target", "is_aggressive", "stopped", "target_out_of_range",
    "is_dead", "animation_finished",
)
_STATE_ID = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,31}$")


def defaults(mob: Mapping[str, Any]) -> dict[str, Any]:
    animations = mob.get("model", {}).get("animations", [])
    by_id = {a.get("id"): a for a in animations if isinstance(a, dict)}
    loop_fallback = next((a.get("id") for a in animations if a.get("loop")), None)
    if not loop_fallback:
        return {"enabled": False, "initial": "idle", "states": [], "transitions": []}
    idle = "idle" if by_id.get("idle", {}).get("loop") else loop_fallback
    walk = "walk" if by_id.get("walk", {}).get("loop") else idle

    def state(identifier: str, animation: str) -> dict[str, Any]:
        return {"id": identifier, "animation": animation, "loop": bool(by_id.get(animation, {}).get("loop"))}

    states = [state("idle", idle), state("walk", walk)]
    for identifier in ("attack", "hurt", "death"):
        if identifier in by_id:
            states.append(state(identifier, identifier))
    transitions: list[dict[str, Any]] = []
    if "death" in by_id:
        transitions.append({"id": "tr_death", "from": "*", "to": "death", "condition": "is_dead", "threshold": 0, "priority": 100, "cooldown": 0})
    if "attack" in by_id:
        transitions.extend((
            {"id": "tr_attack", "from": "*", "to": "attack", "condition": "target_in_range", "threshold": 2.8, "priority": 80, "cooldown": 8},
            {"id": "tr_attack_exit", "from": "attack", "to": "walk", "condition": "target_out_of_range", "threshold": 2.8, "priority": 60, "cooldown": 3},
            {"id": "tr_attack_idle", "from": "attack", "to": "idle", "condition": "no_target", "threshold": 0, "priority": 55, "cooldown": 3},
            {"id": "tr_attack_done", "from": "attack", "to": "walk", "condition": "animation_finished", "threshold": 0, "priority": 50, "cooldown": 0},
        ))
    transitions.extend((
        {"id": "tr_walk", "from": "idle", "to": "walk", "condition": "moving", "threshold": .02, "priority": 40, "cooldown": 2},
        {"id": "tr_idle", "from": "walk", "to": "idle", "condition": "no_target", "threshold": 0, "priority": 20, "cooldown": 2},
        {"id": "tr_idle_stop", "from": "walk", "to": "idle", "condition": "stopped", "threshold": .01, "priority": 10, "cooldown": 2},
    ))
    return {"enabled": True, "initial": "idle", "states": states, "transitions": transitions}


def normalize(machine: Any, mob: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(machine, dict):
        return defaults(mob)
    result = copy.deepcopy(machine)
    default = defaults(mob)
    animations = mob.get("model", {}).get("animations", [])
    by_id = {a.get("id"): a for a in animations if isinstance(a, dict)}
    result["enabled"] = result.get("enabled") if isinstance(result.get("enabled"), bool) else True
    result["initial"] = result.get("initial") if isinstance(result.get("initial"), str) else default["initial"]
    if not by_id:
        result["enabled"] = False
        result["states"] = result.get("states") if isinstance(result.get("states"), list) else []
        result["transitions"] = result.get("transitions") if isinstance(result.get("transitions"), list) else []
        return result
    states = result.get("states")
    result["states"] = (
        [{**s, "loop": bool(by_id[s["animation"]]["loop"])} if isinstance(s, dict) and s.get("animation") in by_id else s for s in states]
        if isinstance(states, list) and states else default["states"]
    )
    transitions = result.get("transitions")
    result["transitions"] = transitions if isinstance(transitions, list) and transitions else default["transitions"]
    return result


def validate(machine: Any, mob: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(machine, dict):
        return ["state machine missing"]
    animation_list = mob.get("model", {}).get("animations")
    has_animation_catalog = isinstance(animation_list, list) and bool(animation_list)
    animations = {
        a.get("id"): a for a in (animation_list or []) if isinstance(a, dict)
    }
    if "enabled" in machine and not isinstance(machine.get("enabled"), bool):
        errors.append("enabled must be boolean")
    states: dict[str, dict[str, Any]] = {}
    state_list = machine.get("states")
    transitions = machine.get("transitions")
    if not isinstance(state_list, list) or not 1 <= len(state_list) <= 32:
        errors.append("states must contain 1..32 entries")
        state_list = state_list if isinstance(state_list, list) else []
    if not isinstance(transitions, list) or len(transitions) > 128:
        errors.append("transitions must contain at most 128 entries")
        transitions = transitions if isinstance(transitions, list) else []
    for state in state_list:
        if not isinstance(state, dict):
            errors.append("invalid state record")
            continue
        identifier = state.get("id")
        if not isinstance(identifier, str) or not _STATE_ID.fullmatch(identifier):
            errors.append(f"invalid state id {identifier}")
        if identifier in states:
            errors.append(f"duplicate state {identifier}")
        states[identifier] = state
        animation_id = state.get("animation")
        if not isinstance(animation_id, str) or not animation_id:
            errors.append(f"state {identifier} animation must be a non-empty string")
        animation = animations.get(animation_id)
        if has_animation_catalog and animation is None:
            errors.append(f"state {identifier} references missing animation {animation_id}")
        if not isinstance(state.get("loop"), bool):
            errors.append(f"state {identifier} loop must be boolean")
        elif has_animation_catalog and animation is not None and state["loop"] != bool(animation.get("loop")):
            errors.append(f"state {identifier} loop must inherit animation {animation_id} loop setting")
    if machine.get("initial") not in states:
        errors.append("initial state does not exist")
    transition_ids: set[str] = set()
    for transition in transitions:
        if not isinstance(transition, dict):
            errors.append("invalid transition record")
            continue
        identifier = transition.get("id")
        if not isinstance(identifier, str) or not _STATE_ID.fullmatch(identifier):
            errors.append(f"invalid transition id {identifier}")
        if identifier in transition_ids:
            errors.append(f"duplicate transition {identifier}")
        transition_ids.add(identifier)
        source, target = transition.get("from"), transition.get("to")
        if source != "*" and source not in states:
            errors.append(f"transition {identifier} has missing source")
        if target not in states:
            errors.append(f"transition {identifier} has missing target")
        if source != "*" and source == target:
            errors.append(f"transition {identifier} cannot transition a state to itself")
        condition_name = transition.get("condition")
        if condition_name not in CONDITIONS:
            errors.append(f"transition {identifier} has unsupported condition")
        threshold = transition.get("threshold")
        maximum = 1 if condition_name == "health_below" else 3 if condition_name in ("moving", "stopped") else 64
        if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 <= threshold <= maximum:
            errors.append(f"transition {identifier} threshold must be 0..{maximum} for {condition_name}")
        priority, cooldown = transition.get("priority"), transition.get("cooldown")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 100:
            errors.append(f"transition {identifier} priority must be 0..100")
        if not isinstance(cooldown, int) or isinstance(cooldown, bool) or not 0 <= cooldown <= 1200:
            errors.append(f"transition {identifier} cooldown must be 0..1200")
    return list(dict.fromkeys(errors))


def condition(transition: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    kind, threshold = transition.get("condition"), transition.get("threshold", 0)
    has_target = bool(context.get("hasTarget"))
    distance = context.get("targetDistance", float("inf"))
    speed = context.get("speed", 0)
    return {
        "always": True,
        "has_target": has_target,
        "no_target": not has_target,
        "target_in_range": has_target and distance <= threshold,
        "target_out_of_range": has_target and distance > threshold,
        "health_below": context.get("healthRatio", 1) <= threshold,
        "moving": speed >= threshold,
        "stopped": speed < threshold,
        "is_aggressive": bool(context.get("aggressive")),
        "is_dead": bool(context.get("isDead")),
        "animation_finished": bool(context.get("animationFinished")),
    }.get(kind, False)


def choose(machine: Mapping[str, Any], context: Mapping[str, Any], current: str,
           cooldowns: Mapping[str, int] | None = None) -> dict[str, Any] | None:
    cooldowns = cooldowns or {}
    eligible = [
        transition for transition in machine.get("transitions", [])
        if (transition.get("from") == "*" or transition.get("from") == current)
        and transition.get("to") != current
        and cooldowns.get(transition.get("id"), 0) <= 0
        and condition(transition, context)
    ]
    eligible.sort(key=lambda item: (-item.get("priority", 0), item.get("id", "")))
    return eligible[0] if eligible else None

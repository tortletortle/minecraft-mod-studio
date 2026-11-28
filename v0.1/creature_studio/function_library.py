from __future__ import annotations

import json
from typing import Any, Mapping

from .behavior_graph import _function_table, validate_graph

PACK_LIMIT = 262_144
FORMAT = "minecraft-mod-studio-functions"
VERSION = 1


class FunctionPackError(ValueError):
    pass


def _normalize_expr(expr: Mapping[str, Any]) -> dict[str, Any]:
    op = expr["op"]
    if op == "literal":
        return {"op": op, "type": expr["type"], "value": expr["value"]}
    if op == "param":
        return {"op": op, "id": expr["id"]}
    if op == "call":
        return {"op": op, "fn": expr["fn"], "args": [_normalize_expr(arg) for arg in expr["args"]]}
    if op == "if":
        return {
            "op": op,
            "test": _normalize_expr(expr["test"]),
            "yes": _normalize_expr(expr["yes"]),
            "no": _normalize_expr(expr["no"]),
        }
    if op == "not":
        return {"op": op, "value": _normalize_expr(expr["value"])}
    return {"op": op, "a": _normalize_expr(expr["a"]), "b": _normalize_expr(expr["b"])}


def normalize_function(function: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": function["id"],
        "params": [{"id": param["id"], "type": param["type"]} for param in function["params"]],
        "returns": function["returns"],
        "body": _normalize_expr(function["body"]),
    }


def validate_library(library: Any) -> list[str]:
    if not isinstance(library, list):
        return ["Function library must be an array"]
    _, errors = _function_table({"version": 3, "functions": library})
    return errors


def pack(library: list[dict[str, Any]]) -> str:
    errors = validate_library(library)
    if errors:
        raise FunctionPackError("; ".join(errors))
    document = {
        "format": FORMAT,
        "version": VERSION,
        "functions": [normalize_function(function) for function in library],
    }
    result = json.dumps(document, ensure_ascii=False, indent=2, separators=(",", ": "))
    if len(result.encode("utf-8")) > PACK_LIMIT:
        raise FunctionPackError("Function pack exceeds 256 KiB")
    return result


def references(library: list[dict[str, Any]], nodes: list[dict[str, Any]]) -> set[str]:
    found = {node.get("fn") for node in nodes if node.get("op") == "call"}

    def walk(expr: Any) -> None:
        if not isinstance(expr, dict):
            return
        if expr.get("op") == "call":
            found.add(expr.get("fn"))
            for argument in expr.get("args", []):
                walk(argument)
        elif expr.get("op") == "if":
            walk(expr.get("test"))
            walk(expr.get("yes"))
            walk(expr.get("no"))
        elif expr.get("op") == "not":
            walk(expr.get("value"))
        else:
            walk(expr.get("a"))
            walk(expr.get("b"))

    for function in library:
        walk(function.get("body"))
    return {item for item in found if isinstance(item, str)}


def _signature(function: Mapping[str, Any]) -> tuple[Any, ...]:
    return function["returns"], tuple((param["id"], param["type"]) for param in function["params"])


def commit_library(graph: Mapping[str, Any], library: list[dict[str, Any]]) -> dict[str, Any]:
    errors = validate_library(library)
    if errors:
        return {"errors": errors}
    candidate = {**graph, "version": 3, "functions": json.loads(json.dumps(library))}
    candidate_errors = validate_graph(candidate)
    if candidate_errors:
        return {"errors": candidate_errors}
    refs = references(candidate["functions"], graph.get("nodes", []))
    after = {function["id"]: function for function in candidate["functions"]}
    for previous in graph.get("functions", []):
        next_function = after.get(previous["id"])
        if previous["id"] in refs and (
            next_function is None or _signature(previous) != _signature(next_function)
        ):
            errors.append(
                f"{previous['id']}: referenced function cannot be deleted or have its signature changed"
            )
    if errors:
        return {"errors": errors}
    return {"errors": [], "graph": candidate}


def import_pack(
    graph: Mapping[str, Any],
    local_library: list[dict[str, Any]],
    text: str,
) -> dict[str, Any]:
    try:
        if not isinstance(text, str) or len(text.encode("utf-8")) > PACK_LIMIT:
            raise FunctionPackError("Function pack exceeds 256 KiB")
        document = json.loads(text)
        if (
            not isinstance(document, dict)
            or document.get("format") != FORMAT
            or document.get("version") != VERSION
            or not isinstance(document.get("functions"), list)
        ):
            raise FunctionPackError("Unsupported function pack format")
        incoming = json.loads(pack(document["functions"]))["functions"]
        local = json.loads(pack(local_library))["functions"]
        merged = {function["id"]: function for function in local}
        added = 0
        unchanged = 0
        for function in incoming:
            previous = merged.get(function["id"])
            if previous is not None:
                if previous != function:
                    raise FunctionPackError(f"Conflicting function ID: {function['id']}")
                unchanged += 1
            else:
                merged[function["id"]] = function
                added += 1
        committed = commit_library(graph, list(merged.values()))
        if committed["errors"]:
            return {"errors": committed["errors"]}
        return {
            "errors": [],
            "library": committed["graph"]["functions"],
            "added": added,
            "unchanged": unchanged,
        }
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {"errors": [str(exc)]}

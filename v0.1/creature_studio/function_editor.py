from __future__ import annotations

from typing import Any, Mapping, Sequence

from .function_library import commit_library


def _zero(value_type: str) -> dict[str, Any]:
    if value_type not in {"int", "bool"}:
        raise ValueError("Unsupported expression type")
    return {"op": "literal", "type": value_type, "value": False if value_type == "bool" else 0}


def available(function: Mapping[str, Any], library: Sequence[Mapping[str, Any]], target_type: str) -> list[str]:
    if target_type not in {"int", "bool"}:
        return []
    choices = ["literal"]
    if any(param.get("type") == target_type for param in function.get("params", [])):
        choices.append("param")
    if any(item.get("id") != function.get("id") and item.get("returns") == target_type for item in library):
        choices.append("call")
    choices.append("if")
    if target_type == "int":
        choices.extend(("add", "subtract", "multiply", "divide"))
    else:
        choices.extend(("not", "and", "or", "lt", "lte", "gt", "gte",
                        "eq_int", "ne_int", "eq_bool", "ne_bool"))
    return choices


def type_of(expression: Mapping[str, Any] | None, function: Mapping[str, Any],
            library: Sequence[Mapping[str, Any]]) -> str | None:
    if not isinstance(expression, Mapping):
        return None
    op = expression.get("op")
    if op == "literal":
        return expression.get("type")
    if op == "param":
        return next((p.get("type") for p in function.get("params", []) if p.get("id") == expression.get("id")), None)
    if op == "call":
        return next((f.get("returns") for f in library if f.get("id") == expression.get("fn")), None)
    if op == "if":
        return type_of(expression.get("yes"), function, library)
    if op in {"add", "subtract", "multiply", "divide"}:
        return "int"
    if op in {"not", "and", "or", "lt", "lte", "gt", "gte", "eq", "ne"}:
        return "bool"
    return None


def kind(expression: Mapping[str, Any], function: Mapping[str, Any],
         library: Sequence[Mapping[str, Any]]) -> str:
    op = expression.get("op")
    if op in {"eq", "ne"}:
        return f"{op}_{'bool' if type_of(expression.get('a'), function, library) == 'bool' else 'int'}"
    return str(op)


def make(operation: str, target_type: str, function: Mapping[str, Any],
         library: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if operation not in available(function, library, target_type):
        raise ValueError("Operation does not match the target expression type")
    if operation == "literal":
        return _zero(target_type)
    if operation == "param":
        param = next(p for p in function["params"] if p["type"] == target_type)
        return {"op": "param", "id": param["id"]}
    if operation == "call":
        target = next(f for f in library if f.get("id") != function.get("id") and f.get("returns") == target_type)
        return {"op": "call", "fn": target["id"], "args": [_zero(p["type"]) for p in target["params"]]}
    if operation == "if":
        return {"op": "if", "test": _zero("bool"), "yes": _zero(target_type), "no": _zero(target_type)}
    if operation == "not":
        return {"op": "not", "value": _zero("bool")}
    parts = operation.split("_", 1)
    op = parts[0]
    equality_type = parts[1] if len(parts) == 2 else None
    operand_type = equality_type or ("bool" if op in {"and", "or"} else "int")
    right = {"op": "literal", "type": "int", "value": 1} if op == "divide" else _zero(operand_type)
    return {"op": op, "a": _zero(operand_type), "b": right}


def slots(expression: Mapping[str, Any], target_type: str, function: Mapping[str, Any],
          library: Sequence[Mapping[str, Any]]) -> list[tuple[Any, str, str]]:
    op = expression.get("op")
    if op == "if":
        return [("test", "condition", "bool"), ("yes", "true", target_type), ("no", "false", target_type)]
    if op == "not":
        return [("value", "input", "bool")]
    if op == "call":
        target = next((f for f in library if f.get("id") == expression.get("fn")), None)
        if target is None:
            return []
        return [(("args", index), param["id"], param["type"]) for index, param in enumerate(target["params"])]
    if op in {"literal", "param"}:
        return []
    operand_type = "bool" if op in {"and", "or"} or (
        op in {"eq", "ne"} and kind(expression, function, library).endswith("_bool")
    ) else "int"
    return [("a", "left", operand_type), ("b", "right", operand_type)]


def commit(graph: Mapping[str, Any], library: list[dict[str, Any]]) -> dict[str, Any]:
    return commit_library(graph, library)

from __future__ import annotations

import copy
import re
from typing import Any, Mapping

OPS = {"event", "branch", "set", "add", "subtract", "multiply", "divide",
       "repeat", "loop_back", "call", "message", "lightning", "heal", "end"}
EVENTS = {"use", "use_on"}
CONTEXTS = {"sneaking": "bool", "stack_count": "int"}
ARITHMETIC = {"add", "subtract", "multiply", "divide"}
BINARY_FUNCTIONS = {"add", "subtract", "multiply", "divide", "lt", "lte", "gt", "gte",
                    "eq", "ne", "and", "or"}
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,31}$")
_LIMIT = 1_000_000


def _is_id(value: Any) -> bool:
    return isinstance(value, str) and bool(_ID.fullmatch(value))


def _valid_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and -_LIMIT <= value <= _LIMIT


def _expr_type(expr: Any, variables: Mapping[str, str]) -> str | None:
    if not isinstance(expr, dict):
        return None
    source = expr.get("source")
    if source == "literal":
        value, kind = expr.get("value"), expr.get("type")
        if kind == "int" and _valid_int(value):
            return "int"
        if kind == "bool" and isinstance(value, bool):
            return "bool"
    elif source == "variable":
        return variables.get(expr.get("value"))
    elif source == "context":
        return CONTEXTS.get(expr.get("value"))
    return None


def _function_table(graph: Mapping[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    functions = graph.get("functions", [])
    if not isinstance(functions, list) or len(functions) > 16:
        return {}, ["Function library must contain at most 16 functions"]
    if functions and graph.get("version") != 3:
        errors.append("Function library requires graph version 3")
    table: dict[str, dict[str, Any]] = {}
    for fn in functions:
        if (not isinstance(fn, dict) or not _is_id(fn.get("id"))
                or fn.get("id") in table or fn.get("returns") not in {"int", "bool"}
                or not isinstance(fn.get("params"), list) or len(fn["params"]) > 8):
            errors.append("Malformed or duplicate function signature")
            continue
        params = fn["params"]
        if any(not isinstance(p, dict) or not _is_id(p.get("id")) or p.get("type") not in {"int", "bool"} for p in params):
            errors.append("Malformed function parameter")
            continue
        if len({p["id"] for p in params}) != len(params):
            errors.append("Duplicate function parameter")
            continue
        table[fn["id"]] = fn

    deps: dict[str, set[str]] = {}
    costs: dict[str, int] = {}
    for key, fn in table.items():
        calls: set[str] = set()
        count = 0
        params = {p["id"]: p["type"] for p in fn["params"]}

        def infer(expr: Any, depth: int = 0) -> str | None:
            nonlocal count
            count += 1
            if count > 64 or depth > 12 or not isinstance(expr, dict):
                errors.append(f"{key}: expression size/depth limit or malformed expression")
                return None
            op = expr.get("op")
            if op == "literal":
                kind = expr.get("type")
                return kind if _expr_type({"source": "literal", **expr}, {}) == kind else None
            if op == "param":
                result = params.get(expr.get("id"))
                if result is None:
                    errors.append(f"{key}: unknown parameter")
                return result
            if op == "call":
                target = table.get(expr.get("fn"))
                args = expr.get("args")
                if target is None or not isinstance(args, list) or len(args) != len(target["params"]):
                    errors.append(f"{key}: unresolved function or argument count")
                    return None
                calls.add(target["id"])
                for arg, param in zip(args, target["params"]):
                    if infer(arg, depth + 1) != param["type"]:
                        errors.append(f"{key}: argument type mismatch")
                return target["returns"]
            if op == "if":
                test, yes, no = (infer(expr.get(k), depth + 1) for k in ("test", "yes", "no"))
                if test == "bool" and yes is not None and yes == no:
                    return yes
                errors.append(f"{key}: conditional type mismatch")
                return None
            if op == "not":
                if infer(expr.get("value"), depth + 1) == "bool":
                    return "bool"
                errors.append(f"{key}: not requires bool")
                return None
            if op in BINARY_FUNCTIONS:
                left, right = infer(expr.get("a"), depth + 1), infer(expr.get("b"), depth + 1)
                if op in {"eq", "ne"}:
                    result = "bool" if left is not None and left == right else None
                elif op in {"and", "or"}:
                    result = "bool" if left == right == "bool" else None
                elif left == right == "int":
                    result = "bool" if op in {"lt", "lte", "gt", "gte"} else "int"
                else:
                    result = None
                if result is None:
                    errors.append(f"{key}: function operand type mismatch")
                if op == "divide" and isinstance(expr.get("b"), dict) and expr["b"].get("op") == "literal" and expr["b"].get("value") == 0:
                    errors.append(f"{key}: literal division by zero")
                return result
            errors.append(f"{key}: unknown expression operator")
            return None

        if infer(fn.get("body")) != fn["returns"]:
            errors.append(f"{key}: return type mismatch")
        deps[key] = calls
        costs[key] = count

    if not errors:
        active: set[str] = set()
        memo: dict[str, int] = {}

        def expanded_cost(key: str) -> int:
            if key in active:
                errors.append(f"{key}: recursive function call forbidden")
                return 1025
            if key in memo:
                return memo[key]
            active.add(key)
            cost = costs[key]
            for child in deps[key]:
                if child not in table:
                    errors.append(f"{key}: unknown called function {child}")
                    continue
                cost += expanded_cost(child)
                if cost > 1024:
                    errors.append(f"{key}: expanded function cost exceeds 1024")
                    break
            active.remove(key)
            memo[key] = cost
            return cost

        for key in table:
            expanded_cost(key)
    return table, list(dict.fromkeys(errors))


def validate_graph(graph: Any) -> list[str]:
    if (not isinstance(graph, dict) or graph.get("version") not in {1, 2, 3}
            or not isinstance(graph.get("nodes"), list) or not 1 <= len(graph["nodes"]) <= 64
            or not isinstance(graph.get("variables"), list) or len(graph["variables"]) > 16
            or not _is_id(graph.get("entry"))):
        return ["Malformed graph header or graph limits (64 nodes, 16 variables)"]
    errors: list[str] = []
    if "functions" in graph and not isinstance(graph["functions"], list):
        return ["Malformed function library"]
    variables: dict[str, str] = {}
    for variable in graph["variables"]:
        if (not isinstance(variable, dict) or not _is_id(variable.get("id"))
                or variable.get("id") in variables or variable.get("type") not in {"int", "bool"}
                or not isinstance(variable.get("name"), str) or len(variable["name"]) > 40
                or _expr_type({"source": "literal", "type": variable.get("type"), "value": variable.get("initial")}, {}) != variable.get("type")):
            errors.append("Malformed or duplicate variable")
            continue
        variables[variable["id"]] = variable["type"]
    nodes: dict[str, dict[str, Any]] = {}
    for node in graph["nodes"]:
        if (not isinstance(node, dict) or not _is_id(node.get("id")) or node.get("id") in nodes
                or node.get("op") not in OPS or not isinstance(node.get("x"), (int, float))
                or not 0 <= node["x"] <= 1800 or not isinstance(node.get("y"), (int, float))
                or not 0 <= node["y"] <= 1200):
            errors.append("Malformed or duplicate node")
            continue
        nodes[node["id"]] = node
    functions, function_errors = _function_table(graph)
    errors.extend(function_errors)

    def ports(node: Mapping[str, Any]) -> list[str]:
        op = node.get("op")
        if op == "end":
            return []
        if op == "branch":
            return ["yes", "no"]
        if op == "repeat":
            return ["body", "next"]
        if op == "loop_back":
            return ["repeat"]
        return ["next"]

    def flow_ports(node: Mapping[str, Any]) -> list[str]:
        return [] if node.get("op") == "loop_back" else ports(node)

    def value_type(expr: Any) -> str | None:
        return _expr_type(expr, variables)

    for node in graph["nodes"]:
        if not isinstance(node, dict) or node.get("id") not in nodes:
            continue
        key, op = node["id"], node["op"]
        for port in ports(node):
            target = node.get(port)
            if target != "" and not _is_id(target):
                errors.append(f"{key}: malformed flow port {port}")
        if op == "event" and node.get("event") not in EVENTS:
            errors.append(f"{key}: unsupported event")
        if op == "branch":
            left, right = value_type(node.get("a")), value_type(node.get("b"))
            if left is None or left != right or node.get("compare") not in {"eq", "ne", "lt", "lte", "gt", "gte"}:
                errors.append(f"{key}: malformed condition")
            elif node["compare"] not in {"eq", "ne"} and left != "int":
                errors.append(f"{key}: ordering requires int operands")
        if op in {"set"} | ARITHMETIC:
            target = variables.get(node.get("variable"))
            expected = "int" if op in ARITHMETIC else target
            if target is None or (op in ARITHMETIC and target != "int") or value_type(node.get("value")) != expected:
                errors.append(f"{key}: malformed assignment")
            if op == "divide" and node.get("value", {}).get("source") == "literal" and node["value"].get("value") == 0:
                errors.append(f"{key}: literal division by zero")
        if op == "call":
            fn = functions.get(node.get("fn"))
            args = node.get("args")
            if (graph.get("version") != 3 or fn is None or not isinstance(args, list)
                    or len(args) != len(fn["params"]) or not _is_id(node.get("variable"))):
                errors.append(f"{key}: malformed call or requires graph version 3")
            else:
                if any(value_type(arg) != param["type"] for arg, param in zip(args, fn["params"])):
                    errors.append(f"{key}: function argument type mismatch")
                if variables.get(node["variable"]) != fn["returns"]:
                    errors.append(f"{key}: function return target type mismatch")
        if op == "repeat" and (not isinstance(node.get("count"), int) or not 1 <= node["count"] <= 32):
            errors.append(f"{key}: repeat count must be 1..32")
        if op == "message" and (not isinstance(node.get("text"), str) or len(node["text"]) > 160):
            errors.append(f"{key}: invalid message")
        if op in {"lightning", "heal"} and value_type(node.get("value")) != "int":
            errors.append(f"{key}: malformed action input")
        if op == "end" and not isinstance(node.get("success"), bool):
            errors.append(f"{key}: invalid return value")

    if len([n for n in graph["nodes"] if isinstance(n, dict) and n.get("op") == "event"]) != 1:
        errors.append("Exactly one entry event is required")
    if nodes.get(graph["entry"], {}).get("op") != "event":
        errors.append("Graph entry must reference the event node")

    active: set[str] = set()
    reachable: set[str] = set()

    def visit(key: str) -> None:
        if key in active:
            errors.append(f"{key}: control-flow cycle (loops unsupported)")
            return
        if key in reachable or key not in nodes:
            return
        active.add(key)
        reachable.add(key)
        for port in flow_ports(nodes[key]):
            target = nodes[key].get(port)
            if isinstance(target, str):
                visit(target)
        active.remove(key)

    visit(graph["entry"])
    if any(node.get("op") == "end" for node in graph["nodes"] if isinstance(node, dict)) is False:
        errors.append("At least one end node required")
    for key in nodes:
        if key not in reachable:
            errors.append(f"{key}: unreachable node")

    # Loop bodies are exclusive regions; all paths must terminate at their owning loop_back.
    owners: dict[str, str] = {}
    for loop in (n for n in graph["nodes"] if isinstance(n, dict) and n.get("op") == "repeat"):
        region: set[str] = set()

        def walk_loop(key: str) -> None:
            if key in region or key not in nodes:
                return
            region.add(key)
            node = nodes[key]
            if node.get("op") == "loop_back":
                if node.get("repeat") != loop["id"]:
                    errors.append(f"{key}: loop_back must target owning repeat {loop['id']}")
                return
            if node.get("op") in {"repeat", "event", "end"}:
                errors.append(f"{key}: repeat body cannot contain nested repeat, event or end")
                return
            for port in flow_ports(node):
                target = node.get(port)
                if isinstance(target, str):
                    walk_loop(target)

        walk_loop(loop.get("body", ""))
        if loop.get("next") in region:
            errors.append(f"{loop['id']}: repeat body reaches its exit")
        if not any(nodes[key].get("op") == "loop_back" for key in region):
            errors.append(f"{loop['id']}: repeat requires loop_back")
        for key in region:
            if key in owners:
                errors.append(f"{key}: shared loop body")
            owners[key] = loop["id"]
        for node in graph["nodes"]:
            if not isinstance(node, dict):
                continue
            for port in flow_ports(node):
                if node.get(port) in region and node.get("id") not in region and not (node.get("id") == loop["id"] and port == "body"):
                    errors.append(f"{node.get('id')}: external entry into loop body {loop['id']}")
    for node in graph["nodes"]:
        if isinstance(node, dict) and node.get("op") == "loop_back":
            if node.get("id") not in owners or nodes.get(node.get("repeat"), {}).get("op") != "repeat" or owners.get(node["id"]) != node.get("repeat"):
                errors.append(f"{node.get('id')}: invalid or orphan loop_back")
    return list(dict.fromkeys(errors))


def _eval_expr(expr: Mapping[str, Any], variables: dict[str, Any], context: Mapping[str, Any]) -> Any:
    source = expr["source"]
    if source == "literal":
        return expr["value"]
    if source == "variable":
        return variables[expr["value"]]
    return context[expr["value"]]


def _eval_function_expr(expr: Mapping[str, Any], params: Mapping[str, Any],
                       functions: Mapping[str, dict[str, Any]], depth: int = 0,
                       active: tuple[str, ...] = ()) -> Any:
    if depth > 12:
        raise RuntimeError("Function expression depth limit exceeded")
    op = expr["op"]
    if op == "literal":
        return expr["value"]
    if op == "param":
        return params[expr["id"]]
    if op == "call":
        key = expr["fn"]
        if key in active:
            raise RuntimeError("Recursive function call")
        target = functions[key]
        args = [_eval_function_expr(item, params, functions, depth + 1, active) for item in expr["args"]]
        return _eval_function_expr(target["body"],
            {p["id"]: value for p, value in zip(target["params"], args)},
            functions, depth + 1, active + (key,))
    if op == "if":
        arm = "yes" if _eval_function_expr(expr["test"], params, functions, depth + 1, active) else "no"
        return _eval_function_expr(expr[arm], params, functions, depth + 1, active)
    if op == "not":
        return not _eval_function_expr(expr["value"], params, functions, depth + 1, active)
    if op == "and":
        return bool(_eval_function_expr(expr["a"], params, functions, depth + 1, active)) and bool(
            _eval_function_expr(expr["b"], params, functions, depth + 1, active))
    if op == "or":
        return bool(_eval_function_expr(expr["a"], params, functions, depth + 1, active)) or bool(
            _eval_function_expr(expr["b"], params, functions, depth + 1, active))
    left = _eval_function_expr(expr["a"], params, functions, depth + 1, active)
    right = _eval_function_expr(expr["b"], params, functions, depth + 1, active)
    if op == "eq": return left == right
    if op == "ne": return left != right
    if op == "lt": return left < right
    if op == "lte": return left <= right
    if op == "gt": return left > right
    if op == "gte": return left >= right
    if op == "divide":
        if right == 0:
            raise ArithmeticError("Function division by zero")
        result = int(left / right)
    elif op == "add": result = left + right
    elif op == "subtract": result = left - right
    elif op == "multiply": result = left * right
    else: raise ValueError(f"Unsupported function operator: {op}")
    return max(-_LIMIT, min(_LIMIT, result))


def simulate(graph: Mapping[str, Any], context: Mapping[str, Any] | None = None,
             max_steps: int = 2048) -> dict[str, Any]:
    errors = validate_graph(graph)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(max_steps, int) or not 1 <= max_steps <= 2048:
        raise ValueError("max_steps must be 1..2048")
    context = context or {}
    variables = {v["id"]: v["initial"] for v in graph["variables"]}
    nodes = {n["id"]: n for n in graph["nodes"]}
    functions = {f["id"]: f for f in graph.get("functions", [])}
    loop_counts: dict[str, int] = {}
    trace: list[str] = []
    effects: list[dict[str, Any]] = []
    pc = graph["entry"]
    budget = min(max_steps, len(nodes) * (33 if any(n["op"] == "repeat" for n in nodes.values()) else 1))
    for _ in range(budget):
        node = nodes[pc]
        trace.append(pc)
        op = node["op"]
        if op == "event":
            pc = node["next"]
        elif op == "branch":
            a, b = _eval_expr(node["a"], variables, context), _eval_expr(node["b"], variables, context)
            cmp = node["compare"]
            result = {"eq": a == b, "ne": a != b, "lt": a < b, "lte": a <= b, "gt": a > b, "gte": a >= b}[cmp]
            pc = node["yes"] if result else node["no"]
        elif op == "set":
            variables[node["variable"]] = _eval_expr(node["value"], variables, context)
            pc = node["next"]
        elif op in ARITHMETIC:
            left, right = variables[node["variable"]], _eval_expr(node["value"], variables, context)
            if op == "divide":
                if right == 0:
                    raise ArithmeticError("division by zero")
                result = int(left / right)
            elif op == "add": result = left + right
            elif op == "subtract": result = left - right
            elif op == "multiply": result = left * right
            else: raise ValueError(f"Unsupported arithmetic operation: {op}")
            variables[node["variable"]] = max(-_LIMIT, min(_LIMIT, result))
            pc = node["next"]
        elif op == "call":
            fn = functions[node["fn"]]
            args = [_eval_expr(arg, variables, context) for arg in node["args"]]
            parameters = {param["id"]: value for param, value in zip(fn["params"], args)}
            variables[node["variable"]] = _eval_function_expr(fn["body"], parameters, functions, active=(fn["id"],))
            pc = node["next"]
        elif op == "repeat":
            count = loop_counts.get(pc, 0)
            if count < node["count"]:
                loop_counts[pc] = count + 1
                pc = node["body"]
            else:
                loop_counts[pc] = 0
                pc = node["next"]
        elif op == "loop_back":
            pc = node["repeat"]
        elif op in {"message", "heal", "lightning"}:
            value = node.get("text") if op == "message" else _eval_expr(node["value"], variables, context)
            effects.append({"type": op, "value": value})
            pc = node["next"]
        elif op == "end":
            return {"success": node["success"], "variables": variables, "trace": trace, "effects": effects}
        else:
            raise ValueError(f"Unsupported behavior operation: {op}")
    raise RuntimeError("Behavior graph exceeded execution step budget")


def _java_string(value: str) -> str:
    import base64
    encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
    return f'new String(java.util.Base64.getDecoder().decode("{encoded}"), java.nio.charset.StandardCharsets.UTF_8)'


def compile_java_method(graph: Mapping[str, Any], index: int) -> str:
    errors = validate_graph(graph)
    if errors:
        raise ValueError("; ".join(errors))
    if not isinstance(index, int) or not 0 <= index <= 200:
        raise ValueError("Invalid program index")
    nodes = graph["nodes"]
    ids = {node["id"]: i for i, node in enumerate(nodes)}
    variables = {v["id"]: (f"v{i}", v["type"]) for i, v in enumerate(graph["variables"])}
    functions, function_errors = _function_table(graph)
    if function_errors:
        raise ValueError("; ".join(function_errors))
    function_names = {key: f"fn{index}_{i}" for i, key in enumerate(functions)}

    def value(expr: Mapping[str, Any]) -> str:
        if expr["source"] == "literal":
            return str(expr["value"]).lower()
        if expr["source"] == "variable":
            return variables[expr["value"]][0]
        return "ctx.sneaking()" if expr["value"] == "sneaking" else "Math.max(0, clamp(ctx.stackCount()))"

    def function_expr(expr: Mapping[str, Any], params: Mapping[str, str]) -> str:
        op = expr["op"]
        if op == "literal": return str(expr["value"]).lower()
        if op == "param": return params[expr["id"]]
        if op == "call": return f"{function_names[expr['fn']]}({', '.join(function_expr(a, params) for a in expr['args'])})"
        if op == "if": return f"({function_expr(expr['test'], params)} ? {function_expr(expr['yes'], params)} : {function_expr(expr['no'], params)})"
        if op == "not": return f"(!{function_expr(expr['value'], params)})"
        left, right = function_expr(expr["a"], params), function_expr(expr["b"], params)
        if op == "divide": return f"clamp((long) {left} / {right})"
        if op in {"add", "subtract", "multiply"}:
            symbol = {"add": "+", "subtract": "-", "multiply": "*"}[op]
            return f"clamp((long) {left} {symbol} {right})"
        symbol = {"eq": "==", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">=", "and": "&&", "or": "||"}[op]
        return f"({left} {symbol} {right})"

    helper_methods: list[str] = []
    for key, fn in functions.items():
        params = {param["id"]: f"p{i}" for i, param in enumerate(fn["params"])}
        return_type = "int" if fn["returns"] == "int" else "boolean"
        signature = ", ".join(("int" if p["type"] == "int" else "boolean") + f" {params[p['id']]}" for p in fn["params"])
        helper_methods.append(
            f"    private static {return_type} {function_names[key]}({signature}) {{ return {function_expr(fn['body'], params)}; }}\\n"
        )

    comparisons = {"eq": "==", "ne": "!=", "lt": "<", "lte": "<=", "gt": ">", "gte": ">="}
    lines = []
    for node in nodes:
        op = node["op"]
        if op == "event":
            body = f"pc = {ids[node['next']]};"
        elif op == "branch":
            body = f"pc = ({value(node['a'])} {comparisons[node['compare']]} {value(node['b'])}) ? {ids[node['yes']]} : {ids[node['no']]};"
        elif op == "set":
            body = f"{variables[node['variable']][0]} = {value(node['value'])}; pc = {ids[node['next']]};"
        elif op in ARITHMETIC:
            var, rhs = variables[node["variable"]][0], value(node["value"])
            symbol = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}[op]
            guard = f"if ({rhs} == 0) return false; " if op == "divide" else ""
            body = f"{guard}{var} = clamp((long) {var} {symbol} {rhs}); pc = {ids[node['next']]};"
        elif op == "call":
            args = ", ".join(value(arg) for arg in node["args"])
            body = f"try {{ {variables[node['variable']][0]} = {function_names[node['fn']]}({args}); }} catch (ArithmeticException ex) {{ return false; }} pc = {ids[node['next']]};"
        elif op == "repeat":
            slot = ids[node["id"]]
            body = f"if (c{slot} < {node['count']}) {{ c{slot}++; pc = {ids[node['body']]}; }} else {{ c{slot} = 0; pc = {ids[node['next']]}; }}"
        elif op == "loop_back":
            body = f"pc = {ids[node['repeat']]};"
        elif op == "message":
            body = f"ctx.message({_java_string(node['text'])}); pc = {ids[node['next']]};"
        elif op in {"heal", "lightning"}:
            amount = value(node["value"])
            action = "ctx.heal(amount);" if op == "heal" else "if (!ctx.lightning(amount)) return false;"
            maximum = 20 if op == "heal" else 32
            body = f"int amount = {amount}; if (amount < 1 || amount > {maximum}) return false; {action} pc = {ids[node['next']]};"
        else:
            body = f"return {'true' if node['success'] else 'false'};"
        lines.append(f"                case {ids[node['id']]} -> {{ {body} }}")
    declarations = [f"        {('int' if v['type'] == 'int' else 'boolean')} v{i} = {str(v['initial']).lower()};"
                    for i, v in enumerate(graph["variables"])]
    declarations += [f"        int c{ids[n['id']]} = 0;" for n in nodes if n["op"] == "repeat"]
    budget = len(nodes) * (33 if any(n["op"] == "repeat" for n in nodes) else 1)
    return (
        "".join(helper_methods)
        + f"    static boolean run{index}(Context ctx) {{\\n"
        + "\\n".join(declarations) + "\\n"
        + f"        int pc = {ids[graph['entry']]};\\n"
        + f"        for (int step = 0; step < {budget}; step++) {{\\n"
        + "            switch (pc) {\\n" + "\\n".join(lines)
        + "\\n                default -> { return false; }\\n"
        + "            }\\n        }\\n        return false;\\n    }\\n"
    )

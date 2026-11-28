from __future__ import annotations

import unittest

from creature_studio.behavior_graph import compile_java_method, simulate, validate_graph


def simple_graph():
    return {
        "version": 1, "entry": "event", "variables": [{"id": "power", "name": "Power", "type": "int", "initial": 2}],
        "nodes": [
            {"id": "event", "op": "event", "event": "use", "next": "add", "x": 0, "y": 0},
            {"id": "add", "op": "add", "variable": "power", "value": {"source": "literal", "type": "int", "value": 3}, "next": "end", "x": 1, "y": 0},
            {"id": "end", "op": "end", "success": True, "x": 2, "y": 0},
        ],
    }


class BehaviorGraphTests(unittest.TestCase):
    def test_validates_and_simulates_typed_graph(self):
        graph = simple_graph()
        self.assertEqual(validate_graph(graph), [])
        result = simulate(graph)
        self.assertTrue(result["success"])
        self.assertEqual(result["variables"]["power"], 5)
        self.assertEqual(result["trace"], ["event", "add", "end"])

    def test_compiles_deterministic_java_method(self):
        source = compile_java_method(simple_graph(), 0)
        self.assertIn("static boolean run0", source)
        self.assertIn("clamp((long) v0 + 3)", source)

    def test_rejects_unreachable_nodes_and_cycles(self):
        graph = simple_graph()
        graph["nodes"].append({"id": "orphan", "op": "end", "success": True, "x": 3, "y": 0})
        self.assertTrue(any("unreachable" in error for error in validate_graph(graph)))

    def test_rejects_invalid_division_by_zero(self):
        graph = simple_graph()
        graph["nodes"][1]["op"] = "divide"
        graph["nodes"][1]["value"]["value"] = 0
        self.assertTrue(any("division by zero" in error for error in validate_graph(graph)))


    def test_integer_add_with_zero_does_not_trigger_division(self):
        graph = simple_graph()
        graph["nodes"][1]["value"]["value"] = 0
        self.assertEqual(simulate(graph)["variables"]["power"], 2)

    def test_v3_function_library_validates_simulates_and_compiles(self):
        graph = {
            "version": 3,
            "entry": "event",
            "variables": [{"id": "result", "name": "Result", "type": "int", "initial": 0}],
            "functions": [{
                "id": "double",
                "params": [{"id": "x", "type": "int"}],
                "returns": "int",
                "body": {
                    "op": "multiply",
                    "a": {"op": "param", "id": "x"},
                    "b": {"op": "literal", "type": "int", "value": 2},
                },
            }],
            "nodes": [
                {"id": "event", "op": "event", "event": "use", "next": "call", "x": 0, "y": 0},
                {"id": "call", "op": "call", "fn": "double", "args": [
                    {"source": "literal", "type": "int", "value": 4}
                ], "variable": "result", "next": "end", "x": 1, "y": 0},
                {"id": "end", "op": "end", "success": True, "x": 2, "y": 0},
            ],
        }
        self.assertEqual(validate_graph(graph), [])
        self.assertEqual(simulate(graph)["variables"]["result"], 8)
        source = compile_java_method(graph, 2)
        self.assertIn("fn2_0(4)", source)
        self.assertIn("private static int fn2_0", source)


if __name__ == "__main__":
    unittest.main()

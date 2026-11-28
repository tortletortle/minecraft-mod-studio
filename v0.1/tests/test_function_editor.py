from __future__ import annotations

import unittest

from creature_studio.function_editor import available, commit, kind, make, slots, type_of


class FunctionEditorTests(unittest.TestCase):
    def setUp(self):
        self.function = {"id": "outer", "params": [{"id": "amount", "type": "int"}], "returns": "int"}
        self.library = [
            self.function,
            {"id": "double", "params": [{"id": "value", "type": "int"}], "returns": "int"},
        ]

    def test_available_and_make_exclude_recursive_self_call(self):
        choices = available(self.function, self.library, "int")
        self.assertIn("call", choices)
        self.assertEqual(make("call", "int", self.function, self.library)["fn"], "double")
        self.assertEqual(make("param", "int", self.function, self.library)["id"], "amount")

    def test_expression_types_kinds_and_slots(self):
        expression = {"op": "eq", "a": {"op": "literal", "type": "bool", "value": True},
                      "b": {"op": "literal", "type": "bool", "value": False}}
        self.assertEqual(type_of(expression, self.function, self.library), "bool")
        self.assertEqual(kind(expression, self.function, self.library), "eq_bool")
        self.assertEqual(slots(expression, "bool", self.function, self.library)[0][2], "bool")

    def test_division_editor_starts_with_nonzero_denominator(self):
        expression = make("divide", "int", self.function, self.library)
        self.assertEqual(expression["b"]["value"], 1)

    def test_call_slots_follow_function_parameter_types(self):
        expression = {"op": "call", "fn": "double", "args": [{"op": "literal", "type": "int", "value": 0}]}
        self.assertEqual(slots(expression, "int", self.function, self.library)[0][1:], ("value", "int"))

    def test_commit_delegates_reference_signature_protection(self):
        result = commit({"version": 1, "entry": "event", "variables": [], "nodes": [
            {"id": "event", "op": "event", "event": "use", "next": "end", "x": 0, "y": 0},
            {"id": "end", "op": "end", "success": True, "x": 1, "y": 0},
        ]}, [{"id": "double", "params": [], "returns": "int",
              "body": {"op": "literal", "type": "int", "value": 2}}])
        self.assertEqual(result["errors"], [])


if __name__ == "__main__":
    unittest.main()

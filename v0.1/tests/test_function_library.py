from __future__ import annotations

import json
import unittest

from creature_studio.function_library import FunctionPackError, commit_library, import_pack, pack, references


FUNCTION = {
    "id": "double",
    "params": [{"id": "x", "type": "int"}],
    "returns": "int",
    "body": {
        "op": "multiply",
        "a": {"op": "param", "id": "x"},
        "b": {"op": "literal", "type": "int", "value": 2},
    },
}


class FunctionLibraryTests(unittest.TestCase):
    def test_pack_is_canonical_and_roundtrips(self):
        packed = pack([FUNCTION])
        self.assertEqual(json.loads(packed)["functions"], [FUNCTION])
        result = import_pack({"version": 1, "entry": "event", "variables": [], "nodes": [\n            {"id": "event", "op": "event", "event": "use", "next": "end", "x": 0, "y": 0},\n            {"id": "end", "op": "end", "success": True, "x": 1, "y": 0},\n        ]}, [], packed)
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["added"], 1)

    def test_import_is_atomic_on_conflicting_function_id(self):
        conflict = {**FUNCTION, "body": {"op": "literal", "type": "int", "value": 9}}
        packed = pack([conflict])
        result = import_pack({"version": 1, "entry": "event", "variables": [], "nodes": []}, [FUNCTION], packed)
        self.assertTrue(any("Conflicting function ID" in error for error in result["errors"]))

    def test_referenced_function_signature_cannot_be_changed(self):
        graph = {
            "version": 3, "entry": "event", "variables": [{"id": "result", "name": "Result", "type": "int", "initial": 0}],
            "functions": [FUNCTION],
            "nodes": [
                {"id": "event", "op": "event", "event": "use", "next": "call", "x": 0, "y": 0},
                {"id": "call", "op": "call", "fn": "double", "args": [{"source": "literal", "type": "int", "value": 1}], "variable": "result", "next": "end", "x": 1, "y": 0},
                {"id": "end", "op": "end", "success": True, "x": 2, "y": 0},
            ],
        }
        changed = [{**FUNCTION, "params": [{"id": "other", "type": "int"}]}]
        result = commit_library(graph, changed)
        self.assertTrue(any("signature changed" in error for error in result["errors"]))

    def test_nested_function_references_are_collected(self):
        nested = {**FUNCTION, "id": "outer", "body": {"op": "call", "fn": "double", "args": [{"op": "param", "id": "x"}]}}
        self.assertEqual(references([FUNCTION, nested], []), {"double"})


if __name__ == "__main__":
    unittest.main()

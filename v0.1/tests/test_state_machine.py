from __future__ import annotations

import unittest

from creature_studio.state_machine import choose, defaults, normalize, validate


class StateMachineTests(unittest.TestCase):
    def setUp(self):
        self.mob = {"model": {"animations": [
            {"id": "idle", "loop": True}, {"id": "walk", "loop": True},
            {"id": "attack", "loop": False}, {"id": "death", "loop": False},
        ]}}

    def test_defaults_and_validation(self):
        machine = defaults(self.mob)
        self.assertTrue(machine["enabled"])
        self.assertEqual(validate(machine, self.mob), [])

    def test_normalize_inherits_animation_loop_setting(self):
        machine = {"enabled": True, "initial": "idle",
                   "states": [{"id": "attack", "animation": "attack", "loop": True}],
                   "transitions": []}
        normalized = normalize(machine, self.mob)
        self.assertFalse(normalized["states"][0]["loop"])

    def test_choose_uses_highest_priority_then_stable_id(self):
        machine = {"transitions": [
            {"id": "z", "from": "*", "to": "attack", "condition": "always", "priority": 20},
            {"id": "a", "from": "*", "to": "walk", "condition": "always", "priority": 20},
        ]}
        self.assertEqual(choose(machine, {}, "idle")["id"], "a")

    def test_choose_obeys_cooldown_and_current_state(self):
        machine = {"transitions": [
            {"id": "attack", "from": "idle", "to": "attack", "condition": "has_target", "priority": 90},
            {"id": "walk", "from": "idle", "to": "walk", "condition": "always", "priority": 10},
        ]}
        self.assertEqual(choose(machine, {"hasTarget": True}, "idle", {"attack": 1})["id"], "walk")

    def test_rejects_duplicate_transition_and_missing_animation(self):
        machine = {"enabled": True, "initial": "idle",
                   "states": [{"id": "idle", "animation": "missing", "loop": True}],
                   "transitions": []}
        errors = validate(machine, self.mob)
        self.assertTrue(any("missing animation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()

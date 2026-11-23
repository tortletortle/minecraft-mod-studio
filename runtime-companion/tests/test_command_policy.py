import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from command_policy import build_command_plan, classify_command, normalize_command


def validation(command, valid=True, error_code=""):
    return {
        "command": normalize_command(command),
        "syntax_only": True,
        "execution_enabled": False,
        "valid": valid,
        "error_code": error_code,
    }


class CommandPolicyTests(unittest.TestCase):
    def test_explicit_read_only_allowlist(self):
        for command in (
            "help", "list", "locate structure minecraft:village", "seed",
            "time query daytime", "data get entity @s Pos",
            "attribute @s minecraft:generic.max_health get",
            "scoreboard players get @s objective", "team list", "bossbar list",
        ):
            with self.subTest(command=command):
                self.assertEqual(classify_command(command)["risk"], "read_only")

    def test_mutations_never_become_read_only(self):
        for command in (
            "setblock ~ ~ ~ stone", "fill ~ ~ ~ ~10 ~10 ~10 stone", "clone 0 0 0 10 10 10 20 0 0",
            "summon minecraft:zombie", "kill @e[type=minecraft:zombie]", "give @s minecraft:diamond",
            "time set day", "weather clear", "gamerule keepInventory true",
            "data modify entity @s Health set value 20", "attribute @s minecraft:generic.max_health base set 40",
        ):
            with self.subTest(command=command):
                self.assertNotEqual(classify_command(command)["risk"], "read_only")

    def test_delegating_and_unknown_commands_default_deny(self):
        for command in ("execute as @e run kill @s", "function example:destructive", "mymod:unknown_action run"):
            with self.subTest(command=command):
                policy = classify_command(command)
                self.assertEqual(policy["risk"], "unknown")
                self.assertEqual(policy["category"], "unknown")

    def test_command_normalization_and_control_character_rejection(self):
        self.assertEqual(normalize_command("  /time query daytime  "), "time query daytime")
        for command in ("", "   ", "fill stone\nkill @e", "say\x00x", "x" * 513):
            with self.subTest(command=repr(command)):
                with self.assertRaises(ValueError):
                    normalize_command(command)

    def test_plan_is_deterministic_and_never_executable(self):
        commands = ["time query daytime", "setblock ~ ~ ~ stone"]
        validations = [validation(command) for command in commands]
        first = build_command_plan(commands, validations)
        second = build_command_plan(commands, validations)
        self.assertEqual(first["plan_id"], second["plan_id"])
        self.assertEqual(first["overall_status"], "operator_review_required")
        self.assertFalse(first["execution_enabled"])
        self.assertEqual(first["commands_executed"], 0)
        self.assertEqual([step["decision"] for step in first["steps"]], ["preview_only", "operator_review_required"])
        self.assertTrue(all(step["execution_allowed"] is False for step in first["steps"]))

    def test_unknown_mod_command_is_blocked_even_with_syntax_valid(self):
        command = "examplemod:spawn_magic_beast"
        plan = build_command_plan([command], [validation(command)])
        self.assertEqual(plan["overall_status"], "blocked_unknown")
        self.assertEqual(plan["steps"][0]["decision"], "blocked_by_default")
        self.assertFalse(plan["manifest_risk_labels_used_for_authorization"])

    def test_invalid_syntax_blocks_whole_plan(self):
        command = "fill ~ ~ ~"
        plan = build_command_plan([command], [validation(command, valid=False, error_code="COMMAND_SYNTAX_INVALID")])
        self.assertEqual(plan["overall_status"], "invalid")
        self.assertEqual(plan["steps"][0]["decision"], "syntax_invalid")

    def test_plan_bounds_and_validation_echo(self):
        with self.assertRaisesRegex(ValueError, "PLAN_STEP_COUNT_OUT_OF_RANGE"):
            build_command_plan([], [])
        with self.assertRaisesRegex(ValueError, "PLAN_STEP_COUNT_OUT_OF_RANGE"):
            build_command_plan(["help"] * 9, [validation("help")] * 9)
        with self.assertRaisesRegex(ValueError, "COMMAND_VALIDATION_ECHO_MISMATCH"):
            build_command_plan(["help"], [validation("list")])


if __name__ == "__main__":
    unittest.main()

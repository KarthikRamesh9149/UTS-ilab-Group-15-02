import unittest

from scripts.custom_harness import QwenCustomHarness


class CustomHarnessTests(unittest.TestCase):
    def test_parses_plain_json_action(self):
        action = QwenCustomHarness.parse_action('{"analysis":"inspect","phase":"inspect","command":"ls","done":false}')
        self.assertEqual(action["command"], "ls")
        self.assertEqual(action["phase"], "inspect")
        self.assertFalse(action["done"])

    def test_parses_fenced_json_action(self):
        action = QwenCustomHarness.parse_action('```json\n{"analysis":"ok","command":"","done":true}\n```')
        self.assertTrue(action["done"])

    def test_rejects_missing_json(self):
        with self.assertRaises(ValueError):
            QwenCustomHarness.parse_action("run ls")

    def test_output_clipping_preserves_head_and_tail(self):
        clipped = QwenCustomHarness._clip("a" * 4000 + "z" * 4000, 1000)
        self.assertIn("output truncated", clipped)
        self.assertTrue(clipped.startswith("a" * 100))
        self.assertTrue(clipped.endswith("z" * 100))

    def test_safety_guard_allows_normal_build_commands(self):
        allowed, reason = QwenCustomHarness.command_is_safe("python -m py_compile /app/solution.py")
        self.assertTrue(allowed)
        self.assertEqual(reason, "")

    def test_safety_guard_rejects_broad_deletion(self):
        allowed, reason = QwenCustomHarness.command_is_safe("rm -rf / --no-preserve-root")
        self.assertFalse(allowed)
        self.assertIn("deletion", reason)

    def test_extracts_explicit_requested_artifact(self):
        paths = QwenCustomHarness.requested_artifacts("Create /app/pipeline_parallel.py and implement it.")
        self.assertEqual(paths, ["/app/pipeline_parallel.py"])

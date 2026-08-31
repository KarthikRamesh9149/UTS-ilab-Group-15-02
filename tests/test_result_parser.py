import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_results import is_infrastructure_error, parse_trial


class ResultParserTests(unittest.TestCase):
    def fixture(self, reward=1, tokens=True, exception=None):
        return {
            "id": "fixture-id", "task_name": "terminal-bench/example-task",
            "started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:10Z",
            "agent_info": {"name": "mini-swe-agent", "version": "1.0", "model_info": {"name": "openai/qwen2.5-coder:3b"}},
            "agent_result": ({"n_input_tokens": 10, "n_output_tokens": 5} if tokens else {}),
            "verifier_result": {"rewards": {"reward": reward}}, "exception_info": exception,
            "agent_execution": {"started_at": "2026-01-01T00:00:01Z"},
        }

    def write(self, data, root):
        path = root / "job/trial/result.json"; path.parent.mkdir(parents=True); path.write_text(json.dumps(data)); return path

    def test_pass_and_fail_come_from_reward(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertTrue(parse_trial(self.write(self.fixture(1), root))["pass"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(parse_trial(self.write(self.fixture(0), root))["pass"])

    def test_missing_tokens_stay_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            row = parse_trial(self.write(self.fixture(tokens=False), Path(tmp)))
            self.assertEqual(row["prompt_tokens"], "")
            self.assertEqual(row["total_tokens"], "")

    def test_infrastructure_error_is_identified(self):
        data = self.fixture(exception={"exception_type": "RuntimeError", "exception_message": "Docker compose failed to connect"})
        data["verifier_result"] = None; data["agent_execution"] = None
        self.assertTrue(is_infrastructure_error(data))

    def test_timed_out_message_is_recorded_as_timeout(self):
        data = self.fixture(exception={"exception_type": "RuntimeError", "exception_message": "Command timed out after 120 seconds"})
        data["verifier_result"] = None
        with tempfile.TemporaryDirectory() as tmp:
            row = parse_trial(self.write(data, Path(tmp)))
            self.assertTrue(row["timeout"])
            self.assertFalse(row["infrastructure_error"])


if __name__ == "__main__":
    unittest.main()

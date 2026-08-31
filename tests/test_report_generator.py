import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from generate_progress_report import summarize


class ReportGeneratorTests(unittest.TestCase):
    def test_summary_counts_valid_pass_fail_and_infra(self):
        rows = [
            {"model_name": "qwen2.5-coder:3b", "harness": "mini-swe-agent", "valid_trial": "True", "pass": "True", "infrastructure_error": "False", "duration_seconds": "10"},
            {"model_name": "qwen2.5-coder:3b", "harness": "mini-swe-agent", "valid_trial": "True", "pass": "False", "infrastructure_error": "False", "duration_seconds": "20"},
            {"model_name": "qwen2.5-coder:3b", "harness": "mini-swe-agent", "valid_trial": "False", "pass": "", "infrastructure_error": "True", "duration_seconds": ""},
        ]
        result = summarize(rows)["qwen2.5-coder:3b | mini-swe-agent"]
        self.assertEqual(result["valid_trials"], 2)
        self.assertEqual(result["passed"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["infrastructure_errors"], 1)
        self.assertEqual(result["mean_runtime_seconds"], 15)


if __name__ == "__main__":
    unittest.main()

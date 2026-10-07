"""Tests of real committed outcomes and recovery evidence accounting."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("report_results", ROOT / "scripts/report_results.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


class ResultTests(unittest.TestCase):
    def setUp(self):
        self.original = report.read_rows(ROOT / "results/custom/trials.csv")
        self.recovery = report.read_rows(ROOT / "results/custom/recovery/trials.csv")

    def test_saved_scores_and_attempt_counts(self):
        summary = report.build_summary()
        self.assertEqual([(r["passed"], r["verified_failures"], r["missing_outcomes"])
                          for r in summary["baselines"]], [(52, 37, 0), (44, 45, 0)])
        original = summary["custom_original"]
        self.assertEqual((original["tasks"], original["passed"], original["verified_failures"],
                          original["missing_outcomes"]), (89, 50, 36, 3))
        combined = summary["custom_recovery_inclusive"]
        self.assertEqual((combined["tasks"], combined["attempts"], combined["passed"],
                          combined["verified_failures"], combined["missing_outcomes"]), (89, 92, 50, 39, 0))

    def test_development_splits(self):
        summary = report.build_summary()
        self.assertEqual([(r["development_passed"], r["remaining_passed"])
                          for r in summary["baselines"]], [(14, 38), (10, 34)])
        self.assertEqual((summary["custom_original"]["development_passed"],
                          summary["custom_original"]["remaining_passed"]), (15, 35))

    def test_summary_is_reproducible(self):
        self.assertEqual(report.build_summary(), json.loads((ROOT / "results/summary.json").read_text()))

    def test_join_does_not_modify_original_records(self):
        before = copy.deepcopy(self.original)
        report.join_recovery(self.original, self.recovery)
        self.assertEqual(self.original, before)

    def test_mismatched_original_identity_is_refused(self):
        changed = copy.deepcopy(self.recovery)
        changed[0]["original_trial_id"] = "different-attempt"
        with self.assertRaises(ValueError):
            report.join_recovery(self.original, changed)

    def test_mismatched_evidence_hash_is_refused(self):
        changed = copy.deepcopy(self.recovery)
        changed[0]["original_result_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            report.join_recovery(self.original, changed)

    def test_verified_outcome_cannot_be_replaced(self):
        changed = copy.deepcopy(self.original)
        changed[62]["reward"] = "0"
        with self.assertRaises(ValueError):
            report.join_recovery(changed, self.recovery)

    def test_duplicate_recovery_is_refused(self):
        with self.assertRaises(ValueError):
            report.join_recovery(self.original, self.recovery + self.recovery[:1])

    def test_nonbinary_rewards_are_refused(self):
        for value in ("nan", "Infinity", "0.5", "garbage"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                report.reward({"reward": value})


if __name__ == "__main__":
    unittest.main()

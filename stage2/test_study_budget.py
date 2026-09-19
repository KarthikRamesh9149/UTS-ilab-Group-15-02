from decimal import Decimal
import json
from pathlib import Path
import unittest

from study_budget import TRIAL_CAP, SCORED_CEILING, STAGE_CAPS, SETUP_CAP, ACCOUNT_RESERVE


class StudyBudgetTests(unittest.TestCase):
    def test_full_planned_matrix_and_setup_fit_remaining_credit(self):
        self.assertEqual(Decimal(TRIAL_CAP)*120, Decimal(STAGE_CAPS['development']))
        self.assertEqual(Decimal(TRIAL_CAP)*267, Decimal(STAGE_CAPS['final']))
        self.assertEqual(sum(map(Decimal, STAGE_CAPS.values())), Decimal(SCORED_CEILING))
        self.assertLess(Decimal(SCORED_CEILING)+Decimal(SETUP_CAP)+Decimal(ACCOUNT_RESERVE), Decimal('12.031657772'))

    def test_written_policy_matches_runtime(self):
        policy = json.loads(Path(__file__).with_name('budget_policy.json').read_text())
        self.assertEqual(Decimal(policy['per_trial_cap_all_harnesses']), Decimal(TRIAL_CAP))
        self.assertEqual(Decimal(policy['development_maximum']), Decimal(STAGE_CAPS['development']))
        self.assertEqual(Decimal(policy['final_maximum']), Decimal(STAGE_CAPS['final']))
        self.assertEqual(Decimal(policy['core_maximum']), Decimal(SCORED_CEILING)+Decimal(SETUP_CAP))

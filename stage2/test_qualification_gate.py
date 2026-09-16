import copy
import unittest
from qualification_gate import evaluate


class QualificationGateTests(unittest.TestCase):
    def setUp(self):
        self.tasks = ['synthetic-' + str(i) for i in range(20)]
        self.fingerprint = 'a' * 64
        self.rows = [{'task_id': task, 'harness': 'terminus-2', 'stage': 'development',
            'model_protocol_sha256': self.fingerprint, 'status': 'verified', 'model_revoked': True,
            'containers_removed': True, 'networks_removed': True, 'volumes_removed': True,
            'verifier_result': {'rewards': {'reward': int(i < 10)}},
            'billing': {'billing_verified': True, 'model_protocol_sha256': self.fingerprint,
                'budget_stop_count': int(i < 2), 'requests': 2, 'prompt_tokens': 100,
                'completion_tokens': 50, 'charged_usd': '.002'}} for i, task in enumerate(self.tasks)]

    def evaluate(self, rows=None, reviewed=True):
        return evaluate(self.rows if rows is None else rows, task_ids=self.tasks,
                        protocol_sha256=self.fingerprint, systemic_review_clear=reviewed)

    def test_exact_threshold_and_no_mutation(self):
        before = copy.deepcopy(self.rows)
        result = self.evaluate()
        self.assertTrue(result['paid_expansion_allowed'])
        self.assertEqual(result['verified_successes'], 10)
        self.assertEqual(result['budget_exhausted_trials'], 2)
        self.assertEqual(before, self.rows)

    def test_nine_successes_do_not_pass(self):
        self.rows[0]['verifier_result']['rewards']['reward'] = 0
        self.assertIn('fewer_than_ten_successes', self.evaluate()['reasons'])

    def test_three_exhausted_trials_do_not_pass(self):
        self.rows[3]['billing']['budget_stop_count'] = 5
        self.assertEqual(self.evaluate()['budget_exhausted_trials'], 3)
        self.assertFalse(self.evaluate()['paid_expansion_allowed'])

    def test_missing_duplicate_and_wrong_condition_fail(self):
        self.assertFalse(self.evaluate(self.rows[:-1])['paid_expansion_allowed'])
        self.rows[-1] = copy.deepcopy(self.rows[0])
        self.assertFalse(self.evaluate()['paid_expansion_allowed'])
        self.rows[0]['harness'] = 'openhands'
        self.assertIn('wrong_condition', self.evaluate()['reasons'])

    def test_review_is_required_even_with_passes(self):
        self.assertIn('systemic_failure_review_required', self.evaluate(reviewed=False)['reasons'])

    def test_unknown_billing_usage_or_cleanup_never_pass(self):
        for field, value in [('prompt_tokens', None), ('billing_verified', False),
                             ('budget_stop_count', None), ('charged_usd', 'NaN')]:
            rows = copy.deepcopy(self.rows)
            rows[0]['billing'][field] = value
            with self.subTest(field=field):
                self.assertFalse(self.evaluate(rows)['paid_expansion_allowed'])
        self.rows[0]['containers_removed'] = False
        self.assertFalse(self.evaluate()['paid_expansion_allowed'])

    def test_reward_booleans_and_protocol_drift_rejected(self):
        self.rows[0]['verifier_result']['rewards']['reward'] = True
        self.rows[1]['model_protocol_sha256'] = 'b' * 64
        result = self.evaluate()
        self.assertIn('invalid_verifier_reward', result['reasons'])
        self.assertIn('model_protocol_mismatch', result['reasons'])

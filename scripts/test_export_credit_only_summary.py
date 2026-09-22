import json
from pathlib import Path
import tempfile
import unittest

from export_credit_only_summary import audit_trial, condition, error_name, safe_task_id


class CreditOnlyExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = Path(self.temp.name)
        self.cell = dict(trial_id='trial', task_id='example', harness='terminus-2')
        self.folder = self.runtime / 'scored-trials/trial'
        self.folder.mkdir(parents=True)
        self.calls = self.runtime / 'scored-attempts/trial'
        self.calls.mkdir(parents=True)
        self.result = dict(self.cell, status='verified', containers_removed=True, networks_removed=True,
            volumes_removed=True, verifier_result={'rewards': {'reward': 0}},
            billing=dict(accounting_mode='provider-credit-only', requests=1, unknown_cost_requests=1,
                known_charged_usd='0', charged_usd=None, costs_complete=False,
                known_prompt_tokens=0, known_completion_tokens=0, prompt_tokens=None, completion_tokens=None))
        self.write_result()
        (self.calls / '000001.request.json').write_text(json.dumps({'private_prompt': 'DO NOT EXPORT'}))
        (self.calls / '000001.outcome.json').write_text(json.dumps(dict(trial_id='trial', status='error', cost_usd=None)))
        (self.calls / '000001.transport-error.json').write_text(json.dumps({'http_status': 429}))

    def write_result(self):
        (self.folder / 'result.json').write_text(json.dumps(self.result))

    def test_zero_reward_and_unknown_cost_are_preserved(self):
        row = audit_trial(self.runtime, self.cell)
        self.assertEqual(row['reward'], 0)
        self.assertEqual(row['known_cost_usd'], '0')
        self.assertIsNone(row['total_cost_usd'])
        self.assertEqual(row['http_429_requests'], 1)
        self.assertNotIn('DO NOT EXPORT', json.dumps(row))
        self.assertIsNone(condition([row])['total_cost_usd'])
        self.assertIsNone(row['prompt_tokens'])
        self.assertIsNone(condition([row])['completion_tokens'])

    def test_missing_outcome_is_not_completed(self):
        (self.calls / '000001.outcome.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Unpaired'):
            audit_trial(self.runtime, self.cell)

    def test_unknown_cost_cannot_be_reported_as_zero_total(self):
        self.result['billing']['charged_usd'] = '0'
        self.write_result()
        with self.assertRaisesRegex(ValueError, 'Unknown charge'):
            audit_trial(self.runtime, self.cell)

    def test_bad_cleanup_fails_closed(self):
        self.result['containers_removed'] = False
        self.write_result()
        with self.assertRaisesRegex(ValueError, 'cleanup'):
            audit_trial(self.runtime, self.cell)

    def test_boolean_reward_is_not_a_score(self):
        self.result['verifier_result']['rewards']['reward'] = True
        self.write_result()
        with self.assertRaisesRegex(ValueError, 'verifier'):
            audit_trial(self.runtime, self.cell)

    def test_identity_mismatch_rejected(self):
        self.result['harness'] = 'openhands'
        self.write_result()
        with self.assertRaisesRegex(ValueError, 'identity'):
            audit_trial(self.runtime, self.cell)

    def test_error_prose_cannot_leak_into_export(self):
        with self.assertRaisesRegex(ValueError, 'exception class'):
            error_name('request failed: secret=value')

    def test_official_versioned_task_identifier_is_allowed(self):
        self.assertTrue(safe_task_id('install-windows-3.11'))
        self.assertFalse(safe_task_id('../escape'))
        self.assertFalse(safe_task_id('=formula'))


if __name__ == '__main__':
    unittest.main()

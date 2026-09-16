import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from matrix_resume import completed_cell
from model_protocol import ModelSettings


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = ModelSettings(64, 1., 'high')
        self.cell = dict(trial_id='final-custom-00-task', task_id='task', stage='final', harness='C2', parent='C1')
        self.path = self.root / '.runtime/stage2/scored-trials' / self.cell['trial_id'] / 'result.json'
        self.row = dict(self.cell, status='verified', model_protocol_sha256=self.settings.fingerprint(),
            model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
            verifier_result={'rewards': {'reward': 0}}, agent_context={'metadata': {'custom_parent': 'C1'}})
        self.billing = {'billing_verified': True, 'model_protocol_sha256': self.settings.fingerprint()}

    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.row))

    def test_missing_cell_does_not_call_billing(self):
        with patch('matrix_resume.audit_trial') as audit:
            self.assertIsNone(completed_cell(self.root, self.cell, self.settings))
            audit.assert_not_called()

    def test_zero_result_retained_and_reaudited(self):
        self.write()
        with patch('matrix_resume.audit_trial', return_value=self.billing) as audit:
            result = completed_cell(self.root, self.cell, self.settings)
            self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
            audit.assert_called_once()

    def test_existing_interrupted_attempt_blocks(self):
        self.path.parent.mkdir(parents=True)
        with self.assertRaises(RuntimeError): completed_cell(self.root, self.cell, self.settings)

    def test_identity_and_parent_mismatch_rejected(self):
        for key in ('task_id', 'harness', 'model_protocol_sha256'):
            original = self.row[key]
            self.row[key] = 'wrong'
            self.write()
            with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)
            self.row[key] = original
        self.row['agent_context']['metadata']['custom_parent'] = 'C0'
        self.write()
        with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)

    def test_invalid_reward_and_cleanup_rejected(self):
        self.row['verifier_result']['rewards']['reward'] = True
        self.write()
        with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)
        self.row['verifier_result']['rewards']['reward'] = 0
        self.row['containers_removed'] = False
        self.write()
        with self.assertRaises(RuntimeError): completed_cell(self.root, self.cell, self.settings)

    def test_billing_failure_blocks_resume(self):
        self.write()
        with patch('matrix_resume.audit_trial', side_effect=ValueError('unresolved')):
            with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)

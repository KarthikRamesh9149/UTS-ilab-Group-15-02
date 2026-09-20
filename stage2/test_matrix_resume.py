import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from historical_hold import canonical_hold_document
from matrix_resume import completed_cell, validated_held_cell, HELD_TERMINAL
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

    def install_hold(self):
        hold = canonical_hold_document()
        hold.update(model_protocol_sha256=self.settings.fingerprint(), sidecar_sha256='c' * 64,
            budget_stop_count=2, budget_stop_classification='historical_pending_barrier',
            capacity_budget_stop_count=0)
        self.cell = {key: hold[key] for key in ('trial_id', 'task_id', 'stage', 'harness')}
        self.row.update(self.cell, status='billing_unresolved', billing={'billing_verified': False})
        self.row.pop('parent', None)
        self.path = self.root / '.runtime/stage2/scored-trials' / self.cell['trial_id'] / 'result.json'
        self.write()
        hold['original_result_sha256'] = hashlib.sha256(self.path.read_bytes()).hexdigest()
        validator = patch('matrix_resume.validate_historical_hold', return_value=hold)
        validator.start()
        self.addCleanup(validator.stop)
        return hold

    def test_historical_zero_has_terminal_disposition_without_billing_imputation(self):
        self.install_hold()
        before = self.path.read_bytes()
        with patch('matrix_resume.audit_trial') as audit:
            row = completed_cell(self.root, self.cell, self.settings)
            audit.assert_not_called()
        self.assertEqual(row['resume_disposition'], HELD_TERMINAL)
        self.assertEqual(row['status'], 'billing_unresolved')
        self.assertEqual(row['verifier_result']['rewards']['reward'], 0)
        self.assertIs(row['billing']['billing_verified'], False)
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.assertIsNone(row['billing'][field])
        self.assertEqual(row['billing']['budget_stop_count'], 2)
        self.assertEqual(row['billing']['capacity_budget_stop_count'], 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNotNone(validated_held_cell(self.root / '.runtime/stage2', row, self.settings.fingerprint()))

    def test_historical_view_rejects_imputed_usage_or_modified_outcome(self):
        self.install_hold()
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            row = completed_cell(self.root, self.cell, self.settings)
            row['billing'][field] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                validated_held_cell(self.root / '.runtime/stage2', row, self.settings.fingerprint())
        row = completed_cell(self.root, self.cell, self.settings)
        row['verifier_result']['rewards']['reward'] = 1
        with self.assertRaises(ValueError):
            validated_held_cell(self.root / '.runtime/stage2', row, self.settings.fingerprint())

    def test_historical_cell_cannot_be_replayed_with_substitute_identity(self):
        self.install_hold()
        substitute = dict(self.cell, trial_id=self.cell['trial_id'] + '-replacement')
        with self.assertRaisesRegex(ValueError, 'substitute'):
            completed_cell(self.root, substitute, self.settings)
        self.path.unlink()
        self.path.parent.rmdir()
        with self.assertRaisesRegex(ValueError, 'replay forbidden'):
            completed_cell(self.root, self.cell, self.settings)

    def test_hold_does_not_accept_another_unresolved_trial(self):
        self.install_hold()
        self.cell = dict(self.cell, trial_id='dev-terminus-2-01-other', task_id='other')
        self.row.update(self.cell)
        self.path = self.root / '.runtime/stage2/scored-trials' / self.cell['trial_id'] / 'result.json'
        self.write()
        with self.assertRaises(RuntimeError):
            completed_cell(self.root, self.cell, self.settings)

    def test_invalid_historical_evidence_blocks_even_missing_future_cell(self):
        with patch('matrix_resume.validate_historical_hold', side_effect=ValueError('Another unresolved dispatch')):
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                completed_cell(self.root, self.cell, self.settings)

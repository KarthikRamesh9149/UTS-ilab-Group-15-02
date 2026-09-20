import fcntl
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budget_ledger import BudgetExceeded, Ledger
from gateway_policy import MODEL
from model_protocol import ModelSettings, freeze_protocol
from post_trial_receipts import collect_receipts
from scored_gateway import durable_json, private_directory
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS
from verify_retained_receipts import verify_retained_receipts


class RetainedReceiptTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.runtime = private_directory(Path(self.temp.name) / 'runtime')
        self.trial = 'dev-terminus-2-05-example'
        attempts = private_directory(self.runtime / 'scored-attempts')
        self.evidence = private_directory(attempts / self.trial)
        self.database = self.runtime / 'scored_budget.sqlite'
        self.ledger = Ledger(self.database, SCORED_CEILING, TRIAL_CAP, STAGE_CAPS,
                             allow_estimated_trials=True)
        self.database.chmod(0o600)
        self.addCleanup(self.ledger.close)
        settings = ModelSettings(8192, 1.0, 'high')
        freeze_protocol(self.runtime, settings)
        durable_json(self.evidence / 'started.json', {'trial_id': self.trial,
            'stage': 'development', 'model_protocol_sha256': settings.fingerprint()})
        self.request_ids = ['request-' + str(i) for i in range(1, 6)]
        for i, identifier in enumerate(self.request_ids, 1):
            self.ledger.reserve(identifier, self.trial, '.106496', '12', 'development', trial_estimate='.001')
            self.ledger.attach_generation(identifier, 'gen-' + str(i))
            self.ledger.settle(identifier, '.001', receipt_pending=True)
            durable_json(self.evidence / f'{i:06}.response.json', {'id': 'gen-' + str(i),
                'model': MODEL, 'provider': 'DeepInfra', 'usage': {'cost': '.001', 'is_byok': False,
                                                              'prompt_tokens': 10, 'completion_tokens': 20}})
            durable_json(self.evidence / f'{i:06}.receipt.json', {'id': 'gen-' + str(i),
                'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.001',
                'native_tokens_prompt': 10, 'native_tokens_completion': 20,
                'tokens_prompt': 12, 'tokens_completion': 23, 'is_byok': False, 'cancelled': False})
        self.ledger.reserve('unknown', self.trial, '.106496', '12', 'development', trial_estimate='.001')

    def verify(self, **kwargs):
        return verify_retained_receipts(self.runtime, trial_id=kwargs.get('trial_id', self.trial),
                                       request_ids=kwargs.get('request_ids', self.request_ids))

    def snapshot(self):
        return {name: self.ledger.db.execute('SELECT * FROM ' + name + ' ORDER BY 1').fetchall()
                for name in ('requests', 'generations', 'receipt_checks', 'incidents', 'policy',
                             'stages', 'trial_stages', 'trial_estimates', 'estimation_policy')}

    def replace(self, filename, **updates):
        path = self.evidence / filename
        document = json.loads(path.read_text())
        document.update(updates)
        path.write_text(json.dumps(document))

    def test_only_named_receipt_flags_change_no_network_and_unknown_remains(self):
        before = self.snapshot()
        with patch('openrouter_transport.OpenRouter._request', side_effect=AssertionError('No network')):
            result = self.verify()
        after = self.snapshot()
        for table in before:
            if table != 'receipt_checks':
                self.assertEqual(before[table], after[table], table)
        self.assertEqual(after['receipt_checks'], [(identifier, 'verified') for identifier in self.request_ids])
        self.assertEqual(self.ledger.pending(), [('unknown', self.trial, 106496000, None)])
        self.assertEqual(result['network_calls'], 0)
        self.assertFalse(result['continuation_authorised'])
        self.assertEqual(len(result['receipts']), 5)
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('next', 'newtrial', '.106496', '12', 'development', trial_estimate='.001')
        with self.assertRaises((BudgetExceeded, ValueError)):
            collect_receipts(self.runtime, self.trial)

    def test_idempotent(self):
        self.verify()
        before = self.snapshot()
        result = self.verify()
        self.assertEqual(before, self.snapshot())
        self.assertTrue(all(row['previous_receipt_state'] == 'verified' for row in result['receipts']))

    def test_explicit_subset_does_not_verify_others(self):
        self.verify(request_ids=[self.request_ids[0]])
        self.assertEqual(len(self.ledger.pending_receipts()), 4)

    def test_invalid_selection_and_unknown_rejected_atomically(self):
        for identifiers in ([], ['request-1', 'request-1'], self.request_ids + ['unknown'],
                            self.request_ids + ['missing'], 'request-1', [None]):
            with self.subTest(identifiers=identifiers):
                before = self.snapshot()
                with self.assertRaises(ValueError): self.verify(request_ids=identifiers)
                self.assertEqual(before, self.snapshot())

    def test_missing_and_conflicting_receipts_never_partially_verify(self):
        path = self.evidence / '000005.receipt.json'
        original = path.read_bytes()
        for patch_value in ({'total_cost': '.002'}, {'provider_name': 'Other'}, {'id': 'wrong'}, {'model': 'wrong'}):
            path.write_bytes(original)
            self.replace(path.name, **patch_value)
            before = self.snapshot()
            with self.assertRaises(ValueError): self.verify()
            self.assertEqual(before, self.snapshot())
        path.unlink()
        with self.assertRaises(FileNotFoundError): self.verify()
        self.assertEqual(len(self.ledger.pending_receipts()), 5)

    def test_duplicate_response_rejected(self):
        duplicate = self.evidence / '999999.response.json'
        durable_json(duplicate, json.loads((self.evidence / '000001.response.json').read_text()))
        with self.assertRaises(ValueError): self.verify()

    def test_native_usage_and_billing_kind_must_match(self):
        path = self.evidence / '000005.receipt.json'
        original = path.read_bytes()
        for updates in ({'native_tokens_prompt': 11}, {'native_tokens_completion': None},
                        {'native_tokens_prompt': True}, {'cancelled': True}, {'is_byok': True}):
            with self.subTest(updates=updates):
                path.write_bytes(original)
                self.replace(path.name, **updates)
                before = self.snapshot()
                with self.assertRaises(ValueError): self.verify()
                self.assertEqual(before, self.snapshot())

    def test_length_finish_is_still_a_valid_billed_completion(self):
        self.replace('000005.response.json', choices=[{'finish_reason': 'length'}])
        self.assertEqual(len(self.verify()['receipts']), 5)

    def test_wrong_trial_or_protocol_rejected(self):
        self.replace('started.json', trial_id='another')
        with self.assertRaises(ValueError): self.verify()
        self.replace('started.json', trial_id=self.trial, model_protocol_sha256='0' * 64)
        with self.assertRaises(ValueError): self.verify()
        with self.assertRaises(ValueError): self.verify(trial_id='../escape')

    def test_missing_generation_and_receipt_check_rejected(self):
        self.ledger.db.execute("DELETE FROM generations WHERE request_id='request-5'")
        with self.assertRaises(ValueError): self.verify()
        self.ledger.attach_generation('request-5', 'gen-5')
        self.ledger.db.execute("DELETE FROM receipt_checks WHERE request_id='request-5'")
        with self.assertRaises(ValueError): self.verify()

    def test_symlinks_rejected(self):
        for path in (self.evidence / '000001.receipt.json', self.database, self.evidence):
            destination = path.with_name(path.name + '.saved')
            path.rename(destination)
            path.symlink_to(destination)
            try:
                with self.assertRaises(ValueError): self.verify()
            finally:
                path.unlink()
                destination.rename(path)

    def test_policy_drift_and_existing_incident_rejected(self):
        self.ledger.db.execute('UPDATE policy SET trial_cap=24000000')
        with self.assertRaises(ValueError): self.verify()
        self.ledger.db.execute('UPDATE policy SET trial_cap=23000000')
        self.ledger.record_receipt_incident('request-1', '.002')
        with self.assertRaises(ValueError): self.verify()

    def test_active_runner_lock_rejected(self):
        path = self.runtime / 'matrix.lock'
        path.touch(mode=0o600)
        with path.open('r+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.verify()

    def test_public_evidence_rejected(self):
        path = self.evidence / '000005.receipt.json'
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.verify()


if __name__ == '__main__':
    unittest.main()

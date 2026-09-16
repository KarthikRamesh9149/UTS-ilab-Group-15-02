import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from gateway_core import GatewayError
from gateway_policy import MODEL
from scored_accounting import audit_trial
from scored_gateway import ScoredSession
from test_scored_gateway import Client


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / '.runtime/stage2'
        self.client = Client()
        self.token = 'fixture-token-' * 4
        self.payload = {'model': MODEL, 'max_tokens': 64,
                        'messages': [{'role': 'user', 'content': 'synthetic'}]}

    def tearDown(self): self.temp.cleanup()

    def create(self, generate=True):
        with ScoredSession(self.root, 'test', 'development', self.token, self.client,
                           estimator=lambda request: '.01') as session:
            if generate: session.complete(self.token, self.payload)
        return self.runtime / 'scored-attempts/test'

    def test_exact_settled_cost_and_missing_token_metrics(self):
        self.create()
        result = audit_trial(self.runtime, 'test', 'development')
        self.assertTrue(result['billing_verified'])
        self.assertEqual(result['charged_usd'], '0.001')
        self.assertEqual(result['requests'], 1)
        self.assertIsNone(result['prompt_tokens'])
        self.assertIsNone(result['completion_tokens'])

    def test_no_requests_is_distinct_from_missing_ledger(self):
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'development')
        self.assertFalse((self.runtime / 'scored_budget.sqlite').exists())
        self.create(generate=False)
        self.assertEqual(audit_trial(self.runtime, 'test', 'development')['requests'], 0)

    def test_missing_receipt_halts(self):
        evidence = self.create()
        (evidence / '000001.receipt.json').unlink()
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'development')

    def test_matching_forged_artifact_cost_still_must_match_ledger(self):
        evidence = self.create()
        path = evidence / '000001.response.json'
        response = json.loads(path.read_text())
        response['usage']['cost'] = '.002'
        path.write_text(json.dumps(response))
        path = evidence / '000001.receipt.json'
        receipt = json.loads(path.read_text())
        receipt['total_cost'] = '.002'
        path.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'development')

    def test_ambiguous_request_is_not_released(self):
        self.client.fail = True
        with self.assertRaises(GatewayError): self.create()
        path = self.runtime / 'scored_budget.sqlite'
        before = path.read_bytes()
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'development')
        self.assertEqual(path.read_bytes(), before)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('SELECT state FROM requests').fetchone(), ('pending',))

    def test_stage_mismatch_halts(self):
        self.create()
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'final')

    def test_routing_drift_halts(self):
        evidence = self.create()
        path = evidence / '000001.request.json'
        request = json.loads(path.read_text())
        request['provider']['allow_fallbacks'] = True
        path.write_text(json.dumps(request))
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'development')

    def test_extra_artifact_is_not_ignored(self):
        evidence = self.create()
        (evidence / '000002.response.json').write_text('{}')
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'test', 'development')

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
from model_protocol import ModelSettings, freeze_protocol
from scored_gateway import private_directory
from budget_ledger import BudgetExceeded


class AccountingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / '.runtime/stage2'
        self.client = Client()
        self.token = 'fixture-token-' * 4
        self.payload = {'model': MODEL, 'max_tokens': 64,
                        'temperature': 1., 'reasoning': {'effort': 'high'},
                        'messages': [{'role': 'user', 'content': 'synthetic'}]}

    def tearDown(self): self.temp.cleanup()

    def create(self, generate=True):
        settings = ModelSettings(64, 1., 'high')
        freeze_protocol(private_directory(self.runtime), settings)
        with ScoredSession(self.root, 'test', 'development', self.token, self.client,
                           estimator=lambda request: '.01', settings=settings, receipt_timing='inline') as session:
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

    def test_budget_refusal_is_counted_without_fake_charge(self):
        self.client.allowance = '2.001'
        with self.assertRaises(BudgetExceeded): self.create()
        result = audit_trial(self.runtime, 'test', 'development')
        self.assertEqual(result['requests'], 0)
        self.assertEqual(result['charged_usd'], '0')
        self.assertEqual(result['budget_stop_count'], 1)
        self.assertEqual(self.client.calls, 0)

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


class HistoricalHoldAccountingTests(unittest.TestCase):
    def setUp(self):
        from test_historical_hold import HoldFixture
        from test_scored_gateway import HoldClient
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixture(self.temp.name)
        self.runtime = self.fixture.runtime
        self.client = HoldClient()
        self.token = 'synthetic-token-' * 4
        self.payload = {'model': MODEL, 'max_tokens': 64, 'temperature': 1.,
                        'reasoning': {'effort': 'high'},
                        'messages': [{'role': 'user', 'content': 'synthetic'}]}

    def tearDown(self):
        self.fixture.close()
        self.temp.cleanup()

    def create(self, *, calls=1):
        from post_trial_receipts import collect_receipts
        with ScoredSession(self.fixture.root, 'new', 'development', self.token, self.client,
                           estimator=lambda _: '.01', settings=self.fixture.settings) as session:
            for _ in range(calls): session.complete(self.token, self.payload)
        collect_receipts(self.runtime, 'new', client=self.client)
        return self.runtime / 'scored-attempts/new'

    def test_new_trial_verified_with_separate_actual_and_unknown_exposure(self):
        import historical_hold as hh
        self.create(calls=2)
        result = audit_trial(self.runtime, 'new', 'development')
        self.assertTrue(result['billing_verified'])
        self.assertEqual(result['charged_usd'], '0.002')
        self.assertEqual(result['aggregate_charged_usd'], '0.00237446')
        self.assertEqual(result['unresolved_reserved_usd'], '0.106496')
        self.assertEqual(result['aggregate_exposure_usd'], '0.10887046')
        self.assertEqual((result['prompt_tokens'], result['completion_tokens']), (14, 6))
        self.assertEqual(result['historical_hold_request_id'], hh.REQUEST_ID)
        self.assertIsNone(hh.validate_historical_hold(self.runtime)['charged_nanodollars'])
        with self.assertRaises(ValueError): audit_trial(self.runtime, hh.TRIAL_ID, 'development')

    def test_new_trial_missing_or_invalid_tokens_cannot_be_verified(self):
        evidence = self.create()
        path = evidence / '000001.response.json'
        response = json.loads(path.read_text())
        for token in ('prompt_tokens', 'completion_tokens'):
            for value in (None, -1, True, '7'):
                with self.subTest(token=token, value=value):
                    original = dict(response['usage'])
                    response['usage'][token] = value
                    path.write_text(json.dumps(response))
                    with self.assertRaisesRegex(ValueError, 'token evidence'):
                        audit_trial(self.runtime, 'new', 'development')
                    response['usage'] = original

    def test_new_trial_receipt_and_identity_checks_are_not_waived(self):
        evidence = self.create()
        receipt_path = evidence / '000001.receipt.json'
        original = receipt_path.read_bytes()
        receipt = json.loads(original)
        for field, value in [('id', 'wrong'), ('provider_name', 'wrong'), ('total_cost', '.002')]:
            with self.subTest(field=field):
                altered = dict(receipt, **{field: value})
                receipt_path.write_text(json.dumps(altered))
                with self.assertRaises(ValueError): audit_trial(self.runtime, 'new', 'development')
        receipt_path.write_bytes(original)
        receipt_path.unlink()
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'new', 'development')

    def test_historical_hold_still_counts_toward_stage_exposure(self):
        self.create()
        ledger = self.fixture.ledger()
        try:
            with ledger.transaction():
                ledger.db.execute("INSERT INTO requests VALUES ('extra','extra',2759000000,2759000000,'settled')")
                ledger.db.execute("INSERT INTO trial_stages VALUES ('extra','development')")
        finally:
            ledger.close()
        with self.assertRaisesRegex(ValueError, 'Stage ceiling'): audit_trial(self.runtime, 'new', 'development')


class TwoHistoricalHoldAccountingTests(HistoricalHoldAccountingTests):
    def setUp(self):
        from test_historical_hold import HoldFixtureV2
        from test_scored_gateway import HoldClient
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixtureV2(self.temp.name)
        self.runtime = self.fixture.runtime
        self.client = HoldClient()
        self.token = 'synthetic-token-' * 4
        self.payload = {'model': MODEL, 'max_tokens': 64, 'temperature': 1.,
                        'reasoning': {'effort': 'high'},
                        'messages': [{'role': 'user', 'content': 'synthetic'}]}

    def test_new_trial_verified_with_separate_actual_and_unknown_exposure(self):
        import historical_hold as hh
        self.create(calls=2)
        result = audit_trial(self.runtime, 'new', 'development')
        self.assertTrue(result['billing_verified'])
        self.assertEqual(result['charged_usd'], '0.002')
        self.assertEqual(result['aggregate_charged_usd'], '0.00525122')
        self.assertEqual(result['unresolved_reserved_usd'], '0.212992')
        self.assertEqual(result['aggregate_exposure_usd'], '0.21824322')
        self.assertEqual((result['prompt_tokens'], result['completion_tokens']), (14, 6))
        self.assertIsNone(result['historical_hold_request_id'])
        self.assertEqual(result['historical_hold_request_ids'], [hh.REQUEST_ID, hh.SECOND_REQUEST_ID])
        for entry in hh.hold_entries(hh.validate_historical_hold(self.runtime)):
            self.assertIsNone(entry['charged_nanodollars'])
            with self.assertRaises(ValueError): audit_trial(self.runtime, entry['trial_id'], 'development')

    def test_third_future_unknown_is_not_accepted_for_accounting(self):
        self.client.fail = True
        with self.assertRaises(GatewayError): self.create()
        with self.assertRaises(ValueError): audit_trial(self.runtime, 'new', 'development')

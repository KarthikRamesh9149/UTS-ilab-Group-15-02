from pathlib import Path
import tempfile
import unittest

from budget_ledger import Ledger, BudgetExceeded, dollars
from gateway_core import Gateway, GatewayError, Trial, token_digest
from gateway_policy import MODEL
from openrouter_transport import TransportError
from post_trial_receipts import collect_receipts
from scored_gateway import durable_json, private_directory


class DeferredReceiptsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.runtime = private_directory(Path(self.temp.name))
        self.evidence = private_directory(self.runtime / 'native-setup-attempts/fixture')
        self.ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        self.response = {'id': 'g1', 'model': MODEL, 'provider': 'DeepInfra',
                         'usage': {'cost': '.001', 'is_byok': False}}
        self.receipt_calls = []
        self.receipt = {'id': 'g1', 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.001'}
        self.gateway = Gateway(self.ledger, Trial('fixture', 'setup', token_digest('token')),
            lambda: '12', lambda request: '.1', self.complete, self.generation, receipt_timing='post_trial')
        self.payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'fixture'}], 'max_tokens': 64}

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def complete(self, request):
        durable_json(self.evidence / '000001.response.json', self.response)
        return self.response

    def generation(self, identifier):
        self.receipt_calls.append(identifier)
        return self.receipt

    def test_response_charge_enforced_without_blocking_for_receipt(self):
        response = self.gateway.complete('token', self.payload)
        self.assertEqual(response['id'], 'g1')
        self.assertEqual(self.receipt_calls, [])
        self.assertEqual(self.ledger.exposure(), dollars('.001'))
        self.assertEqual(len(self.ledger.pending_receipts()), 1)
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('r2', 'next-trial', '.1', '12', 'setup')
        report = collect_receipts(self.runtime, 'fixture', kind='setup', client=self)
        self.assertEqual(report['generation_calls'], 0)
        self.assertEqual(report['receipts_verified'], 1)
        self.assertEqual(self.receipt_calls, ['g1'])
        self.assertEqual(self.ledger.pending_receipts(), [])
        self.ledger.reserve('r2', 'next-trial', '.1', '12', 'setup')

    def test_wrong_provider_stays_pending_and_blocks_dispatch(self):
        self.response['provider'] = 'Other'
        with self.assertRaises(GatewayError):
            self.gateway.complete('token', self.payload)
        self.assertEqual(len(self.ledger.pending()), 1)
        with self.assertRaises(BudgetExceeded):
            self.gateway.complete('token', self.payload)

    def test_same_trial_may_continue_before_historical_receipt_arrives(self):
        self.gateway.complete('token', self.payload)
        self.ledger.reserve('r2', 'fixture', '.1', '12', 'setup')
        self.assertEqual(len(self.ledger.pending()), 1)
        self.assertEqual(len(self.ledger.pending_receipts()), 1)

    def test_reported_cost_over_reservation_halts_immediately(self):
        self.response['usage']['cost'] = '.2'
        with self.assertRaises(BudgetExceeded):
            self.gateway.complete('token', self.payload)
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0], 1)

    def test_delayed_receipt_polled_after_response_without_generation(self):
        self.gateway.complete('token', self.payload)
        now = [0]
        def sleep(delay): now[0] += delay
        calls = []
        def reader(identifier):
            calls.append(identifier)
            if len(calls) < 3: raise TransportError('OpenRouter HTTP status 404')
            return self.receipt
        from types import SimpleNamespace
        collect_receipts(self.runtime, 'fixture', kind='setup', client=SimpleNamespace(generation=reader),
                         clock=lambda: now[0], sleep=sleep)
        self.assertEqual(calls, ['g1'] * 3)

    def test_mismatch_persists_halt_for_future_trials(self):
        self.gateway.complete('token', self.payload)
        self.receipt['total_cost'] = '.002'
        with self.assertRaisesRegex(ValueError, 'ledger halted'):
            collect_receipts(self.runtime, 'fixture', kind='setup', client=self)
        self.assertEqual(self.ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0], 1)
        with self.assertRaises(BudgetExceeded):
            self.ledger.reserve('r2', 'next', '.1', '12', 'setup')

    def test_unavailable_receipt_cannot_claim_verified(self):
        self.gateway.complete('token', self.payload)
        now = [0]
        def reader(identifier): raise TransportError('Not ready')
        def sleep(delay): now[0] += delay
        from types import SimpleNamespace
        with self.assertRaises(TransportError):
            collect_receipts(self.runtime, 'fixture', kind='setup', client=SimpleNamespace(generation=reader),
                             deadline_seconds=1, clock=lambda: now[0], sleep=sleep)
        self.assertFalse((self.evidence / '000001.receipt.json').exists())


class HistoricalHoldReceiptTests(unittest.TestCase):
    def setUp(self):
        from test_historical_hold import HoldFixture
        from test_scored_gateway import HoldClient, ScoredSession
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixture(self.temp.name)
        self.runtime = self.fixture.runtime
        self.client = HoldClient()
        token = 'hold-receipt-token-' * 4
        payload = {'model': MODEL, 'max_tokens': 64, 'temperature': 1.,
                   'reasoning': {'effort': 'high'},
                   'messages': [{'role': 'user', 'content': 'synthetic'}]}
        with ScoredSession(self.fixture.root, 'new', 'development', token, self.client,
                           estimator=lambda _: '.01', settings=self.fixture.settings) as session:
            session.complete(token, payload)

    def tearDown(self):
        self.fixture.close()
        self.temp.cleanup()

    def test_new_trial_receipts_can_reconcile_but_old_charge_stays_unknown(self):
        import historical_hold as hh
        original = self.fixture.result.read_bytes()
        report = collect_receipts(self.runtime, 'new', client=self.client)
        self.assertEqual(report, {'receipts_verified': 1, 'generation_calls': 0})
        self.assertEqual(self.client.calls, 1)
        self.assertEqual(self.fixture.result.read_bytes(), original)
        ledger = self.fixture.ledger()
        try:
            self.assertEqual(ledger.pending(), [(hh.REQUEST_ID, hh.TRIAL_ID, 106496000, None)])
            self.assertEqual(ledger.pending_receipts(), [])
        finally:
            ledger.close()
        with self.assertRaises(BudgetExceeded): collect_receipts(self.runtime, hh.TRIAL_ID, client=self.client)

    def test_new_trial_missing_generation_is_not_hidden_by_join(self):
        ledger = self.fixture.ledger()
        try:
            ledger.db.execute("DELETE FROM generations WHERE request_id IN (SELECT id FROM requests WHERE trial='new')")
            self.assertEqual(len(ledger.pending_receipts()), 1)
            self.assertIsNone(ledger.pending_receipts()[0][2])
        finally:
            ledger.close()
        with self.assertRaises(ValueError): collect_receipts(self.runtime, 'new', client=self.client)

    def test_new_mismatch_records_incident_and_blocks_all_further_admission(self):
        self.client.cost = '.002'
        with self.assertRaisesRegex(ValueError, 'ledger halted'):
            collect_receipts(self.runtime, 'new', client=self.client)
        ledger = self.fixture.ledger()
        try:
            self.assertEqual(ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0], 1)
            with self.assertRaises(BudgetExceeded):
                ledger.reserve('another', 'another', '.1', '12', 'development', trial_estimate='.01')
        finally:
            ledger.close()

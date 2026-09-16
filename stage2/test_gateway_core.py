from pathlib import Path
import tempfile
import unittest

from budget_ledger import BudgetExceeded, Ledger, dollars
from gateway_core import Gateway, GatewayError, Trial, token_digest
from gateway_policy import MODEL


class GatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.ledger = Ledger(Path(self.temp.name) / 'ledger.sqlite', '.1', '.055')
        self.calls = []
        self.response = {'id': 'synthetic-generation', 'model': MODEL, 'usage': {'cost': '.001'}}
        self.gateway = Gateway(self.ledger, Trial('trial1', 'development', token_digest('test-token')),
                               lambda: '25', lambda request: '.01', self.upstream)
        self.payload = {'model': MODEL, 'messages': [{'role':'user','content':'fixture'}], 'max_tokens': 32}

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def upstream(self, request):
        self.assertEqual(self.ledger.exposure(), dollars('.01'))
        self.calls.append(request)
        return self.response

    def test_reserves_before_dispatch_and_settles(self):
        self.gateway.complete('test-token', self.payload)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.ledger.exposure(), dollars('.001'))

    def test_auth_and_revocation_precede_dispatch(self):
        with self.assertRaises(GatewayError):
            self.gateway.complete('bad', self.payload)
        self.gateway.revoke()
        with self.assertRaises(GatewayError):
            self.gateway.complete('test-token', self.payload)
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.exposure(), 0)

    def test_missing_cost_blocks_next_request(self):
        self.response['usage'] = {}
        with self.assertRaises(GatewayError):
            self.gateway.complete('test-token', self.payload)
        with self.assertRaises(BudgetExceeded):
            self.gateway.complete('test-token', self.payload)
        self.assertEqual(len(self.calls), 1)

    def test_network_failure_never_retries_or_leaks_exception(self):
        def failed(request):
            self.calls.append(request)
            raise RuntimeError('secret-canary')
        self.gateway.upstream = failed
        with self.assertRaises(GatewayError) as caught:
            self.gateway.complete('test-token', self.payload)
        self.assertNotIn('secret-canary', str(caught.exception))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.ledger.exposure(), dollars('.01'))

    def test_no_estimator_means_no_paid_call(self):
        self.gateway.maximum_charge = None
        with self.assertRaises(GatewayError):
            self.gateway.complete('test-token', self.payload)
        self.assertEqual(self.calls, [])

    def test_insufficient_balance_prevents_dispatch(self):
        self.gateway.balance_reader = lambda: '2.001'
        with self.assertRaises(BudgetExceeded):
            self.gateway.complete('test-token', self.payload)
        self.assertEqual(self.calls, [])

    def test_wrong_model_keeps_reservation(self):
        self.response['model'] = 'wrong'
        with self.assertRaises(GatewayError):
            self.gateway.complete('test-token', self.payload)
        self.assertEqual(self.ledger.exposure(), dollars('.01'))

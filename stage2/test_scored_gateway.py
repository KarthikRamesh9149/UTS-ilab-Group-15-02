from decimal import Decimal
import json
import fcntl
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from budget_ledger import BudgetExceeded, dollars
from gateway_core import GatewayError
from gateway_policy import MODEL, ENDPOINT
from scored_gateway import ScoredSession, serve
from setup_probe import CONTEXT


class Client:
    allowance = '25'
    calls = 0
    fail = False
    cost = '.001'

    def metadata(self):
        return {'data': {'id': MODEL, 'endpoints': [{'tag': ENDPOINT,
            'quantization': 'fp8', 'context_length': CONTEXT,
            'pricing': {'prompt': '.00000006', 'completion': '.00000018'}}]}}

    def key_status(self):
        return {'limit_remaining': self.allowance}

    def balance(self):
        return '25'

    def complete(self, request):
        self.calls += 1
        if self.fail:
            raise RuntimeError('secret-canary')
        return {'id': 'fixture-' + str(self.calls), 'model': MODEL,
                'usage': {'cost': self.cost}}

    def generation(self, identifier):
        return {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra',
                'total_cost': self.cost}


class ScoredGatewayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.client = Client()
        self.token = 'synthetic-token-' * 4
        self.payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'test'}], 'max_tokens': 64}

    def tearDown(self):
        self.temp.cleanup()

    def session(self, identifier='trial-1', stage='development'):
        return ScoredSession(self.root, identifier, stage, self.token, self.client,
                             estimator=lambda request: '.01', receipt_timing='inline')

    def test_durable_request_response_receipt_and_shared_caps(self):
        with self.session() as session:
            session.complete(self.token, self.payload)
            self.assertEqual(session.ledger.exposure(), dollars('.001'))
            for kind in ['request', 'response', 'receipt']:
                path = session.evidence / ('000001.' + kind + '.json')
                self.assertIsInstance(json.loads(path.read_text()), dict)
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        with self.session('trial-2', 'final') as session:
            self.assertEqual(session.ledger.exposure(), dollars('.001'))
            self.assertEqual(session.ledger.ceiling, dollars('8.901'))
            self.assertEqual(session.ledger.trial_cap, dollars('.023'))

    def test_cannot_replay_finished_trial(self):
        with self.session():
            pass
        with self.assertRaises(FileExistsError):
            self.session()

    def test_concurrent_session_refused(self):
        with self.session():
            with self.assertRaises(BlockingIOError):
                self.session('trial-2')
        with self.session('trial-2'):
            pass

    def test_gateway_and_host_orchestration_locks_are_distinct(self):
        runtime = self.root / '.runtime/stage2'
        runtime.mkdir(parents=True, mode=0o700)
        with (runtime / 'scored.lock').open('w') as host_lock:
            fcntl.flock(host_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.session():
                self.assertTrue((runtime / 'gateway.lock').exists())

    def test_ambiguous_generation_persists_and_blocks_next_trial(self):
        self.client.fail = True
        with self.session() as session:
            with self.assertRaises(GatewayError):
                session.complete(self.token, self.payload)
            self.assertEqual(len(session.ledger.pending()), 1)
        with self.assertRaises(BudgetExceeded):
            self.session('trial-2')
        self.assertEqual(self.client.calls, 1)

    def test_fresh_key_allowance_prevents_dispatch(self):
        with self.session() as session:
            self.client.allowance = '2.001'
            with self.assertRaises(BudgetExceeded):
                session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 0)

    def test_underestimate_halts_future_trials(self):
        self.client.cost = '.011'
        with self.session() as session:
            with self.assertRaises(BudgetExceeded):
                session.complete(self.token, self.payload)
        with self.assertRaises(BudgetExceeded):
            self.session('trial-2')
        self.assertEqual(self.client.calls, 1)
        self.assertFalse((self.root / '.runtime/stage2/scored-attempts/trial-2').exists())

    def test_closed_session_cannot_dispatch(self):
        session = self.session()
        session.close()
        with self.assertRaises(RuntimeError):
            session.complete(self.token, self.payload)

    def test_unknown_allowance_and_invalid_identity_fail_closed(self):
        self.client.allowance = None
        with self.assertRaises(BudgetExceeded):
            self.session()
        with self.assertRaises(ValueError):
            self.session('../escape')

    def test_service_interrupt_closes_socket_and_releases_ownership(self):
        from model_protocol import ModelSettings, freeze_protocol
        from scored_gateway import private_directory
        freeze_protocol(private_directory(self.root / '.runtime/stage2'), ModelSettings(64, 1., 'high'))
        token = self.root / 'token'
        token.write_text('a' * 64)
        token.chmod(0o600)
        sock = self.root / 'socket' / 'model.sock'
        with patch('openrouter_transport.load_key', return_value='synthetic-key'), \
             patch('openrouter_transport.OpenRouter', return_value=self.client), \
             patch('gateway_http.UnixHTTPServer.serve_forever', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                serve(self.root, 'service-trial', 'development', token, self.root / 'credential', sock)
        self.assertFalse(sock.exists())
        with self.session('following-trial'):
            pass
        self.assertEqual(self.client.calls, 0)

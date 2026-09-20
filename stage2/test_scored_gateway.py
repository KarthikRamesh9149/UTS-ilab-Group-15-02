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
from openrouter_transport import TransportError, error_diagnostic


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

    def complete(self, request, *, on_response_headers=None):
        self.calls += 1
        if self.fail:
            raise RuntimeError('secret-canary')
        return {'id': 'fixture-' + str(self.calls), 'model': MODEL,
                'usage': {'cost': self.cost}}

    def generation(self, identifier):
        return {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra',
                'total_cost': self.cost}


class HoldClient(Client):
    def complete(self, request, *, on_response_headers=None):
        response = super().complete(request, on_response_headers=on_response_headers)
        response['provider'] = 'DeepInfra'
        response['usage'].update(is_byok=False, prompt_tokens=7, completion_tokens=3)
        return response


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
            self.assertIsNone(session.ledger.pending()[0][3])
        with self.assertRaises(BudgetExceeded):
            self.session('trial-2')
        self.assertEqual(self.client.calls, 1)

    def test_transport_diagnostic_is_durable_without_settlement_or_replay(self):
        diagnostic = error_diagnostic({'id': 'gen-failed', 'error': {'code': 502}}, status=502)
        with self.session() as session, patch.object(self.client, 'complete',
                side_effect=TransportError('Safe error', diagnostic=diagnostic)) as complete:
            with self.assertRaises(GatewayError): session.complete(self.token, self.payload)
            path = session.evidence / '000001.transport-error.json'
            self.assertEqual(json.loads(path.read_text()), diagnostic)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(len(session.ledger.pending()), 1)
            self.assertEqual(session.ledger.pending()[0][3], 'gen-failed')
            self.assertFalse((session.evidence / '000001.response.json').exists())
            complete.assert_called_once()
        with self.assertRaises(BudgetExceeded): self.session('next-trial')

    def test_fresh_key_allowance_prevents_dispatch(self):
        with self.session() as session:
            self.client.allowance = '2.001'
            with self.assertRaises(BudgetExceeded):
                session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 0)

    def test_headers_are_durable_and_linked_before_interrupted_body(self):
        for number, error in enumerate((TransportError('body timeout'), KeyboardInterrupt())):
            with self.subTest(error=type(error).__name__), self.session('header-' + str(number)) as session:
                diagnostic = error_diagnostic(status=200, headers={
                    'X-Generation-Id': 'gen-before-body', 'X-Request-Id': 'req-before-body'})
                def complete(request, *, on_response_headers):
                    self.client.calls += 1
                    on_response_headers(dict(diagnostic, raw='secret-canary'))
                    record = json.loads((session.evidence / '000001.response-headers.json').read_text())
                    reservation = json.loads((session.evidence / '000001.reservation.json').read_text())
                    self.assertEqual(record['reservation_id'], session.ledger.pending()[0][0])
                    self.assertEqual(record['reservation_id'], reservation['reservation_id'])
                    self.assertEqual(record['diagnostic'], diagnostic)
                    self.assertNotIn('secret-canary', json.dumps(record))
                    self.assertEqual(session.ledger.pending()[0][3], 'gen-before-body')
                    self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(),
                                     (None, 'pending'))
                    raise error
                with patch.object(self.client, 'complete', side_effect=complete) as dispatch:
                    with self.assertRaises(KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else GatewayError):
                        session.complete(self.token, self.payload)
                    dispatch.assert_called_once()
                self.assertFalse((session.evidence / '000001.response.json').exists())
                reserved = session.ledger.pending()[0][2]
                self.assertGreater(reserved, 0)
                self.assertEqual(session.ledger.exposure(), reserved)
                self.assertEqual((session.evidence / '000001.response-headers.json').stat().st_mode & 0o777, 0o600)
                if isinstance(error, KeyboardInterrupt):
                    self.assertTrue((session.evidence / '000001.interruption.json').exists())
                    self.assertEqual(json.loads((session.evidence / '000001.timing.json').read_text())['status'], 'interrupted')
                with self.assertRaises(BudgetExceeded): session.complete(self.token, self.payload)
            with self.assertRaises(BudgetExceeded): self.session('blocked-' + str(number))
            # Each subcase uses a fresh temporary ledger, never clears a hold.
            if number == 0:
                self.temp.cleanup()
                self.temp = tempfile.TemporaryDirectory()
                self.root = Path(self.temp.name)

    def test_missing_headers_leave_generation_unknown_on_interruption(self):
        def complete(request, *, on_response_headers):
            on_response_headers(error_diagnostic(status=200))
            raise KeyboardInterrupt
        with self.session() as session, patch.object(self.client, 'complete', side_effect=complete) as dispatch:
            with self.assertRaises(KeyboardInterrupt): session.complete(self.token, self.payload)
            self.assertIsNone(session.ledger.pending()[0][3])
            self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(), (None, 'pending'))
            self.assertIsNone(json.loads((session.evidence / '000001.response-headers.json').read_text())['diagnostic']['generation_id'])
            dispatch.assert_called_once()

    def test_real_transport_callback_records_id_before_body_interrupt(self):
        from io import BytesIO
        from openrouter_transport import OpenRouter
        class Response(BytesIO):
            status = 200
            headers = {'X-Generation-Id': 'gen-real-transport-fixture'}
            def read(inner, size):
                record = json.loads((session.evidence / '000001.response-headers.json').read_text())
                self.assertEqual(record['reservation_id'], session.ledger.pending()[0][0])
                self.assertEqual(session.ledger.pending()[0][3], 'gen-real-transport-fixture')
                raise KeyboardInterrupt
        response = Response()
        with patch('openrouter_transport.build_opener') as build_opener:
            build_opener.return_value.open.return_value = response
            original = self.client
            self.client = OpenRouter('synthetic-not-secret', generation_enabled=True, completion_wait_seconds=360)
            for name in ('metadata', 'balance', 'key_status'):
                setattr(self.client, name, getattr(original, name))
            with self.session() as session:
                with self.assertRaises(KeyboardInterrupt): session.complete(self.token, self.payload)
                self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(), (None, 'pending'))
                self.assertFalse((session.evidence / '000001.response.json').exists())
            build_opener.return_value.open.assert_called_once()
            self.assertEqual(build_opener.return_value.open.call_args.kwargs['timeout'], 360)
        self.assertTrue(response.closed)

    def test_header_body_identity_conflict_preserves_first_id_and_reservation(self):
        def complete(request, *, on_response_headers):
            on_response_headers(error_diagnostic(status=200, headers={'X-Generation-Id': 'gen-header'}))
            return {'id': 'gen-other-body', 'model': MODEL, 'usage': {'cost': '.001'}}
        with self.session() as session, patch.object(self.client, 'complete', side_effect=complete) as dispatch:
            with self.assertRaisesRegex(GatewayError, 'generation identity'):
                session.complete(self.token, self.payload)
            self.assertEqual(session.ledger.pending()[0][3], 'gen-header')
            self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(), (None, 'pending'))
            self.assertEqual(session.ledger.exposure(), session.ledger.pending()[0][2])
            self.assertTrue((session.evidence / '000001.response.json').exists())
            dispatch.assert_called_once()

    def test_matching_header_and_body_settle_only_after_full_response(self):
        def complete(request, *, on_response_headers):
            on_response_headers(error_diagnostic(status=200, headers={'X-Generation-Id': 'gen-matching'}))
            self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(), (None, 'pending'))
            return {'id': 'gen-matching', 'model': MODEL, 'usage': {'cost': '.001'}}
        with self.session() as session, patch.object(self.client, 'complete', side_effect=complete):
            session.complete(self.token, self.payload)
            self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(), (dollars('.001'), 'settled'))
            self.assertEqual(session.ledger.db.execute('SELECT COUNT(*) FROM generations').fetchone()[0], 1)


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
             patch('openrouter_transport.OpenRouter', return_value=self.client) as transport, \
             patch('gateway_http.UnixHTTPServer.serve_forever', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                serve(self.root, 'service-trial', 'development', token, self.root / 'credential', sock,
                      completion_wait_seconds=360)
            transport.assert_called_once_with('synthetic-key', generation_enabled=True, completion_wait_seconds=360)
        self.assertFalse(sock.exists())
        with self.session('following-trial'):
            pass
        self.assertEqual(self.client.calls, 0)

    def test_service_requires_valid_explicit_completion_wait_before_file_access(self):
        for value in (True, False, 0, -1, float('nan'), float('inf'), '360', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                serve(self.root, 'unused', 'development', 'missing', 'missing', 'missing',
                      completion_wait_seconds=value)
        with self.assertRaises(TypeError):
            serve(self.root, 'unused', 'development', 'missing', 'missing', 'missing')


class HistoricalHoldGatewayTests(unittest.TestCase):
    def setUp(self):
        from test_historical_hold import HoldFixture
        self.temp = tempfile.TemporaryDirectory()
        self.fixture = HoldFixture(self.temp.name)
        self.client = HoldClient()
        self.token = 'synthetic-hold-token-' * 4
        self.payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'test'}],
                        'max_tokens': 64, 'temperature': 1., 'reasoning': {'effort': 'high'}}

    def tearDown(self):
        self.fixture.close()
        self.temp.cleanup()

    def session(self, trial='new'):
        return ScoredSession(self.fixture.root, trial, 'development', self.token, self.client,
                             settings=self.fixture.settings, estimator=lambda _: '.01')

    def test_different_trial_can_run_and_old_trial_cannot_replay(self):
        import historical_hold as hh
        with self.session() as session:
            session.complete(self.token, self.payload)
            self.assertEqual(session.ledger.pending()[0][0], hh.REQUEST_ID)
            self.assertEqual(session.ledger.exposure(), 107870460)
        with self.assertRaises(BudgetExceeded): self.session(hh.TRIAL_ID)
        self.assertEqual(self.client.calls, 1)

    def test_new_trial_pending_receipts_prevent_another_trial_start(self):
        with self.session() as session:
            session.complete(self.token, self.payload)
        with self.assertRaises(BudgetExceeded): self.session('next')
        self.assertFalse((self.fixture.runtime / 'scored-attempts/next').exists())

    def test_fresh_credit_accounts_for_historical_pending_amount(self):
        with self.session() as session:
            self.client.allowance = '2.11'
            with self.assertRaises(BudgetExceeded): session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 0)

    def test_unknown_new_outcome_blocks_restart_without_releasing_either_hold(self):
        self.client.fail = True
        with self.session() as session:
            with self.assertRaises(GatewayError): session.complete(self.token, self.payload)
            self.assertEqual(len(session.ledger.pending()), 2)
        with self.assertRaises(BudgetExceeded): self.session('next')
        self.assertEqual(self.client.calls, 1)

    def test_setup_unknown_introduced_after_session_admission_blocks_dispatch(self):
        from budget_ledger import Ledger
        with self.session() as session:
            setup = Ledger(self.fixture.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
            try:
                setup.reserve('setup-unknown', 'setup-probe', '.1', '12', 'setup')
                with self.assertRaises(BudgetExceeded): session.complete(self.token, self.payload)
            finally:
                setup.close()
        self.assertEqual(self.client.calls, 0)

    def test_setup_incident_or_unverified_receipt_blocks_session_start(self):
        from budget_ledger import Ledger
        setup = Ledger(self.fixture.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        try:
            for statement in ["INSERT INTO incidents VALUES ('unknown',1)",
                              "INSERT INTO receipt_checks VALUES ('orphan','pending')"]:
                with self.subTest(statement=statement):
                    setup.db.execute(statement)
                    with self.assertRaises(BudgetExceeded): self.session('next')
                    setup.db.execute('DELETE FROM incidents')
                    setup.db.execute('DELETE FROM receipt_checks')
        finally:
            setup.close()
        self.assertEqual(self.client.calls, 0)

    def test_amended_session_requires_original_setup_ledger_even_for_dangling_sidecar(self):
        import historical_hold as hh
        (self.fixture.runtime / 'setup_budget.sqlite').unlink()
        with self.assertRaisesRegex(BudgetExceeded, 'Original setup ledger required'):
            self.session()
        sidecar = self.fixture.runtime / hh.SIDECAR
        sidecar.unlink()
        sidecar.symlink_to(self.fixture.runtime / 'missing-amendment')
        with self.assertRaisesRegex(BudgetExceeded, 'Original setup ledger required'):
            self.session()
        self.assertEqual(self.client.calls, 0)

    def test_setup_ledger_removal_after_admission_blocks_dispatch(self):
        with self.session() as session:
            (self.fixture.runtime / 'setup_budget.sqlite').unlink()
            with self.assertRaisesRegex(BudgetExceeded, 'Original setup ledger required'):
                session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 0)

    def test_setup_ledger_must_stay_private(self):
        setup_path = self.fixture.runtime / 'setup_budget.sqlite'
        setup_path.chmod(0o644)
        with self.assertRaisesRegex(BudgetExceeded, 'Original setup ledger required'):
            self.session()
        setup_path.chmod(0o600)
        with self.session() as session:
            setup_path.chmod(0o644)
            with self.assertRaisesRegex(BudgetExceeded, 'Original setup ledger required'):
                session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 0)

    def test_validated_setup_deferral_is_still_deducted_from_scored_credit(self):
        from budget_ledger import Ledger
        from scored_gateway import require_clear_setup_ledger
        setup = Ledger(self.fixture.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        setup.reserve('setup-unknown', 'setup-probe', '.1', '12', 'setup')
        setup.close()
        validated = [{'deferred_request_ids': ['setup-unknown'],
                      'extra_reserved_nanodollars': 0}]
        import deferred_billing
        original = deferred_billing.validate_deferrals
        def validate(runtime, db=None, *, kind='scored', active_trial=None):
            return validated if kind == 'setup' else original(runtime, db, kind=kind, active_trial=active_trial)
        with patch('deferred_billing.validate_deferrals', side_effect=validate):
            self.assertEqual(require_clear_setup_ledger(self.fixture.runtime), Decimal('.1'))
            with self.session() as session:
                self.client.allowance = '2.3'
                with self.assertRaises(BudgetExceeded): session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 0)

    def test_receipt_only_setup_deferral_deducts_only_unbilled_difference(self):
        from budget_ledger import Ledger
        from scored_gateway import require_clear_setup_ledger
        setup = Ledger(self.fixture.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        setup.reserve('setup-receipt', 'setup-probe', '.1', '12', 'setup')
        setup.settle('setup-receipt', '.001', receipt_pending=True)
        setup.close()
        validated = [{'deferred_request_ids': ['setup-receipt'],
                      'extra_reserved_nanodollars': dollars('.099')}]
        with patch('deferred_billing.validate_deferrals', return_value=validated):
            self.assertEqual(require_clear_setup_ledger(self.fixture.runtime), Decimal('.099'))

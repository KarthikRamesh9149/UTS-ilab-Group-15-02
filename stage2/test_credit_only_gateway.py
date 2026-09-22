from copy import deepcopy
from decimal import Decimal
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from credit_only_accounting import summarise, metrics_for, PassiveTrialTrace
from credit_only_gateway import (PassiveSession, CreditOnlyError, CreditOnlyHandler,
                                 prepare_credit_request, exact_cost)
from credit_only_policy import POLICY, POLICY_FILE, require_policy
from gateway_http import make_server
from gateway_policy import MODEL, ENDPOINT
from model_protocol import ModelSettings
from openrouter_transport import TransportError, error_diagnostic
from scored_gateway import durable_json, private_directory

SETTINGS = ModelSettings(8192, 1., 'high')
TOKEN = 'synthetic-trial-token-' * 4
PAYLOAD = dict(model=MODEL, max_tokens=8192, temperature=1., reasoning={'effort': 'high'},
               messages=[{'role': 'user', 'content': 'synthetic infrastructure fixture'}])


class Client:
    def __init__(self):
        self.calls = []
        self.response = dict(id='gen-fixture', model=MODEL, provider='DeepInfra',
            choices=[{'message': {'role': 'assistant', 'content': 'fixture'}}],
            usage=dict(cost=Decimal('.00042'), prompt_tokens=10, completion_tokens=4))
        self.error = None

    def complete(self, payload, *, on_response_headers=None):
        self.calls.append(deepcopy(payload))
        if self.error is not None:
            raise self.error
        response = deepcopy(self.response)
        if response.get('id') == 'gen-fixture':
            response['id'] += '-' + str(len(self.calls))
        on_response_headers(error_diagnostic(status=200))
        return response

    def balance(self): raise AssertionError('No balance admission permitted')
    def key_status(self): raise AssertionError('No allowance admission permitted')
    def metadata(self): raise AssertionError('No price admission permitted')
    def generation(self, identifier): raise AssertionError('Receipts cannot gate dispatch')


class PassiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        durable_json(self.runtime / POLICY_FILE, POLICY)
        self.client = Client()

    def tearDown(self):
        self.temp.cleanup()

    def session(self, name='credit-only-1'):
        return PassiveSession(self.root, name, 'final', TOKEN, self.client, settings=SETTINGS)

    def test_policy_is_explicit_private_and_exact(self):
        path = self.runtime / POLICY_FILE
        self.assertEqual(require_policy(self.runtime), POLICY)
        path.chmod(0o644)
        with self.assertRaises(ValueError): self.session()
        path.chmod(0o600)
        value = dict(POLICY, reserve_usd='1')
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.session()
        self.assertFalse(self.client.calls)

    def test_exact_routing_without_price_filter(self):
        before = deepcopy(PAYLOAD)
        request = prepare_credit_request(PAYLOAD, SETTINGS)
        self.assertEqual(PAYLOAD, before)
        self.assertEqual(request['provider'], dict(only=[ENDPOINT], order=[ENDPOINT],
            allow_fallbacks=False, require_parameters=True, quantizations=['fp8']))
        self.assertEqual(request['max_tokens'], 8192)
        self.assertEqual(request['top_p'], 1.)

    def test_old_caps_pending_receipts_and_holds_are_not_read(self):
        names = ('setup_budget.sqlite', 'scored_budget.sqlite', 'baseline-repeat-budget-v1.json',
                 'historical-hold-v1.json', 'deferred-billing-policy-v1.json')
        for name in names:
            (self.runtime / name).write_bytes(b'invalid-old-accounting-must-not-be-read')
        with patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No reservation')), \
             self.session() as session:
            for _ in range(3):
                session.complete(TOKEN, PAYLOAD)
        self.assertEqual(len(self.client.calls), 3)
        for name in names:
            self.assertEqual((self.runtime / name).read_bytes(), b'invalid-old-accounting-must-not-be-read')
        self.assertFalse(list((self.runtime / 'scored-attempts').rglob('*.reservation.json')))

    def test_missing_usage_receipt_and_generation_id_still_return_completion(self):
        self.client.response.pop('usage')
        self.client.response.pop('id')
        with self.session() as session:
            for _ in range(3):
                self.assertEqual(session.complete(TOKEN, PAYLOAD)['model'], MODEL)
        summary = summarise(self.runtime, 'credit-only-1')
        self.assertEqual(summary['requests'], 3)
        self.assertEqual(summary['unknown_cost_requests'], 3)
        self.assertEqual(summary['known_charged_usd'], '0')
        self.assertIsNone(summary['charged_usd'])
        self.assertIsNone(summary['prompt_tokens'])
        self.assertFalse(summary['billing_verified'])
        self.assertIsNone(summary['provider_stop'])
        with self.session('credit-only-2') as session:
            session.complete(TOKEN, PAYLOAD)
        self.assertEqual(len(self.client.calls), 4)

    def test_invalid_costs_are_unknown_not_completion_failures(self):
        for number, value in enumerate((None, True, -1, 'NaN', 'Infinity', '-0.2', {}, [], .003)):
            self.client.response['usage']['cost'] = value
            with self.subTest(value=value), self.session('case-' + str(number)) as session:
                self.assertEqual(session.complete(TOKEN, PAYLOAD)['provider'], 'DeepInfra')
                summary = summarise(self.runtime, session.trial_id)
                self.assertIsNone(summary['charged_usd'])
                self.assertEqual(summary['unknown_cost_requests'], 1)

    def test_high_actual_charge_does_not_stop_next_call(self):
        self.client.response['usage']['cost'] = Decimal('10000.123456789')
        with self.session() as session:
            session.complete(TOKEN, PAYLOAD)
            session.complete(TOKEN, PAYLOAD)
        summary = summarise(self.runtime, 'credit-only-1')
        self.assertEqual(summary['charged_usd'], '20000.246913578')
        self.assertTrue(summary['costs_complete'])
        self.assertFalse(summary['billing_verified'])

    def test_bad_token_and_protocol_never_dispatch(self):
        with self.session() as session:
            with self.assertRaises(CreditOnlyError) as caught: session.complete('wrong', PAYLOAD)
            self.assertEqual(caught.exception.http_status, 401)
            for payload in (dict(PAYLOAD, model='other'), dict(PAYLOAD, max_tokens=8193),
                    dict(PAYLOAD, temperature=0), dict(PAYLOAD, provider={'only': ['other']})):
                with self.assertRaises(ValueError): session.complete(TOKEN, payload)
        self.assertFalse(self.client.calls)

    def test_credit_rejection_is_real_and_never_retried(self):
        self.client.error = TransportError('SECRET-canary', diagnostic=error_diagnostic(
            {'error': {'code': 402}}, status=402))
        with self.session() as session:
            with self.assertRaises(CreditOnlyError) as caught: session.complete(TOKEN, PAYLOAD)
            self.assertEqual(caught.exception.code, 'provider_credit_exhausted')
            self.assertNotIn('SECRET', str(caught.exception))
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, PAYLOAD)
        self.assertEqual(len(self.client.calls), 1)
        summary = summarise(self.runtime, 'credit-only-1')
        self.assertEqual(summary['provider_stop']['reason'], 'provider_credit_exhausted')
        self.assertIsNone(summary['charged_usd'])

    def test_authentication_and_identity_rejections_stop_matrix(self):
        for number, status in enumerate((401, 403)):
            self.client.error = TransportError('sensitive', diagnostic=error_diagnostic(status=status))
            with self.session('auth-' + str(number)) as session:
                with self.assertRaises(CreditOnlyError): session.complete(TOKEN, PAYLOAD)
            self.assertEqual(summarise(self.runtime, session.trial_id)['provider_stop']['reason'], 'upstream_authentication')
        self.client.error = None
        for number, changed in enumerate(({'model': 'wrong'}, {'provider': 'other'})):
            self.client.response.update(changed)
            with self.session('identity-' + str(number)) as session:
                with self.assertRaises(CreditOnlyError): session.complete(TOKEN, PAYLOAD)
            summary = summarise(self.runtime, session.trial_id)
            self.assertEqual(summary['provider_stop']['reason'], 'response_integrity')
            self.assertEqual(summary['charged_usd'], '0.00042')

    def test_timeout_stops_attempt_not_later_task_or_billing(self):
        self.client.error = TransportError('sensitive timeout')
        with self.session() as session:
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, PAYLOAD)
            with self.assertRaises(CreditOnlyError): session.complete(TOKEN, PAYLOAD)
        self.assertEqual(len(self.client.calls), 1)
        self.assertIsNone(summarise(self.runtime, 'credit-only-1')['provider_stop'])
        self.client.error = None
        with self.session('credit-only-2') as session: session.complete(TOKEN, PAYLOAD)
        self.assertEqual(len(self.client.calls), 2)

    def test_duplicate_generation_identity_rejected(self):
        self.client.response['id'] = 'gen-duplicate'
        with self.session() as session:
            session.complete(TOKEN, PAYLOAD)
            with self.assertRaises(CreditOnlyError) as caught: session.complete(TOKEN, PAYLOAD)
            self.assertEqual(caught.exception.code, 'response_integrity')

    def test_interruption_has_unknown_durable_outcome(self):
        self.client.error = KeyboardInterrupt()
        with self.session() as session:
            with self.assertRaises(KeyboardInterrupt): session.complete(TOKEN, PAYLOAD)
            self.assertEqual(json.loads((session.evidence / '000001.outcome.json').read_text())['status'], 'interrupted')
        self.assertIsNone(summarise(self.runtime, 'credit-only-1')['charged_usd'])

    def test_no_replay_no_concurrent_session_and_revocation(self):
        with self.session() as session:
            with self.assertRaises(BlockingIOError): self.session('other')
        with self.assertRaises(CreditOnlyError): session.complete(TOKEN, PAYLOAD)
        with self.assertRaises(FileExistsError): self.session()
        with self.session('other'): pass

    def test_private_call_evidence_before_provider_dispatch(self):
        original = self.client.complete
        with self.session() as session:
            def complete(payload, **kwargs):
                path = session.evidence / '000001.request.json'
                self.assertTrue(path.exists())
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                return original(payload, **kwargs)
            self.client.complete = complete
            session.complete(TOKEN, PAYLOAD)
            for path in session.evidence.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertNotIn(TOKEN, path.read_text())

    def test_incomplete_call_counts_as_unknown(self):
        with self.session() as session:
            durable_json(session.evidence / '000001.request.json', PAYLOAD)
        summary = summarise(self.runtime, session.trial_id)
        self.assertEqual(summary['requests'], 1)
        self.assertEqual(summary['unknown_cost_requests'], 1)
        self.assertIsNone(summary['charged_usd'])

    def test_trace_unknown_metrics_are_omitted_not_zero(self):
        self.assertEqual(metrics_for({'cost_usd': None}), {'requests': 1})
        self.assertEqual(exact_cost('0.0000000001'), '1E-10')
        self.assertNotIn('charged_nanodollars', metrics_for({'cost_usd': '1E-10'}))
        self.client.response.pop('usage')
        trace = PassiveTrialTrace(self.root / 'traces', trial_id='credit-only-1', task_id='fixture',
            harness='terminus-2', protocol_sha256=SETTINGS.fingerprint())
        import time
        start = time.time_ns()
        with self.session() as session: session.complete(TOKEN, PAYLOAD)
        end = time.time_ns()
        trace(kind='trial', started_ns=start, ended_ns=end, seconds=(end-start)/1e9)
        result = trace.finish(session.evidence, summarise(self.runtime, session.trial_id))
        self.assertEqual(result['unknown_cost_requests'], 1)
        for event in trace.spool.events():
            self.assertNotIn('charged_nanodollars', event['metrics'])
            self.assertNotIn('input_tokens', event['metrics'])


    # Exercise the real shared framing with the new error semantics.
    def test_live_loopback_http_error_and_completion_contract(self):
        session = self.session()
        server = make_server(lambda: session, handler=CreditOnlyHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def call(payload):
            client = http.client.HTTPConnection(*server.server_address, timeout=3)
            try:
                client.request('POST', '/v1/chat/completions', json.dumps(payload), {'Authorization': 'Bearer ' + TOKEN})
                response = client.getresponse()
                return response.status, json.loads(response.read())
            finally:
                client.close()
        try:
            self.client.response.pop('usage')
            self.assertEqual(call(PAYLOAD)[0], 200)
            self.client.error = TransportError('sensitive', diagnostic=error_diagnostic(status=402))
            status, body = call(PAYLOAD)
            self.assertEqual(status, 402)
            self.assertEqual(body['error']['code'], 'provider_credit_exhausted')
            self.assertNotIn('Budget admission', json.dumps(body))
            self.assertEqual(call(PAYLOAD)[0], 409)
            self.assertEqual(len(self.client.calls), 2)
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=3); session.close()


if __name__ == '__main__': unittest.main()

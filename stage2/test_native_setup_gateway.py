import os
from pathlib import Path
import tempfile
import unittest
import json
import hashlib
from decimal import Decimal
from unittest.mock import patch

from budget_ledger import Ledger, BudgetExceeded, dollars
from gateway_policy import MODEL
from model_protocol import ModelSettings
from native_setup_gateway import NativeSetupSession, scored_pending_liability, serve
from openrouter_transport import error_diagnostic
from native_setup_accounting import audit_setup
from test_scored_gateway import Client
from test_historical_hold import HoldFixture


class NativeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.runtime = self.root / '.runtime/stage2'
        self.runtime.mkdir(parents=True, mode=0o700)
        ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        ledger.close()
        os.chmod(self.runtime / 'setup_budget.sqlite', 0o600)
        self.client = Client()
        self.settings = ModelSettings(8192, 1., 'high')

    def tearDown(self): self.temp.cleanup()

    def session(self, name='setup-native-fixture1'):
        return NativeSetupSession(self.root, name, 'a' * 64, self.client, settings=self.settings, receipt_timing='inline')

    def request(self):
        return dict(model=MODEL, messages=[{'role': 'user', 'content': 'fixture'}],
                    max_tokens=8192, temperature=1., reasoning={'effort': 'high'})

    def test_shared_setup_spend_survives_session_and_no_scored_ledger(self):
        with self.session() as session:
            session.complete('a' * 64, self.request())
            self.assertEqual(session.ledger.ceiling, dollars('1'))
            self.assertIsNone(session.gateway.trial_estimate)
        with self.session('setup-native-fixture2') as session:
            self.assertEqual(session.ledger.exposure(), dollars('.001'))
        self.assertFalse((self.runtime / 'scored_budget.sqlite').exists())

    def test_missing_existing_ledger_cannot_create_new_allowance(self):
        (self.runtime / 'setup_budget.sqlite').unlink()
        with self.assertRaises(FileNotFoundError): self.session()
        self.assertEqual(self.client.calls, 0)

    def test_prior_setup_spend_is_not_reset(self):
        ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        ledger.reserve('earlier-setup', 'earlier-probe', '.95', '25', 'setup')
        ledger.settle('earlier-setup', '.95')
        ledger.close()
        with self.session() as session:
            with self.assertRaises(BudgetExceeded): session.complete('a' * 64, self.request())
            self.assertEqual(session.ledger.exposure(), dollars('.95'))
            self.assertEqual(session.budget_stop_sequence, 1)
        self.assertEqual(self.client.calls, 0)

    def test_unknown_outcome_blocks_later_session(self):
        self.client.fail = True
        with self.session() as session:
            with self.assertRaises(Exception): session.complete('a' * 64, self.request())
        with self.assertRaises(BudgetExceeded): self.session('setup-native-fixture2')
        self.assertEqual(self.client.calls, 1)

    def test_header_only_setup_interruption_retains_id_and_full_unknown_liability(self):
        def complete(request, *, on_response_headers):
            on_response_headers(error_diagnostic(status=200, headers={'X-Generation-Id': 'gen-setup-header'}))
            raise KeyboardInterrupt
        with self.session() as session, patch.object(self.client, 'complete', side_effect=complete) as dispatch:
            with self.assertRaises(KeyboardInterrupt): session.complete('a' * 64, self.request())
            pending = session.ledger.pending()
            self.assertEqual(pending[0][3], 'gen-setup-header')
            self.assertEqual(session.ledger.exposure(), pending[0][2])
            self.assertEqual(session.ledger.db.execute('SELECT charged,state FROM requests').fetchone(), (None, 'pending'))
            headers = json.loads((session.evidence / '000001.response-headers.json').read_text())
            self.assertEqual(headers['reservation_id'], pending[0][0])
            self.assertFalse((session.evidence / '000001.response.json').exists())
            self.assertTrue((session.evidence / '000001.interruption.json').exists())
            dispatch.assert_called_once()
        with self.assertRaises(BudgetExceeded): self.session('setup-native-blocked')
        from reconcile_pending import reconcile
        with patch.object(self.client, 'generation') as receipt:
            with self.assertRaisesRegex(ValueError, 'durable matching response'):
                reconcile(self.root, kind='setup', trial_id='setup-native-fixture1', client=self.client)
            receipt.assert_not_called()

    def test_service_passes_explicit_wait_and_interrupts_without_dispatch(self):
        from dataclasses import asdict
        token = self.root / 'token'
        token.write_text('a' * 64)
        token.chmod(0o600)
        settings = self.root / 'settings.json'
        settings.write_text(json.dumps(asdict(self.settings)))
        settings.chmod(0o600)
        sock = self.root / 'socket' / 'model.sock'
        with patch('openrouter_transport.load_key', return_value='synthetic-key'), \
             patch('openrouter_transport.OpenRouter', return_value=self.client) as transport, \
             patch('gateway_http.UnixHTTPServer.serve_forever', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                serve(self.root, 'setup-native-service', token, self.root / 'credential', sock,
                      settings, completion_wait_seconds=360)
            transport.assert_called_once_with('synthetic-key', generation_enabled=True, completion_wait_seconds=360)
        self.assertFalse(sock.exists())
        self.assertEqual(self.client.calls, 0)

    def test_service_requires_valid_explicit_completion_wait_before_file_access(self):
        for value in (True, False, 0, -1, float('nan'), float('inf'), '360', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                serve(self.root, 'unused', 'missing', 'missing', 'missing', 'missing',
                      completion_wait_seconds=value)
        with self.assertRaises(TypeError):
            serve(self.root, 'unused', 'missing', 'missing', 'missing', 'missing')

    def test_finished_session_cannot_replay(self):
        with self.session(): pass
        with self.assertRaises(FileExistsError): self.session()

    def test_settings_drift_rejected_without_generation(self):
        with self.session() as session:
            request = self.request()
            request['temperature'] = 0
            with self.assertRaises(ValueError): session.complete('a' * 64, request)
        self.assertEqual(self.client.calls, 0)

    def held_scored_request(self):
        fixture = HoldFixture(self.root)
        self.addCleanup(fixture.close)
        path = self.runtime / 'scored_budget.sqlite'
        path.chmod(0o600)
        return path

    def test_unregistered_scored_unknown_blocks_setup(self):
        self.held_scored_request()
        (self.runtime / 'historical-hold-v1.json').unlink()
        with self.assertRaises(BudgetExceeded): self.session()
        self.assertEqual(self.client.calls, 0)

    def test_second_scored_unknown_blocks_setup_even_with_credit(self):
        path = self.held_scored_request()
        import sqlite3
        with sqlite3.connect(path) as db:
            db.execute("INSERT INTO requests VALUES ('second','new',106496000,NULL,'pending')")
        self.client.allowance = '12'
        with self.assertRaises(ValueError): self.session()
        self.assertEqual(self.client.calls, 0)

    def test_scored_unverified_receipt_blocks_setup(self):
        path = self.held_scored_request()
        import sqlite3
        with sqlite3.connect(path) as db:
            db.execute("INSERT INTO receipt_checks VALUES ('unverified','pending')")
        with self.assertRaises(ValueError): self.session()
        self.assertEqual(self.client.calls, 0)

    def test_setup_protects_separate_scored_hold_without_mutating_it(self):
        path = self.held_scored_request()
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        self.client.allowance = '2.15'
        with self.session() as session:
            with self.assertRaises(BudgetExceeded): session.complete('a' * 64, self.request())
        self.assertEqual(self.client.calls, 0)
        self.assertEqual(scored_pending_liability(self.runtime), Decimal('.106496'))
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), before)

    def test_separate_hold_is_deducted_exactly_once(self):
        self.held_scored_request()
        self.client.allowance = '2.22'
        with self.session() as session:
            session.complete('a' * 64, self.request())
        self.assertEqual(self.client.calls, 1)

    def test_scored_ledger_symlink_is_rejected_before_setup_call(self):
        path = self.held_scored_request()
        other = self.runtime / 'original-scored.sqlite'
        path.rename(other)
        path.symlink_to(other)
        with self.assertRaises(ValueError): self.session()
        self.assertEqual(self.client.calls, 0)

    def make_auditable_call(self):
        original = self.client.complete
        def complete(request, *, on_response_headers=None):
            response = original(request, on_response_headers=on_response_headers)
            response['usage'].update(prompt_tokens=10, completion_tokens=4)
            return response
        self.client.complete = complete
        with self.session() as session:
            session.complete('a' * 64, self.request())
            return session.evidence

    def test_readonly_audit_reconciles_receipts_and_usage(self):
        self.make_auditable_call()
        result = audit_setup(self.runtime, 'setup-native-fixture1', self.settings)
        self.assertTrue(result['billing_verified'])
        self.assertEqual(result['charged_usd'], '0.001')
        self.assertEqual(result['prompt_tokens'], 10)

    def test_audit_rejects_missing_receipt(self):
        evidence = self.make_auditable_call()
        (evidence / '000001.receipt.json').unlink()
        with self.assertRaises(ValueError): audit_setup(self.runtime, 'setup-native-fixture1', self.settings)

    def test_audit_rejects_wire_settings_drift(self):
        evidence = self.make_auditable_call()
        path = evidence / '000001.request.json'
        request = json.loads(path.read_text())
        request['temperature'] = 0
        path.write_text(json.dumps(request))
        with self.assertRaises(ValueError): audit_setup(self.runtime, 'setup-native-fixture1', self.settings)

    def test_audit_rejects_receipt_charge_drift(self):
        evidence = self.make_auditable_call()
        path = evidence / '000001.receipt.json'
        receipt = json.loads(path.read_text())
        receipt['total_cost'] = '.002'
        path.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError): audit_setup(self.runtime, 'setup-native-fixture1', self.settings)

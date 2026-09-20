import fcntl
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from budget_ledger import BudgetExceeded, Ledger, dollars
from deferred_billing import (register_policy, register_terminal_deferral, validate_deferrals,
    validate_terminal_deferral, unresolved_liability_nanodollars)
from gateway_core import GatewayError
from gateway_policy import MODEL
from model_protocol import ModelSettings, freeze_protocol
from native_setup_accounting import audit_setup
from native_setup_gateway import NativeSetupSession, scored_pending_liability
from scored_accounting import audit_trial
from scored_gateway import ScoredSession, durable_json, private_directory
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS
from test_scored_gateway import HoldClient


class DeferredBillingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.settings = ModelSettings(8192, 1., 'high')
        freeze_protocol(self.runtime, self.settings)
        ledger = Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        ledger.close()
        (self.runtime / 'setup_budget.sqlite').chmod(0o600)
        ledger = Ledger(self.runtime / 'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP, STAGE_CAPS,
                        allow_estimated_trials=True)
        ledger.close()
        (self.runtime / 'scored_budget.sqlite').chmod(0o600)
        self.client = HoldClient()
        self.payload = {'model': MODEL, 'messages': [{'role': 'user', 'content': 'fixture'}],
                        'max_tokens': 8192, 'temperature': 1., 'reasoning': {'effort': 'high'}}
        self.token = 'a' * 64

    def session(self, identifier, kind='setup', timing='post_trial'):
        if kind == 'setup':
            return NativeSetupSession(self.root, identifier, self.token, self.client,
                                      settings=self.settings, receipt_timing=timing)
        return ScoredSession(self.root, identifier, 'development', self.token, self.client,
            estimator=lambda _: '.01', settings=self.settings, receipt_timing=timing)

    def failed(self, *, kind='setup', receipt_missing=False):
        trial = 'setup-native-deferred' if kind == 'setup' else 'dev-terminus-2-06-example'
        self.client.fail = not receipt_missing
        with self.session(trial, kind) as session:
            if receipt_missing:
                session.complete(self.token, self.payload)
            else:
                with self.assertRaises(GatewayError): session.complete(self.token, self.payload)
            request_id = session.ledger.db.execute('SELECT id FROM requests WHERE trial=?', (trial,)).fetchone()[0]
        self.client.fail = False
        relative = Path('scored-trials') / trial / 'result.json'
        if kind == 'setup':
            relative = Path('native-live-fixture/.runtime/stage2') / relative
        path = self.runtime / relative
        parent = self.runtime
        for part in relative.parts[:-1]:
            parent = private_directory(parent / part)
        result = {'trial_id': trial, 'task_id': 'fixture', 'stage': 'development', 'harness': 'terminus-2',
            'model_protocol_sha256': self.settings.fingerprint(), 'status': 'billing_unresolved',
            'model_revoked': True, 'containers_removed': True, 'networks_removed': True,
            'volumes_removed': True, 'billing': {'billing_verified': False},
            'verifier_result': {'rewards': {'reward': 0}}}
        durable_json(path, result)
        return trial, request_id, path

    def register(self, kind='setup', *, receipt_missing=False):
        trial, request, path = self.failed(kind=kind, receipt_missing=receipt_missing)
        register_policy(self.runtime)
        entry = register_terminal_deferral(self.runtime, kind=kind, trial_id=trial, result_path=path)
        return trial, request, path, entry

    def ledger(self, kind='setup'):
        if kind == 'setup':
            return Ledger(self.runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'},
                          deferred_billing_runtime=self.runtime, deferred_billing_kind='setup')
        return Ledger(self.runtime / 'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP, STAGE_CAPS,
            allow_estimated_trials=True, historical_hold_runtime=self.runtime, deferred_billing_runtime=self.runtime)

    def test_active_pending_and_unregistered_closed_attempt_still_block(self):
        trial, _, path = self.failed()
        register_policy(self.runtime)
        with self.assertRaises(BudgetExceeded): self.session('setup-native-next')
        with self.assertRaises(BudgetExceeded): self.session(trial)
        self.assertFalse((self.runtime / 'deferred-billing').exists())

    def test_terminal_unknown_allows_different_trial_without_row_mutation(self):
        trial, request, path, entry = self.register()
        ledger = self.ledger()
        self.addCleanup(ledger.close)
        self.assertEqual(ledger.db.execute('SELECT charged,state FROM requests WHERE id=?', (request,)).fetchone(), (None, 'pending'))
        self.assertEqual(entry['reserved_nanodollars'], dollars('.106496'))
        self.assertEqual(ledger.exposure(), dollars('.106496'))
        self.assertEqual(ledger.blocking_pending(trial='new'), [])
        self.assertEqual(len(ledger.pending()), 1)
        with self.session('setup-native-next', timing='inline') as session:
            session.complete(self.token, self.payload)
        report = audit_setup(self.runtime, 'setup-native-next', self.settings)
        self.assertTrue(report['billing_verified'])
        self.assertEqual(report['charged_usd'], '0.001')
        deferred = audit_setup(self.runtime, trial, self.settings)
        self.assertFalse(deferred['billing_verified'])
        self.assertIsNone(deferred['charged_usd'])
        self.assertIsNone(deferred['requests'])
        self.assertEqual(validate_terminal_deferral(self.runtime, trial, json.loads(path.read_text()), kind='setup'), entry)

    def test_terminal_missing_receipt_retains_known_charge_and_full_exposure(self):
        trial, request, _, entry = self.register(receipt_missing=True)
        ledger = self.ledger(); self.addCleanup(ledger.close)
        self.assertEqual(ledger.db.execute('SELECT charged,state FROM requests WHERE id=?', (request,)).fetchone(), (dollars('.001'), 'settled'))
        self.assertEqual(entry['extra_reserved_nanodollars'], dollars('.105496'))
        self.assertEqual(entry['known_charged_nanodollars'], dollars('.001'))
        self.assertEqual(ledger.exposure(), dollars('.106496'))
        self.assertEqual(unresolved_liability_nanodollars(ledger.db, [entry]), dollars('.105496'))
        self.assertEqual(len(ledger.pending_receipts()), 1)
        self.assertEqual(ledger.blocking_receipts(trial='new'), [])
        self.assertFalse(audit_setup(self.runtime, trial, self.settings)['billing_verified'])
        with self.session('setup-native-next', timing='inline') as session:
            session.complete(self.token, self.payload)
        self.assertEqual(ledger.exposure(), dollars('.107496'))

    def test_same_terminal_trial_cannot_resume_or_reserve_again(self):
        trial, _, _, _ = self.register()
        ledger = self.ledger(); self.addCleanup(ledger.close)
        with self.assertRaises(BudgetExceeded): ledger.reserve('replacement', trial, '.106496', '12', 'setup')
        with self.assertRaises(BudgetExceeded): self.session(trial)

    def test_retained_unknown_and_receipt_liability_preserve_caps_and_reserve(self):
        self.register()
        ledger = self.ledger(); self.addCleanup(ledger.close)
        with self.assertRaises(BudgetExceeded): ledger.reserve('over', 'new', '.9', '12', 'setup')
        with self.assertRaises(BudgetExceeded): ledger.reserve('floor', 'new', '.1', '2.206495999', 'setup')

    def test_receipt_extra_liability_participates_in_account_and_aggregate_caps(self):
        self.register(receipt_missing=True)
        ledger = self.ledger(); self.addCleanup(ledger.close)
        with self.assertRaises(BudgetExceeded): ledger.reserve('over', 'new', '.9', '12', 'setup')
        with self.assertRaises(BudgetExceeded): ledger.reserve('floor', 'new', '.1', '2.205495999', 'setup')

    def test_scored_unknown_stage_and_trial_caps_remain_binding(self):
        trial, _, _, entry = self.register(kind='scored')
        ledger = self.ledger('scored'); self.addCleanup(ledger.close)
        self.assertFalse(audit_trial(self.runtime, trial, 'development')['billing_verified'])
        self.assertEqual(scored_pending_liability(self.runtime), __import__('decimal').Decimal('.106496'))
        with self.assertRaises(BudgetExceeded): ledger.reserve('stage', 'new', '2.7', '12', 'development', trial_estimate='.01')
        with self.assertRaises(BudgetExceeded): ledger.reserve('trial', 'new', '.1', '12', 'development', trial_estimate='.024')
        with self.session('new-scored', kind='scored', timing='inline') as session:
            session.complete(self.token, self.payload)
        self.assertTrue(audit_trial(self.runtime, 'new-scored', 'development')['billing_verified'])

    def test_unclosed_or_live_gateway_cannot_be_registered(self):
        trial, _, path = self.failed()
        register_policy(self.runtime)
        result = json.loads(path.read_text())
        result['model_revoked'] = False
        path.write_text(json.dumps(result))
        with self.assertRaisesRegex(ValueError, 'revocation'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)
        result['model_revoked'] = True; path.write_text(json.dumps(result))
        with (self.runtime / 'gateway.lock').open('r+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)

    def test_result_or_evidence_tampering_invalidates_deferral(self):
        _, _, path, _ = self.register()
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'changed'):
            validate_deferrals(self.runtime, kind='setup')

    def test_policy_missing_or_changed_never_authorises_deferral(self):
        trial, _, path = self.failed()
        with self.assertRaisesRegex(ValueError, 'registered first'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)
        policy = register_policy(self.runtime)
        from deferred_billing import POLICY
        doc = json.loads((self.runtime / POLICY).read_text()); doc['reserve_nanodollars'] = 0
        (self.runtime / POLICY).write_text(json.dumps(doc))
        with self.assertRaises(ValueError): validate_deferrals(self.runtime, kind='setup')

    def test_wrong_protocol_route_extra_evidence_and_small_reserve_reject(self):
        trial, request, path = self.failed()
        register_policy(self.runtime)
        evidence = self.runtime / 'native-setup-attempts' / trial
        request_path = evidence / '000001.request.json'
        original = request_path.read_bytes()
        wrong = json.loads(original); wrong['provider']['allow_fallbacks'] = True
        request_path.write_text(json.dumps(wrong))
        with self.assertRaisesRegex(ValueError, 'routing'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)
        request_path.write_bytes(original)
        durable_json(evidence / '000002.response.json', {'id': 'unledgered'})
        with self.assertRaisesRegex(ValueError, 'Unmapped'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)
        (evidence / '000002.response.json').unlink()
        with sqlite3.connect(self.runtime / 'setup_budget.sqlite') as db:
            db.execute('UPDATE requests SET reserved=1 WHERE id=?', (request,))
        with self.assertRaisesRegex(ValueError, 'full-context'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)

    def test_flat_transport_conflict_and_ledger_incident_remain_fatal(self):
        trial, request, path = self.failed()
        register_policy(self.runtime)
        evidence = self.runtime / 'native-setup-attempts' / trial
        durable_json(evidence / '000001.transport-error.json', {'identifier_conflict': True, 'generation_id': None})
        with self.assertRaisesRegex(ValueError, 'Conflicting'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)
        (evidence / '000001.transport-error.json').unlink()
        with sqlite3.connect(self.runtime / 'setup_budget.sqlite') as db:
            db.execute('INSERT INTO incidents VALUES (?,?)', (request, 999999999))
        with self.assertRaisesRegex(ValueError, 'incident'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)

    def test_orphan_receipt_is_blocking_with_or_without_active_trial(self):
        ledger = self.ledger(); self.addCleanup(ledger.close)
        ledger.db.execute("INSERT INTO receipt_checks VALUES ('orphan','pending')")
        self.assertEqual(len(ledger.blocking_receipts()), 1)
        self.assertEqual(len(ledger.blocking_receipts(trial='new')), 1)

    def test_new_active_unknown_is_not_implicitly_exempted_by_prior_deferral(self):
        self.register()
        self.client.fail = True
        with self.session('setup-native-second') as session:
            with self.assertRaises(GatewayError): session.complete(self.token, self.payload)
        self.client.fail = False
        with self.assertRaises(BudgetExceeded): self.session('setup-native-third')
        self.assertEqual(self.client.calls, 2)

    def test_scored_gateway_reserves_deferred_setup_liability_exactly_once(self):
        self.register()
        self.client.allowance = '2.212991999'
        with self.session('next-scored', kind='scored', timing='inline') as session:
            with self.assertRaises(BudgetExceeded): session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 1)
        self.client.allowance = '2.212992'
        with self.session('allowed-scored', kind='scored', timing='inline') as session:
            session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 2)

    def test_setup_gateway_reserves_scored_missing_receipt_extra_exactly_once(self):
        self.register(kind='scored', receipt_missing=True)
        self.client.allowance = '2.211991999'
        with self.session('setup-native-next') as session:
            with self.assertRaises(BudgetExceeded): session.complete(self.token, self.payload)
        self.client.allowance = '2.211992'
        with self.session('setup-native-allowed', timing='inline') as session:
            session.complete(self.token, self.payload)
        self.assertEqual(self.client.calls, 2)

    def test_self_consistent_wrong_protocol_cannot_be_registered(self):
        trial, _, path = self.failed()
        register_policy(self.runtime)
        for artifact in (path, self.runtime / 'native-setup-attempts' / trial / 'started.json'):
            value = json.loads(artifact.read_text()); value['model_protocol_sha256'] = 'b' * 64
            artifact.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'model protocol'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)

    def test_available_conflicting_receipt_cannot_be_deferred(self):
        trial, _, path = self.failed(receipt_missing=True)
        register_policy(self.runtime)
        evidence = self.runtime / 'native-setup-attempts' / trial
        response = json.loads((evidence / '000001.response.json').read_text())
        durable_json(evidence / '000001.receipt.json', dict(self.client.generation(response['id']), total_cost='.002'))
        with self.assertRaisesRegex(ValueError, 'Costs disagree'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)

    def test_standing_policy_requires_canonical_scored_ledger_before_setup(self):
        register_policy(self.runtime)
        (self.runtime / 'scored_budget.sqlite').unlink()
        with self.assertRaisesRegex(ValueError, 'canonical scored ledger'):
            self.session('setup-native-missing-ledger')
        self.assertEqual(self.client.calls, 0)

    def test_explicit_byok_response_remains_fatal_after_native_gateway_rejection(self):
        original = self.client.complete
        def byok_response(request, *, on_response_headers=None):
            self.client.fail = False
            response = original(request, on_response_headers=on_response_headers)
            response['usage']['is_byok'] = True
            return response
        self.client.complete = byok_response
        trial, request, path = self.failed()
        register_policy(self.runtime)
        with self.assertRaisesRegex(ValueError, 'Explicit BYOK'):
            register_terminal_deferral(self.runtime, kind='setup', trial_id=trial, result_path=path)
        with sqlite3.connect(self.runtime / 'setup_budget.sqlite') as db:
            self.assertEqual(db.execute('SELECT charged,state FROM requests WHERE id=?',
                                        (request,)).fetchone(), (None, 'pending'))
        self.assertFalse((self.runtime / 'deferred-billing').exists())

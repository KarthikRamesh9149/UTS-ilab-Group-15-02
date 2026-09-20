import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from historical_hold import canonical_hold_document, hold_entries, validate_historical_hold
from matrix_resume import completed_cell, validated_held_cell, validated_deferred_cell, HELD_TERMINAL, DEFERRED_TERMINAL
from model_protocol import ModelSettings


class DeferredCellFixture:
    """Portable real-registration fixture with no provider or mocked validator."""
    def __init__(self, root, cell, *, reward=0, settings=None):
        from budget_ledger import Ledger, dollars
        from deferred_billing import register_policy, register_terminal_deferral
        from gateway_policy import MODEL, prepare_request
        from model_protocol import freeze_protocol
        from scored_gateway import durable_json, private_directory
        from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS
        from setup_probe import full_context_bound
        self.root, self.cell = Path(root), dict(cell)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.settings = settings or ModelSettings(8192, 1., 'high')
        freeze_protocol(self.runtime, self.settings)
        self.policy = register_policy(self.runtime)
        identifier = cell['trial_id']
        self.original = dict(cell, status='billing_unresolved',
            model_protocol_sha256=self.settings.fingerprint(),
            model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
            cleanup_errors=[], verifier_error_type=None, agent_error_type='APIError',
            phase_seconds={'setup': .2, 'agent': 1., 'verifier': .3},
            billing={'billing_verified': False}, verifier_result={'rewards': {'reward': reward}},
            agent_context={'metadata': {'custom_parent': cell.get('parent')}})
        output = private_directory(private_directory(self.runtime / 'scored-trials') / identifier)
        self.result_path = output / 'result.json'
        durable_json(self.result_path, self.original)
        evidence = private_directory(private_directory(self.runtime / 'scored-attempts') / identifier)
        durable_json(evidence / 'started.json', {'trial_id': identifier, 'stage': cell['stage'],
            'model_protocol_sha256': self.settings.fingerprint()})
        request_id = 'fixture-pending-' + identifier
        durable_json(evidence / '000001.reservation.json', {'trial_id': identifier,
            'reservation_id': request_id, 'sequence': 1})
        request = self.settings.enforce(prepare_request({'model': MODEL, 'max_tokens': 64,
            'temperature': 1., 'reasoning': {'effort': 'high'},
            'messages': [{'role': 'user', 'content': 'Synthetic deferral fixture.'}]}))
        durable_json(evidence / '000001.request.json', request)
        self.reserved_nanodollars = dollars(full_context_bound(request))
        self.database = self.runtime / 'scored_budget.sqlite'
        ledger = Ledger(self.database, SCORED_CEILING, TRIAL_CAP, STAGE_CAPS, allow_estimated_trials=True)
        try:
            with ledger.transaction():
                ledger.db.execute('INSERT INTO trial_stages VALUES (?,?)', (identifier, cell['stage']))
                ledger.db.execute("INSERT INTO requests VALUES (?,?,?,NULL,'pending')",
                                  (request_id, identifier, self.reserved_nanodollars))
                ledger.db.execute('INSERT INTO trial_estimates VALUES (?,10000000)', (request_id,))
        finally:
            ledger.close()
        self.database.chmod(0o600)
        self.entry = register_terminal_deferral(self.runtime, kind='scored', trial_id=identifier,
                                               result_path=self.result_path)

    def view(self):
        return completed_cell(self.root, self.cell, self.settings)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = ModelSettings(64, 1., 'high')
        self.cell = dict(trial_id='final-custom-00-task', task_id='task', stage='final', harness='C2', parent='C1')
        self.path = self.root / '.runtime/stage2/scored-trials' / self.cell['trial_id'] / 'result.json'
        self.row = dict(self.cell, status='verified', model_protocol_sha256=self.settings.fingerprint(),
            model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
            verifier_result={'rewards': {'reward': 0}}, agent_context={'metadata': {'custom_parent': 'C1'}})
        self.billing = {'billing_verified': True, 'model_protocol_sha256': self.settings.fingerprint()}

    def write(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.row))

    def test_missing_cell_does_not_call_billing(self):
        with patch('matrix_resume.audit_trial') as audit:
            self.assertIsNone(completed_cell(self.root, self.cell, self.settings))
            audit.assert_not_called()

    def test_zero_result_retained_and_reaudited(self):
        self.write()
        with patch('matrix_resume.audit_trial', return_value=self.billing) as audit:
            result = completed_cell(self.root, self.cell, self.settings)
            self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
            audit.assert_called_once()

    def test_existing_interrupted_attempt_blocks(self):
        self.path.parent.mkdir(parents=True)
        with self.assertRaises(RuntimeError): completed_cell(self.root, self.cell, self.settings)

    def test_identity_and_parent_mismatch_rejected(self):
        for key in ('task_id', 'harness', 'model_protocol_sha256'):
            original = self.row[key]
            self.row[key] = 'wrong'
            self.write()
            with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)
            self.row[key] = original
        self.row['agent_context']['metadata']['custom_parent'] = 'C0'
        self.write()
        with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)

    def test_invalid_reward_and_cleanup_rejected(self):
        self.row['verifier_result']['rewards']['reward'] = True
        self.write()
        with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)
        self.row['verifier_result']['rewards']['reward'] = 0
        self.row['containers_removed'] = False
        self.write()
        with self.assertRaises(RuntimeError): completed_cell(self.root, self.cell, self.settings)

    def test_billing_failure_blocks_resume(self):
        self.write()
        with patch('matrix_resume.audit_trial', side_effect=ValueError('unresolved')):
            with self.assertRaises(ValueError): completed_cell(self.root, self.cell, self.settings)

    def install_hold(self):
        hold = canonical_hold_document()
        hold.update(model_protocol_sha256=self.settings.fingerprint(), sidecar_sha256='c' * 64,
            budget_stop_count=2, budget_stop_classification='historical_pending_barrier',
            capacity_budget_stop_count=0)
        self.cell = {key: hold[key] for key in ('trial_id', 'task_id', 'stage', 'harness')}
        self.row.update(self.cell, status='billing_unresolved', billing={'billing_verified': False})
        self.row.pop('parent', None)
        self.path = self.root / '.runtime/stage2/scored-trials' / self.cell['trial_id'] / 'result.json'
        self.write()
        hold['original_result_sha256'] = hashlib.sha256(self.path.read_bytes()).hexdigest()
        validator = patch('matrix_resume.validate_historical_hold', return_value=hold)
        validator.start()
        self.addCleanup(validator.stop)
        return hold

    def test_historical_zero_has_terminal_disposition_without_billing_imputation(self):
        self.install_hold()
        before = self.path.read_bytes()
        with patch('matrix_resume.audit_trial') as audit:
            row = completed_cell(self.root, self.cell, self.settings)
            audit.assert_not_called()
        self.assertEqual(row['resume_disposition'], HELD_TERMINAL)
        self.assertEqual(row['status'], 'billing_unresolved')
        self.assertEqual(row['verifier_result']['rewards']['reward'], 0)
        self.assertIs(row['billing']['billing_verified'], False)
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.assertIsNone(row['billing'][field])
        self.assertEqual(row['billing']['budget_stop_count'], 2)
        self.assertEqual(row['billing']['capacity_budget_stop_count'], 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertIsNotNone(validated_held_cell(self.root / '.runtime/stage2', row, self.settings.fingerprint()))

    def test_historical_view_rejects_imputed_usage_or_modified_outcome(self):
        self.install_hold()
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            row = completed_cell(self.root, self.cell, self.settings)
            row['billing'][field] = 0
            with self.subTest(field=field), self.assertRaises(ValueError):
                validated_held_cell(self.root / '.runtime/stage2', row, self.settings.fingerprint())
        row = completed_cell(self.root, self.cell, self.settings)
        row['verifier_result']['rewards']['reward'] = 1
        with self.assertRaises(ValueError):
            validated_held_cell(self.root / '.runtime/stage2', row, self.settings.fingerprint())

    def test_historical_cell_cannot_be_replayed_with_substitute_identity(self):
        self.install_hold()
        substitute = dict(self.cell, trial_id=self.cell['trial_id'] + '-replacement')
        with self.assertRaisesRegex(ValueError, 'substitute'):
            completed_cell(self.root, substitute, self.settings)
        self.path.unlink()
        self.path.parent.rmdir()
        with self.assertRaisesRegex(ValueError, 'replay forbidden'):
            completed_cell(self.root, self.cell, self.settings)

    def test_hold_does_not_accept_another_unresolved_trial(self):
        self.install_hold()
        self.cell = dict(self.cell, trial_id='dev-terminus-2-01-other', task_id='other')
        self.row.update(self.cell)
        self.path = self.root / '.runtime/stage2/scored-trials' / self.cell['trial_id'] / 'result.json'
        self.write()
        with self.assertRaises(RuntimeError):
            completed_cell(self.root, self.cell, self.settings)

    def test_invalid_historical_evidence_blocks_even_missing_future_cell(self):
        with patch('matrix_resume.validate_historical_hold', side_effect=ValueError('Another unresolved dispatch')):
            with self.assertRaisesRegex(ValueError, 'unresolved'):
                completed_cell(self.root, self.cell, self.settings)


class TwoHoldResumeTests(unittest.TestCase):
    def setUp(self):
        from test_historical_hold import HoldFixtureV2
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture = HoldFixtureV2(temporary.name)
        self.addCleanup(self.fixture.close)
        self.root, self.runtime, self.settings = self.fixture.root, self.fixture.runtime, self.fixture.settings
        self.registry = validate_historical_hold(self.runtime)
        self.holds = hold_entries(self.registry)
        self.assertEqual(len(self.holds), 2)

    @staticmethod
    def cell(hold):
        return {key: hold[key] for key in ('trial_id', 'task_id', 'stage', 'harness')}

    def test_both_exact_held_zeros_retain_original_bytes_and_unknown_billing(self):
        for hold in self.holds:
            with self.subTest(trial=hold['trial_id']):
                path = self.fixture.results[hold['trial_id']]
                before = path.read_bytes()
                with patch('matrix_resume.audit_trial') as audit:
                    row = completed_cell(self.root, self.cell(hold), self.settings)
                    audit.assert_not_called()
                self.assertEqual(row['resume_disposition'], HELD_TERMINAL)
                self.assertEqual(row['status'], 'billing_unresolved')
                self.assertEqual(row['verifier_result']['rewards']['reward'], 0)
                self.assertIs(row['billing']['billing_verified'], False)
                for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
                    self.assertIsNone(row['billing'][field])
                self.assertEqual(row['historical_hold_sha256'], self.registry['sidecar_sha256'])
                self.assertEqual(row['original_result_sha256'], hold['original_result_sha256'])
                self.assertEqual(row['billing']['retained_reservation_nanodollars'], hold['reserved_nanodollars'])
                self.assertEqual(validated_held_cell(self.runtime, row, self.settings.fingerprint()), hold)
                self.assertEqual(path.read_bytes(), before)

    def test_neither_held_cell_can_use_a_substitute_trial_id(self):
        for hold in self.holds:
            substitute = dict(self.cell(hold), trial_id=hold['trial_id'] + '-replacement')
            with self.subTest(trial=hold['trial_id']), self.assertRaisesRegex(ValueError, 'substitute'):
                completed_cell(self.root, substitute, self.settings)
            self.assertFalse((self.runtime / 'scored-trials' / substitute['trial_id']).exists())

    def test_either_original_result_tamper_blocks_future_resume_without_replay(self):
        future = dict(trial_id='dev-C0-00-future', task_id='future', stage='development', harness='C0')
        for hold in self.holds:
            path = self.fixture.results[hold['trial_id']]
            before = path.read_bytes()
            try:
                path.write_bytes(before + b'\n')
                with self.subTest(trial=hold['trial_id']), self.assertRaises(ValueError):
                    completed_cell(self.root, future, self.settings)
            finally:
                path.write_bytes(before)
        self.assertFalse((self.runtime / 'scored-trials' / future['trial_id']).exists())

    def test_held_result_byte_hash_is_rechecked_after_registry_validation(self):
        for hold in self.holds:
            cell = self.cell(hold)
            row = completed_cell(self.root, cell, self.settings)
            path = self.fixture.results[hold['trial_id']]
            before = path.read_bytes()
            try:
                path.write_bytes(before + b'\n')
                with patch('matrix_resume.validate_historical_hold', return_value=self.registry):
                    with self.subTest(trial=hold['trial_id']), self.assertRaisesRegex(ValueError, 'changed after validation'):
                        completed_cell(self.root, cell, self.settings)
                    with self.assertRaisesRegex(ValueError, 'changed after validation'):
                        validated_held_cell(self.runtime, row, self.settings.fingerprint())
            finally:
                path.write_bytes(before)

    def test_neither_held_view_allows_cost_usage_or_outcome_imputation(self):
        for hold in self.holds:
            for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
                row = completed_cell(self.root, self.cell(hold), self.settings)
                row['billing'][field] = 0
                with self.subTest(trial=hold['trial_id'], field=field), self.assertRaises(ValueError):
                    validated_held_cell(self.runtime, row, self.settings.fingerprint())
            row = completed_cell(self.root, self.cell(hold), self.settings)
            row['verifier_result']['rewards']['reward'] = 1
            with self.assertRaises(ValueError):
                validated_held_cell(self.runtime, row, self.settings.fingerprint())

    def test_held_view_cannot_select_other_registered_trial_evidence(self):
        row = completed_cell(self.root, self.cell(self.holds[0]), self.settings)
        row['trial_id'] = self.holds[1]['trial_id']
        with self.assertRaises(ValueError):
            validated_held_cell(self.runtime, row, self.settings.fingerprint())
        row['trial_id'] = 'unregistered-hold'
        with self.assertRaisesRegex(ValueError, 'not registered'):
            validated_held_cell(self.runtime, row, self.settings.fingerprint())

    def test_two_hold_registry_does_not_admit_a_third_unresolved_result(self):
        row = json.loads(self.fixture.results[self.holds[0]['trial_id']].read_text())
        row.update(trial_id='dev-terminus-2-06-third', task_id='third')
        path = self.runtime / 'scored-trials' / row['trial_id'] / 'result.json'
        path.parent.mkdir(mode=0o700)
        path.write_text(json.dumps(row))
        with self.assertRaises(RuntimeError):
            completed_cell(self.root, self.cell(row), self.settings)


class DeferredResumeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture = DeferredCellFixture(temporary.name,
            dict(trial_id='dev-C0-00-synthetic', task_id='synthetic', stage='development', harness='C0'), reward=1)

    def test_registered_terminal_reward_preserved_without_unknown_billing_imputation(self):
        fixture = self.fixture
        before = fixture.result_path.read_bytes()
        with patch('matrix_resume.audit_trial') as audit:
            row = fixture.view()
            audit.assert_not_called()
        self.assertEqual(row['resume_disposition'], DEFERRED_TERMINAL)
        self.assertEqual(row['verifier_result']['rewards']['reward'], 1)
        self.assertEqual(row['status'], 'billing_unresolved')
        self.assertIs(row['billing']['billing_verified'], False)
        for key in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.assertIsNone(row['billing'][key])
        self.assertEqual(row['billing']['retained_reservation_nanodollars'], fixture.reserved_nanodollars)
        self.assertEqual(validated_deferred_cell(fixture.runtime, row, fixture.settings.fingerprint()), fixture.entry)
        self.assertEqual(fixture.result_path.read_bytes(), before)

    def test_registered_result_cannot_replay_or_invent_complete_metrics(self):
        fixture = self.fixture
        with self.assertRaisesRegex(ValueError, 'substitute'):
            completed_cell(fixture.root, dict(fixture.cell, trial_id='replacement'), fixture.settings)
        for key in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            row = fixture.view()
            row['billing'][key] = 0
            with self.subTest(key=key), self.assertRaises(ValueError):
                validated_deferred_cell(fixture.runtime, row, fixture.settings.fingerprint())

    def test_result_tamper_missing_registration_and_missing_runtime_reject(self):
        from deferred_billing import DIRECTORY
        fixture = self.fixture
        row = fixture.view()
        with self.assertRaises(ValueError): validated_deferred_cell(None, row, fixture.settings.fingerprint())
        original = fixture.result_path.read_bytes()
        fixture.result_path.write_bytes(original + b'\n')
        with self.assertRaises(ValueError): fixture.view()
        fixture.result_path.write_bytes(original)
        (fixture.runtime / DIRECTORY / ('scored--' + fixture.cell['trial_id'] + '.json')).unlink()
        with self.assertRaises(ValueError): validated_deferred_cell(fixture.runtime, row, fixture.settings.fingerprint())

    def test_cleanup_infrastructure_or_invalid_reward_never_become_terminal(self):
        from matrix_resume import _deferred_view
        fixture = self.fixture
        for key, value in [('status', 'infrastructure_failed'), ('containers_removed', False),
                           ('cleanup_errors', ['failure']), ('verifier_error_type', 'RuntimeError')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                _deferred_view(dict(fixture.original, **{key: value}), fixture.entry)
        for reward in (True, 2, None):
            changed = dict(fixture.original, verifier_result={'rewards': {'reward': reward}})
            with self.subTest(reward=reward), self.assertRaises(ValueError):
                _deferred_view(changed, fixture.entry)

    def test_own_trial_audit_is_explicitly_incomplete_and_keeps_stage_binding(self):
        from scored_accounting import audit_trial
        fixture = self.fixture
        result = audit_trial(fixture.runtime, fixture.cell['trial_id'], 'development')
        self.assertIs(result['billing_verified'], False)
        self.assertIsNone(result['charged_usd'])
        with self.assertRaisesRegex(ValueError, 'stage'):
            audit_trial(fixture.runtime, fixture.cell['trial_id'], 'final')

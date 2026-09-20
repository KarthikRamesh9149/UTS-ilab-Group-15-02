import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from historical_hold import canonical_hold_document
from matrix_resume import completed_cell
from qualification_gate import evaluate


class StandingGateFixture:
    """Real two-hold registry plus a new independently registered deferral."""
    def __init__(self, root):
        from test_historical_hold import HoldFixtureV2
        from test_matrix_resume import DeferredCellFixture
        from historical_hold import hold_entries, validate_historical_hold
        self.held = HoldFixtureV2(root)
        self.root, self.runtime, self.settings = self.held.root, self.held.runtime, self.held.settings
        self.tasks = [f'synthetic-{i}' for i in range(20)]
        holds = hold_entries(validate_historical_hold(self.runtime))
        for hold in holds:
            index = int(hold['trial_id'].split('-')[3])
            self.tasks[index] = hold['task_id']
        self.rows = []
        for index, task in enumerate(self.tasks):
            cell = dict(trial_id=f'dev-terminus-2-{index:02d}-{task}', task_id=task,
                        harness='terminus-2', stage='development')
            if any(entry['trial_id'] == cell['trial_id'] for entry in holds):
                row = completed_cell(self.root, cell, self.settings)
            else:
                row = dict(cell, model_protocol_sha256=self.settings.fingerprint(), status='verified',
                    model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
                    verifier_result={'rewards': {'reward': 0}},
                    billing={'billing_verified': True, 'model_protocol_sha256': self.settings.fingerprint(),
                        'charged_usd': '.001', 'prompt_tokens': 10, 'completion_tokens': 2, 'requests': 1,
                        'budget_stop_count': 0})
            self.rows.append(row)
        self.deferred = DeferredCellFixture(self.root,
            {key: self.rows[7][key] for key in ('trial_id', 'task_id', 'stage', 'harness')},
            reward=1, settings=self.settings)
        self.rows[7] = self.deferred.view()

    def evaluate(self, rows=None, *, reviewed=True):
        return evaluate(self.rows if rows is None else rows, task_ids=self.tasks,
            protocol_sha256=self.settings.fingerprint(), systemic_review_clear=reviewed, runtime=self.runtime)

    def close(self):
        self.held.close()


class QualificationGateTests(unittest.TestCase):
    def setUp(self):
        self.tasks = ['synthetic-' + str(i) for i in range(20)]
        self.fingerprint = 'a' * 64
        self.runtime = None
        self.rows = [{'task_id': task, 'harness': 'terminus-2', 'stage': 'development',
            'model_protocol_sha256': self.fingerprint, 'status': 'verified', 'model_revoked': True,
            'containers_removed': True, 'networks_removed': True, 'volumes_removed': True,
            'verifier_result': {'rewards': {'reward': int(i < 10)}},
            'billing': {'billing_verified': True, 'model_protocol_sha256': self.fingerprint,
                'budget_stop_count': int(i < 2), 'requests': 2, 'prompt_tokens': 100,
                'completion_tokens': 50, 'charged_usd': '.002'}} for i, task in enumerate(self.tasks)]

    def evaluate(self, rows=None, reviewed=True):
        return evaluate(self.rows if rows is None else rows, task_ids=self.tasks,
                        protocol_sha256=self.fingerprint, systemic_review_clear=reviewed, runtime=self.runtime)

    def install_hold(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.runtime = root / '.runtime/stage2'
        hold = canonical_hold_document()
        hold.update(model_protocol_sha256=self.fingerprint, sidecar_sha256='c' * 64,
            budget_stop_count=2, budget_stop_classification='historical_pending_barrier',
            capacity_budget_stop_count=0)
        self.tasks[0] = hold['task_id']
        cell = {key: hold[key] for key in ('trial_id', 'task_id', 'harness', 'stage')}
        original = dict(copy.deepcopy(self.rows[0]), **cell, status='billing_unresolved',
                        billing={'billing_verified': False}, verifier_result={'rewards': {'reward': 0}})
        path = self.runtime / 'scored-trials' / hold['trial_id'] / 'result.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(original))
        hold['original_result_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        validator = patch('matrix_resume.validate_historical_hold', return_value=hold)
        validator.start()
        self.addCleanup(validator.stop)
        self.rows[0] = completed_cell(root, cell, SimpleNamespace(fingerprint=lambda: self.fingerprint))
        self.rows[10]['verifier_result']['rewards']['reward'] = 1
        self.rows[2]['billing']['budget_stop_count'] = 1
        return hold

    def test_exact_threshold_and_no_mutation(self):
        before = copy.deepcopy(self.rows)
        result = self.evaluate()
        self.assertTrue(result['paid_expansion_allowed'])
        self.assertEqual(result['verified_successes'], 10)
        self.assertEqual(result['budget_exhausted_trials'], 2)
        self.assertEqual(before, self.rows)

    def test_nine_successes_do_not_pass(self):
        self.rows[0]['verifier_result']['rewards']['reward'] = 0
        self.assertIn('fewer_than_ten_successes', self.evaluate()['reasons'])

    def test_three_exhausted_trials_do_not_pass(self):
        self.rows[3]['billing']['budget_stop_count'] = 5
        self.assertEqual(self.evaluate()['budget_exhausted_trials'], 3)
        self.assertFalse(self.evaluate()['paid_expansion_allowed'])

    def test_missing_duplicate_and_wrong_condition_fail(self):
        self.assertFalse(self.evaluate(self.rows[:-1])['paid_expansion_allowed'])
        self.rows[-1] = copy.deepcopy(self.rows[0])
        self.assertFalse(self.evaluate()['paid_expansion_allowed'])
        self.rows[0]['harness'] = 'openhands'
        self.assertIn('wrong_condition', self.evaluate()['reasons'])

    def test_review_is_required_even_with_passes(self):
        self.assertIn('systemic_failure_review_required', self.evaluate(reviewed=False)['reasons'])

    def test_unknown_billing_usage_or_cleanup_never_pass(self):
        for field, value in [('prompt_tokens', None), ('billing_verified', False),
                             ('budget_stop_count', None), ('charged_usd', 'NaN')]:
            rows = copy.deepcopy(self.rows)
            rows[0]['billing'][field] = value
            with self.subTest(field=field):
                self.assertFalse(self.evaluate(rows)['paid_expansion_allowed'])
        self.rows[0]['containers_removed'] = False
        self.assertFalse(self.evaluate()['paid_expansion_allowed'])

    def test_reward_booleans_and_protocol_drift_rejected(self):
        self.rows[0]['verifier_result']['rewards']['reward'] = True
        self.rows[1]['model_protocol_sha256'] = 'b' * 64
        result = self.evaluate()
        self.assertIn('invalid_verifier_reward', result['reasons'])
        self.assertIn('model_protocol_mismatch', result['reasons'])

    def test_amendment_retains_original_gate_failure_and_fixed_zero_denominator(self):
        self.install_hold()
        before = copy.deepcopy(self.rows)
        result = self.evaluate()
        self.assertFalse(result['paid_expansion_allowed'])
        self.assertFalse(result['original_billing_completeness_satisfied'])
        self.assertTrue(result['accounting_bounded_expansion_allowed'])
        self.assertEqual(result['status'], 'accounting_bounded_expansion_allowed')
        self.assertEqual(result['verified_successes'], 10)
        self.assertEqual(result['expected_trials'], 20)
        self.assertEqual(result['observed_trials'], 20)
        self.assertEqual(result['budget_exhausted_trials'], 2)
        self.assertEqual(result['historical_pending_barrier_markers'], 2)
        self.assertEqual(result['budget_stop_markers'], 4)
        self.assertFalse(result['actual_charge_and_token_totals_complete'])
        self.assertIn('billing_unverified', result['reasons'])
        self.assertIn('usage_missing', result['reasons'])
        self.assertEqual(before, self.rows)

    def test_historical_hold_does_not_relax_success_stop_or_review_thresholds(self):
        self.install_hold()
        self.assertFalse(self.evaluate(reviewed=False)['accounting_bounded_expansion_allowed'])
        self.rows[10]['verifier_result']['rewards']['reward'] = 0
        result = self.evaluate()
        self.assertFalse(result['accounting_bounded_expansion_allowed'])
        self.assertIn('fewer_than_ten_successes', result['accounting_bounded_reasons'])
        self.rows[10]['verifier_result']['rewards']['reward'] = 1
        self.rows[3]['billing']['budget_stop_count'] = 1
        result = self.evaluate()
        self.assertFalse(result['accounting_bounded_expansion_allowed'])
        self.assertIn('more_than_two_budget_stops', result['accounting_bounded_reasons'])

    def test_hold_must_match_evidence_and_never_imputes_missing_charge(self):
        self.install_hold()
        for field, value in [('charged_usd', '0'), ('prompt_tokens', 0),
                             ('billing_verified', True), ('completion_tokens', 0)]:
            rows = copy.deepcopy(self.rows)
            rows[0]['billing'][field] = value
            with self.subTest(field=field):
                result = self.evaluate(rows)
                self.assertFalse(result['accounting_bounded_expansion_allowed'])
                self.assertIn('historical_hold_invalid', result['reasons'])
        self.runtime = None
        self.assertFalse(self.evaluate()['accounting_bounded_expansion_allowed'])

    def test_no_replacement_or_second_unresolved_trial_can_use_hold(self):
        self.install_hold()
        rows = copy.deepcopy(self.rows)
        rows[0]['trial_id'] += '-replacement'
        self.assertFalse(self.evaluate(rows)['accounting_bounded_expansion_allowed'])
        self.rows[1]['status'] = 'billing_unresolved'
        self.rows[1]['billing']['billing_verified'] = False
        self.assertFalse(self.evaluate()['accounting_bounded_expansion_allowed'])
        self.assertFalse(self.evaluate(self.rows[1:])['accounting_bounded_expansion_allowed'])

    def install_completion_amendment(self):
        first = self.install_hold()
        second = dict(first, trial_id='dev-terminus-2-05-reshard-c4-data',
            task_id='reshard-c4-data', request_id='5464bb2d-0767-42ff-86d7-66b11ab737ad',
            budget_stop_count=0, budget_stop_classification='no_budget_stop')
        self.tasks[5] = second['task_id']
        cell = {key: second[key] for key in ('trial_id', 'task_id', 'harness', 'stage')}
        original = dict(copy.deepcopy(self.rows[5]), **cell, status='billing_unresolved',
                        billing={'billing_verified': False}, verifier_result={'rewards': {'reward': 0}})
        path = self.runtime / 'scored-trials' / second['trial_id'] / 'result.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(original))
        second['original_result_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        document = {'schema_version': 2, 'sidecar_sha256': first['sidecar_sha256'],
                    'model_protocol_sha256': self.fingerprint, 'holds': [first, second]}
        for target in ('matrix_resume.validate_historical_hold', 'qualification_gate.validate_historical_hold'):
            validator = patch(target, return_value=document)
            validator.start()
            self.addCleanup(validator.stop)
        self.rows[5] = completed_cell(self.runtime.parent.parent, cell,
                                     SimpleNamespace(fingerprint=lambda: self.fingerprint))
        for row in self.rows:
            row['verifier_result']['rewards']['reward'] = 0
        self.rows[3]['billing']['budget_stop_count'] = 1
        return document

    def test_completion_amendment_retains_original_failure_without_performance_stop(self):
        document = self.install_completion_amendment()
        before = copy.deepcopy(self.rows)
        result = self.evaluate()
        self.assertFalse(result['paid_expansion_allowed'])
        self.assertFalse(result['accounting_bounded_expansion_allowed'])
        self.assertFalse(result['original_performance_gate_satisfied'])
        self.assertFalse(result['actual_charge_and_token_totals_complete'])
        self.assertTrue(result['completion_amendment_expansion_allowed'])
        self.assertEqual(result['status'], 'completion_amendment_expansion_allowed')
        self.assertEqual(result['verified_successes'], 0)
        self.assertEqual(result['budget_exhausted_trials'], 3)
        self.assertEqual(result['held_terminal_trials'], 2)
        self.assertEqual(result['historical_hold_sha256'], document['sidecar_sha256'])
        self.assertEqual(result['completion_amendment_sha256'], document['sidecar_sha256'])
        self.assertEqual(result['completion_amendment_reasons'], [])
        self.assertIn('fewer_than_ten_successes', result['reasons'])
        self.assertIn('more_than_two_budget_stops', result['reasons'])
        self.assertIn('more_than_one_historical_hold', result['reasons'])
        self.assertEqual(before, self.rows)

    def test_completion_amendment_requires_complete_fixed_set_and_systemic_review(self):
        self.install_completion_amendment()
        for rows, reviewed in ((self.rows[:6], True), (self.rows, False),
                               (self.rows[:-1] + [copy.deepcopy(self.rows[1])], True)):
            with self.subTest(observed=len(rows), reviewed=reviewed):
                self.assertFalse(self.evaluate(rows, reviewed)['completion_amendment_expansion_allowed'])

    def test_completion_amendment_does_not_relax_new_billing_cleanup_or_protocol(self):
        self.install_completion_amendment()
        for field, value in [('billing_verified', False), ('charged_usd', None),
                             ('charged_usd', '0.024'), ('requests', None), ('budget_stop_count', None)]:
            rows = copy.deepcopy(self.rows)
            rows[1]['billing'][field] = value
            with self.subTest(field=field, value=value):
                self.assertFalse(self.evaluate(rows)['completion_amendment_expansion_allowed'])
        for field, value in [('containers_removed', False), ('model_revoked', False),
                             ('model_protocol_sha256', 'b' * 64), ('harness', 'openhands')]:
            rows = copy.deepcopy(self.rows)
            rows[1][field] = value
            with self.subTest(field=field):
                self.assertFalse(self.evaluate(rows)['completion_amendment_expansion_allowed'])

    def test_completion_amendment_requires_exact_registered_v2_and_both_held_views(self):
        document = self.install_completion_amendment()
        for validated in (None, document['holds'][0], dict(document, sidecar_sha256='d' * 64),
                          dict(document, model_protocol_sha256='d' * 64)):
            with patch('qualification_gate.validate_historical_hold', return_value=validated):
                self.assertFalse(self.evaluate()['completion_amendment_expansion_allowed'])
        with patch('qualification_gate.validate_historical_hold', side_effect=ValueError('third unresolved call')):
            self.assertFalse(self.evaluate()['completion_amendment_expansion_allowed'])
        rows = copy.deepcopy(self.rows)
        rows[5]['billing']['charged_usd'] = '0'
        self.assertFalse(self.evaluate(rows)['completion_amendment_expansion_allowed'])
        self.assertFalse(self.evaluate(self.rows[:5] + self.rows[6:])['completion_amendment_expansion_allowed'])


class StandingDeferralGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.fixture = StandingGateFixture(temp.name)
        self.addCleanup(self.fixture.close)

    def test_registered_deferral_allows_completion_without_claiming_billing_or_performance_pass(self):
        fixture = self.fixture
        result = fixture.evaluate()
        self.assertTrue(result['billing_deferral_expansion_allowed'])
        self.assertEqual(result['status'], 'billing_deferral_expansion_allowed')
        self.assertFalse(result['paid_expansion_allowed'])
        self.assertFalse(result['original_billing_completeness_satisfied'])
        self.assertFalse(result['original_performance_gate_satisfied'])
        self.assertEqual(result['verified_successes'], 1)
        self.assertEqual(result['held_terminal_trials'], 2)
        self.assertEqual(result['billing_deferred_trials'], 1)
        self.assertEqual(result['deferred_billing_result_registrations'],
                         {fixture.deferred.cell['trial_id']: fixture.deferred.entry['sidecar_sha256']})
        self.assertEqual(result['billing_deferral_reasons'], [])

    def test_standing_policy_does_not_allow_unregistered_uncertainty_or_bad_cleanup(self):
        fixture = self.fixture
        for altered in [dict(fixture.rows[8], status='billing_unresolved', billing={'billing_verified': False}),
                        dict(fixture.rows[8], containers_removed=False)]:
            rows = copy.deepcopy(fixture.rows)
            rows[8] = altered
            self.assertFalse(fixture.evaluate(rows)['billing_deferral_expansion_allowed'])
        self.assertFalse(fixture.evaluate(reviewed=False)['billing_deferral_expansion_allowed'])

    def test_standing_policy_or_deferral_tamper_is_not_a_flag_bypass(self):
        fixture = self.fixture
        rows = copy.deepcopy(fixture.rows)
        rows[7]['billing']['charged_usd'] = '0'
        self.assertFalse(fixture.evaluate(rows)['billing_deferral_expansion_allowed'])
        from deferred_billing import POLICY
        (fixture.runtime / POLICY).write_text('{}')
        self.assertFalse(fixture.evaluate()['billing_deferral_expansion_allowed'])

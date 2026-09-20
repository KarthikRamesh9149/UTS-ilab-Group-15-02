import copy
from decimal import Decimal
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from final_analysis import analyze, paired
from final_schedule import schedule
from matrix_resume import DEFERRED_TERMINAL


def deferred_view(row, *, reward=0, known=3_000_000, retained=20_000_000):
    """Consumer fixture; canonical registry validation is patched only by callers."""
    entry = {key: row[key] for key in
             ('trial_id', 'task_id', 'stage', 'harness', 'model_protocol_sha256')}
    entry.update(known_charged_nanodollars=known, retained_liability_nanodollars=retained,
                 reserved_nanodollars=retained + known, budget_stop_count=2,
                 sidecar_sha256='a' * 64, original_result_sha256='b' * 64,
                 policy_sha256='c' * 64)
    row.update(status='billing_unresolved', resume_disposition=DEFERRED_TERMINAL,
               billing_deferred=True, deferred_billing_sha256=entry['sidecar_sha256'],
               original_result_sha256=entry['original_result_sha256'],
               billing_deferral_policy_sha256=entry['policy_sha256'])
    row['verifier_result']['rewards']['reward'] = reward
    row['billing'].update(billing_verified=False, accounting_bounded=True,
        charged_usd=None, prompt_tokens=None, completion_tokens=None, requests=None,
        budget_stop_count=entry['budget_stop_count'],
        known_billed_subtotal_usd=str(Decimal(known) / Decimal(1_000_000_000)),
        retained_reservation_nanodollars=retained,
        hard_reserved_nanodollars=entry['reserved_nanodollars'])
    return entry


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tasks = [f'task-{i:02d}' for i in range(89)]
        self.rows = []
        for cell in schedule(self.tasks, custom_condition='C2', custom_parent='C1'):
            self.rows.append(dict(cell, status='verified', model_protocol_sha256='protocol',
                model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
                verifier_result={'rewards': {'reward': 0}},
                agent_context={'metadata': {'custom_parent': 'C1'}},
                phase_seconds={'agent': 2.}, billing={'billing_verified': True,
                    'model_protocol_sha256': 'protocol', 'charged_usd': '.01', 'prompt_tokens': 10,
                    'completion_tokens': 5, 'requests': 1, 'budget_stop_count': 0}))

    def analyze(self, runtime=None):
        return analyze(self.rows, all_tasks=self.tasks, development_tasks=self.tasks[:20],
                       custom_condition='C2', custom_parent='C1', protocol='protocol', runtime=runtime)

    def test_all_zero_is_not_a_win_and_costs_include_failures(self):
        result = self.analyze()
        self.assertFalse(result['project_success_certified'])
        for comparison in result['full_89']['paired'].values():
            self.assertFalse(comparison['observed_accuracy_lead'])
            self.assertFalse(comparison['efficiency_win_accepted'])
            self.assertEqual(comparison['exact_mcnemar_two_sided_p_exploratory'], 1.)
        custom = result['full_89']['conditions']['custom']
        self.assertEqual(custom['charged_usd'], '0.89')
        self.assertEqual(custom['prompt_tokens'], 890)
        self.assertEqual(custom['agent_seconds'], 178.)
        self.assertTrue(result['accuracy_complete'])
        self.assertTrue(result['billing_complete'])
        self.assertEqual(result['accounting']['billing_verified_trials'], 267)
        self.assertEqual(result['accounting']['billing_deferred_trials'], 0)
        self.assertEqual(result['accounting']['accounting_coverage'], 1.)
        self.assertEqual(result['accounting']['charged_usd'], '2.67')
        self.assertEqual(result['outside_development_69']['conditions']['custom']['tasks'], 69)

    def test_real_registered_deferral_keeps_complete_matrix_accuracy(self):
        from test_matrix_resume import DeferredCellFixture
        with tempfile.TemporaryDirectory() as directory:
            cell = {key: self.rows[0][key] for key in ('trial_id', 'task_id', 'stage', 'harness', 'parent')}
            fixture = DeferredCellFixture(directory, cell, reward=1)
            for row in self.rows:
                row['model_protocol_sha256'] = fixture.settings.fingerprint()
                row['billing']['model_protocol_sha256'] = fixture.settings.fingerprint()
            self.rows[0] = fixture.view()
            result = analyze(self.rows, all_tasks=self.tasks, development_tasks=self.tasks[:20],
                custom_condition='C2', custom_parent='C1', protocol=fixture.settings.fingerprint(), runtime=fixture.runtime)
            self.assertTrue(result['accuracy_complete'])
            self.assertFalse(result['billing_complete'])
            self.assertEqual(result['accounting']['billing_deferred_trials'], 1)
            self.assertIsNone(result['accounting']['charged_usd'])
            self.assertEqual(result['accounting']['retained_liability_usd'],
                             str(Decimal(fixture.reserved_nanodollars) / 1_000_000_000))

    def test_deferred_zero_and_one_preserve_accuracy_with_explicit_unknown_totals(self):
        custom_rows = [row for row in self.rows if row['harness'] == 'C2']
        entries = {}
        for index, reward, known, retained in [(0, 1, 3_000_000, 20_000_000),
                                               (21, 0, 4_000_000, 25_000_000)]:
            row = custom_rows[index]
            entries[row['trial_id']] = deferred_view(row, reward=reward, known=known, retained=retained)
        runtime = Path('/synthetic-runtime')
        with patch('final_analysis.validated_deferred_cell',
                   side_effect=lambda directory, row, protocol: entries[row['trial_id']]) as validate:
            result = self.analyze(runtime)
        self.assertEqual(validate.call_count, 2)
        self.assertTrue(all(call.args[0] == runtime and call.args[2] == 'protocol'
                            for call in validate.call_args_list))
        self.assertTrue(result['accuracy_complete'])
        self.assertFalse(result['billing_complete'])
        custom = result['full_89']['conditions']['custom']
        self.assertEqual(custom['passes'], 1)
        self.assertEqual(custom['accuracy'], 1 / 89)
        self.assertEqual(custom['billing_deferred_trials'], 2)
        self.assertEqual(custom['billing_verified_trials'], 87)
        self.assertEqual(custom['accounting_coverage'], 87 / 89)
        self.assertEqual(custom['known_billed_subtotal_usd'], '0.877')
        self.assertEqual(custom['retained_reservation_nanodollars'], 45_000_000)
        self.assertEqual(custom['retained_liability_usd'], '0.045')
        self.assertEqual(custom['budget_stopped_trials'], 2)
        for key in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.assertIsNone(custom[key])
            self.assertIsNone(result['accounting'][key])
        self.assertEqual(custom['known_prompt_tokens_subtotal'], 870)
        self.assertEqual(custom['cells_with_known_prompt_tokens'], 87)
        self.assertEqual(result['accounting']['known_billed_subtotal_usd'], '2.657')
        self.assertEqual(result['outside_development_69']['conditions']['custom']['passes'], 0)
        self.assertEqual(result['outside_development_69']['conditions']['custom']['billing_deferred_trials'], 1)
        self.assertEqual(result['full_89']['conditions']['terminus-2']['charged_usd'], '0.89')
        for comparison in result['full_89']['paired'].values():
            self.assertEqual(comparison['net_pass_gain'], 1)
            self.assertFalse(comparison['efficiency_win_accepted'])

    def test_all_deferred_has_unknown_usage_not_zero_totals(self):
        entries = {row['trial_id']: deferred_view(row, reward=1, known=0) for row in self.rows}
        with patch('final_analysis.validated_deferred_cell',
                   side_effect=lambda directory, row, protocol: entries[row['trial_id']]):
            result = self.analyze(Path('/synthetic-runtime'))
        totals = result['accounting']
        self.assertEqual(totals['billing_deferred_trials'], 267)
        self.assertEqual(totals['accounting_coverage'], 0.)
        self.assertEqual(totals['known_billed_subtotal_usd'], '0')
        self.assertIsNone(totals['charged_usd'])
        for key in ('prompt_tokens', 'completion_tokens', 'requests'):
            self.assertIsNone(totals[key])
            self.assertEqual(totals['known_' + key + '_subtotal'], 0)
            self.assertEqual(totals['cells_with_known_' + key], 0)
        self.assertEqual(result['full_89']['conditions']['custom']['accuracy'], 1.)

    def test_markers_without_canonical_registration_cannot_authorize_deferral(self):
        deferred_view(self.rows[0])
        with self.assertRaises(ValueError):
            self.analyze()
        with tempfile.TemporaryDirectory() as runtime, self.assertRaises((ValueError, OSError)):
            self.analyze(Path(runtime))
        with patch('final_analysis.validated_deferred_cell', return_value=None), self.assertRaises(ValueError):
            self.analyze(Path('/synthetic-runtime'))

    def test_deferred_unknown_fields_cannot_be_imputed(self):
        entry = deferred_view(self.rows[0])
        original = copy.deepcopy(self.rows[0])
        for field in ('charged_usd', 'prompt_tokens', 'completion_tokens', 'requests'):
            self.rows[0] = copy.deepcopy(original)
            self.rows[0]['billing'][field] = 0
            with self.subTest(field=field), patch('final_analysis.validated_deferred_cell', return_value=entry):
                with self.assertRaises(ValueError):
                    self.analyze(Path('/synthetic-runtime'))

    def test_deferred_still_requires_exact_identity_cleanup_and_binary_reward(self):
        entry = deferred_view(self.rows[0])
        original = copy.deepcopy(self.rows[0])
        mutations = [('trial_id', original['trial_id'] + '-replay'), ('containers_removed', False),
                     ('model_revoked', False), ('model_protocol_sha256', 'wrong')]
        for field, value in mutations:
            self.rows[0] = copy.deepcopy(original)
            self.rows[0][field] = value
            with self.subTest(field=field), patch('final_analysis.validated_deferred_cell', return_value=entry):
                with self.assertRaises(ValueError): self.analyze(Path('/synthetic-runtime'))
        self.rows[0] = original
        self.rows[0]['verifier_result']['rewards']['reward'] = True
        with patch('final_analysis.validated_deferred_cell', return_value=entry), self.assertRaises(ValueError):
            self.analyze(Path('/synthetic-runtime'))

    def test_development_gain_not_claimed_as_outside_gain(self):
        for row in self.rows:
            if row['harness'] == 'C2' and row['task_id'] in self.tasks[:20]:
                row['verifier_result']['rewards']['reward'] = 1
        result = self.analyze()
        self.assertEqual(result['full_89']['paired']['terminus-2']['net_pass_gain'], 20)
        self.assertEqual(result['outside_development_69']['paired']['terminus-2']['net_pass_gain'], 0)

    def test_exact_discordant_tail(self):
        tasks = list('abcdef')
        custom = {task: {'reward': 1} for task in tasks}
        baseline = {task: {'reward': 0} for task in tasks}
        result = paired(custom, baseline, tasks)
        self.assertEqual(result['exact_mcnemar_two_sided_p_exploratory'], .03125)
        self.assertEqual(result['gained_tasks'], tasks)
        self.assertEqual(result['regressed_tasks'], [])

    def test_missing_or_duplicate_cells_rejected(self):
        self.rows.pop()
        with self.assertRaises(ValueError): self.analyze()
        self.rows.append(copy.deepcopy(self.rows[0]))
        with self.assertRaises(ValueError): self.analyze()

    def test_wrong_protocol_cleanup_or_parent_rejected(self):
        original = copy.deepcopy(self.rows)
        for key, value in [('model_protocol_sha256', 'changed'), ('containers_removed', False),
                           ('trial_id', 'final-not-the-scheduled-cell')]:
            self.rows = copy.deepcopy(original)
            self.rows[0][key] = value
            with self.assertRaises(ValueError): self.analyze()
        self.rows = original
        next(row for row in self.rows if row['harness'] == 'C2')['agent_context']['metadata']['custom_parent'] = 'C0'
        with self.assertRaises(ValueError): self.analyze()

    def test_unknown_usage_nonfinite_time_boolean_reward_rejected(self):
        original = copy.deepcopy(self.rows)
        self.rows[0]['billing']['completion_tokens'] = None
        with self.assertRaises(ValueError): self.analyze()
        self.rows = copy.deepcopy(original)
        self.rows[0]['phase_seconds']['agent'] = float('nan')
        with self.assertRaises(ValueError): self.analyze()
        self.rows = original
        self.rows[0]['verifier_result']['rewards']['reward'] = True
        with self.assertRaises(ValueError): self.analyze()

import copy
import unittest

from final_analysis import analyze, paired
from final_schedule import schedule


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

    def analyze(self):
        return analyze(self.rows, all_tasks=self.tasks, development_tasks=self.tasks[:20],
                       custom_condition='C2', custom_parent='C1', protocol='protocol')

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
        self.assertEqual(result['outside_development_69']['conditions']['custom']['tasks'], 69)

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

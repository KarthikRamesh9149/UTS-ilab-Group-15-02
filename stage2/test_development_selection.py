import unittest
from development_selection import select


class SelectionTests(unittest.TestCase):
    tasks = [f'task-{i}' for i in range(20)]
    protocol = 'a' * 64

    def block(self, condition, passes=10, cost='.001', parent=None):
        return [dict(task_id=task, harness=condition, stage='development', status='verified',
            model_protocol_sha256=self.protocol, model_revoked=True, containers_removed=True,
            networks_removed=True, volumes_removed=True, verifier_result={'rewards': {'reward': int(i < passes)}},
            phase_seconds={'agent': 1}, agent_context={'metadata': {'custom_parent': parent}},
            billing={'billing_verified': True, 'model_protocol_sha256': self.protocol,
                     'charged_usd': cost, 'prompt_tokens': 10, 'completion_tokens': 2, 'requests': 1})
            for i, task in enumerate(self.tasks)]

    def run_selection(self, blocks, parent=None):
        return select(blocks, task_ids=self.tasks, protocol=self.protocol, c2_parent=parent)

    def test_passes_outrank_cost(self):
        result = self.run_selection({'C0': self.block('C0'), 'C1': self.block('C1', 11, '.002')})
        self.assertEqual(result['selected'], 'C1')

    def test_cost_then_simplicity(self):
        self.assertEqual(self.run_selection({'C0': self.block('C0'), 'C1': self.block('C1', cost='.0009')})['selected'], 'C1')
        self.assertEqual(self.run_selection({'C0': self.block('C0'), 'C1': self.block('C1')})['selected'], 'C0')

    def test_tied_increment_ablate_later_addition(self):
        result = self.run_selection({'C0': self.block('C0', 8), 'C1': self.block('C1', 10),
                                     'C2': self.block('C2', 12, parent='C1')}, 'C1')
        self.assertEqual(result['diagnostic']['remove'], 'completion')
        self.assertFalse(result['final_evaluation_success_claimed'])

    def test_remove_planning_preserves_completion(self):
        result = self.run_selection({'C0': self.block('C0', 5), 'C1': self.block('C1', 10),
                                     'C2': self.block('C2', 11, parent='C1')}, 'C1')
        self.assertEqual((result['diagnostic']['condition'], result['diagnostic']['parent']), ('C2', 'C0'))

    def test_no_accuracy_gain_repeats_selected_unchanged(self):
        result = self.run_selection({'C0': self.block('C0'), 'C1': self.block('C1'),
                                     'C2': self.block('C2', cost='.0005', parent='C0')}, 'C0')
        self.assertEqual(result['diagnostic']['kind'], 'unchanged_repeat')

    def test_incomplete_or_duplicate_not_selectable(self):
        for bad in [self.block('C1')[:-1], [self.block('C1')[0]] * 20]:
            with self.assertRaises(ValueError): self.run_selection({'C0': self.block('C0'), 'C1': bad})

    def test_wrong_parent_rejected(self):
        with self.assertRaises(ValueError):
            self.run_selection({'C0': self.block('C0'), 'C1': self.block('C1'),
                                'C2': self.block('C2', parent='C1')}, 'C1')

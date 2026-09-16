from collections import Counter
import unittest
from final_schedule import schedule


class FinalScheduleTests(unittest.TestCase):
    tasks = [f'fixture-{i:02d}' for i in range(89)]

    def test_complete_fresh_rotated_matrix(self):
        cells = schedule(self.tasks, custom_condition='C2', custom_parent='C1')
        self.assertEqual(len(cells), 267)
        self.assertEqual(len({cell['trial_id'] for cell in cells}), 267)
        self.assertEqual(Counter(cell['role'] for cell in cells), dict.fromkeys(['terminus-2', 'openhands', 'custom'], 89))
        self.assertEqual([cells[index]['role'] for index in (0, 3, 6)], ['terminus-2', 'openhands', 'custom'])
        for task in self.tasks:
            rows = [cell for cell in cells if cell['task_id'] == task]
            self.assertEqual(len(rows), 3)
            self.assertTrue(all(cell['stage'] == 'final' for cell in rows))
        self.assertTrue(all(cell['parent'] == 'C1' for cell in cells if cell['role'] == 'custom'))

    def test_input_order_does_not_change_schedule(self):
        self.assertEqual(schedule(self.tasks, custom_condition='C0'), schedule(self.tasks[::-1], custom_condition='C0'))

    def test_missing_duplicate_and_unsafe_tasks_rejected(self):
        for tasks in (self.tasks[:-1], [self.tasks[0]] * 89, self.tasks[:-1] + ['../escape']):
            with self.assertRaises(ValueError): schedule(tasks, custom_condition='C0')

    def test_parent_must_match_condition(self):
        for condition, parent in [('C0', 'C1'), ('C2', None), ('C3', None)]:
            with self.assertRaises(ValueError): schedule(self.tasks, custom_condition=condition, custom_parent=parent)

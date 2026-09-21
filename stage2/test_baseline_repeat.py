import unittest
from run_baseline_repeat import cells


class BaselineRepeatTests(unittest.TestCase):
    def test_all_178_fresh_cells_and_paired_tasks(self):
        tasks = [f'task-{i:02d}' for i in range(89)]
        rows = cells(tasks)
        self.assertEqual(len(rows), 178)
        self.assertEqual(len({r['trial_id'] for r in rows}), 178)
        for role in ('terminus-2', 'openhands'):
            self.assertEqual({r['task_id'] for r in rows if r['harness'] == role}, set(tasks))
        self.assertTrue(all(r['trial_id'].startswith('repeat1-final-') for r in rows))
        self.assertTrue(all(r['stage'] == 'final' for r in rows))

    def test_missing_task_refused(self):
        with self.assertRaises(ValueError): cells(['a']*88)

    def test_duplicate_task_refused(self):
        with self.assertRaises(ValueError): cells(['a']*89)

    def test_order_does_not_depend_on_prior_scores(self):
        tasks = [f'task-{i:02d}' for i in range(89)]
        self.assertEqual(cells(tasks), cells(list(reversed(tasks))))

if __name__ == '__main__': unittest.main()

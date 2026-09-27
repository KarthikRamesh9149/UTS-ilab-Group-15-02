"""Synthetic schedules only. No task environment or model is invoked."""
from collections import Counter
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from portable_candidate_freeze import capture
from portable_custom_policy import fingerprint
from portable_evaluation_schedule import schedule, validate_schedule
from test_portable_candidate_freeze import FreezeFixture


class PortableEvaluationScheduleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture = FreezeFixture(temporary.name)
        self.enterContext(self.fixture.patches())
        self.document = capture(temporary.name)
        self.manifest = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())

    def test_confirmation_is_twenty_per_system_not_full_baseline_replay(self):
        value = schedule(self.document, self.manifest, 'confirmation')
        self.assertEqual(value['intended'], 60)
        self.assertEqual(Counter(row['role'] for row in value['cells']),
                         {'terminus-2': 20, 'openhands': 20, 'custom': 20})
        for role in ('terminus-2', 'openhands', 'custom'):
            rows = [row for row in value['cells'] if row['role'] == role]
            self.assertEqual([row['task_id'] for row in rows], self.manifest['development_ids'])
            self.assertTrue(all(row['stage'] == 'development' for row in rows))
            expected = ('C2', 'C1') if role == 'custom' else (role, None)
            self.assertTrue(all((row['harness'], row['parent']) == expected for row in rows))

    def test_confirmation_rotates_condition_order(self):
        rows = schedule(self.document, self.manifest, 'confirmation')['cells']
        self.assertEqual([row['role'] for row in rows[:9]], [
            'terminus-2', 'openhands', 'custom', 'openhands', 'custom', 'terminus-2',
            'custom', 'terminus-2', 'openhands'])

    def test_diagnostic_keeps_frozen_ablation_on_development_tasks(self):
        value = schedule(self.document, self.manifest, 'diagnostic')
        self.assertEqual(value['intended'], 20)
        self.assertEqual(value['diagnostic_kind'], 'ablation')
        self.assertEqual([row['task_id'] for row in value['cells']], self.manifest['development_ids'])
        self.assertTrue(all(row['harness'] == 'C1' and row['parent'] is None for row in value['cells']))

    def test_final_has_exactly_eighty_nine_fresh_custom_cells(self):
        value = schedule(self.document, self.manifest, 'final')
        rows = value['cells']
        self.assertEqual(len(rows), 89)
        self.assertEqual(len({row['trial_id'] for row in rows}), 89)
        self.assertEqual({row['task_id'] for row in rows}, set(self.manifest['all_task_ids']))
        self.assertEqual([row['task_id'] for row in rows[:20]], self.manifest['development_ids'])
        self.assertTrue(all(row['stage'] == 'final' and row['role'] == 'custom'
                            and row['harness'] == 'C2' and row['parent'] == 'C1' for row in rows))

    def test_attempt_names_never_overlap_any_other_phase_or_development(self):
        seen = set(self.document['result_bindings'])
        for phase in ('confirmation', 'diagnostic', 'final'):
            names = {row['trial_id'] for row in schedule(self.document, self.manifest, phase)['cells']}
            self.assertFalse(seen & names)
            self.assertTrue(all(len(name) <= 120 for name in names))
            seen.update(names)
        self.assertEqual(len(seen), 60 + 60 + 20 + 89)

    def test_schedule_never_admits_paid_execution_or_claims_win(self):
        for phase in ('confirmation', 'diagnostic', 'final'):
            value = schedule(self.document, self.manifest, phase)
            self.assertFalse(value['paid_launch_ready'])
            self.assertFalse(value['full_benchmark_win_claimed'])
            self.assertFalse(value['automatic_task_replay'])
            self.assertEqual(value['parallel_trials'], 1)
            self.assertEqual(value['candidate_sha256'], fingerprint(self.document))
            self.assertEqual(validate_schedule(value, self.document, self.manifest), value)

    def test_changed_manifest_including_held_out_identity_is_rejected(self):
        for change in ('order', 'resource', 'identity'):
            value = deepcopy(self.manifest)
            if change == 'order':
                value['development_ids'].reverse()
            elif change == 'resource':
                value['tasks'][0]['memory_mb'] += 1
            else:
                value['outside_development_ids'][0] = 'substituted-task'
            with self.assertRaises(ValueError):
                schedule(self.document, value, 'final')

    def test_modified_schedule_or_foreign_candidate_is_rejected(self):
        original = schedule(self.document, self.manifest, 'final')
        mutations = (
            lambda d: d.update(parallel_trials=2),
            lambda d: d.update(attempts_per_registered_cell=2),
            lambda d: d.update(paid_launch_ready=True),
            lambda d: d.update(candidate_sha256='0' * 64),
            lambda d: d['cells'].reverse(),
            lambda d: d['cells'].pop(),
            lambda d: d['cells'][0].update(harness='C0'),
            lambda d: d['cells'][0].update(parent='C0'),
            lambda d: d['cells'][0].update(trial_id='repeat-an-old-attempt'),
        )
        for mutate in mutations:
            value = deepcopy(original)
            mutate(value)
            with self.assertRaises(ValueError):
                validate_schedule(value, self.document, self.manifest)

    def test_invalid_phase_or_incomplete_freeze_is_rejected(self):
        for phase in (None, 'development', 'qualification', 'final-retry'):
            with self.assertRaises(ValueError):
                schedule(self.document, self.manifest, phase)
        self.document['selection_inputs'].pop('C2')
        with self.assertRaises(ValueError):
            schedule(self.document, self.manifest, 'final')

    def test_schedule_does_not_mutate_freeze_or_manifest(self):
        before = deepcopy((self.document, self.manifest))
        value = schedule(self.document, self.manifest, 'final')
        value['cells'][0]['task_id'] = 'changed-returned-object'
        self.assertEqual((self.document, self.manifest), before)


if __name__ == '__main__':
    unittest.main()

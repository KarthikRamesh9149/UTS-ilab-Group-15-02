import copy
import json
from pathlib import Path
import tempfile
import unittest

from corrected_custom_scope import matched_baselines, inspect, COMPARATORS, BASELINES
from freeze_inputs import select_dev
from retry_policy import SETTINGS


class CorrectedCustomScopeTests(unittest.TestCase):
    def setUp(self):
        tasks = ['synthetic-' + str(i) for i in range(89)]
        self.manifest = dict(all_task_ids=tasks, development_ids=select_dev(tasks))
        self.rows = [dict(trial_id=f'{h}-{t}', harness=h, task_id=t,
            reward='1' if h == 'openhands' else '0', result_sha256='a' * 64,
            cleanup_complete='True', model_revoked='True')
            for h in COMPARATORS for t in self.manifest['development_ids']]

    def check(self):
        return matched_baselines(self.manifest, self.rows, model_protocol=SETTINGS.document())

    def test_same_twenty_all_failures_and_preselected_comparator_preserved(self):
        before = copy.deepcopy((self.manifest, self.rows))
        result = self.check()
        self.assertEqual(result['primary_comparator'], 'terminus-2')
        self.assertEqual(result['conditions']['terminus-2'], dict(attempted=20, passed=0, failed=20))
        self.assertEqual(result['conditions']['openhands'], dict(attempted=20, passed=20, failed=0))
        self.assertFalse(result['paid_launch_ready'])
        self.assertFalse(result['baseline_reruns_needed'])
        self.assertEqual((self.manifest, self.rows), before)

    def test_cannot_swap_development_task(self):
        self.manifest['development_ids'][0] = next(t for t in self.manifest['all_task_ids']
            if t not in self.manifest['development_ids'])
        with self.assertRaises(ValueError): self.check()

    def test_cannot_reorder_split(self):
        self.manifest['development_ids'].reverse()
        with self.assertRaises(ValueError): self.check()

    def test_duplicate_row_or_trial_identifier_fails(self):
        self.rows[0] = dict(self.rows[1])
        with self.assertRaises(ValueError): self.check()
        self.setUp()
        self.rows[0]['trial_id'] = self.rows[1]['trial_id']
        with self.assertRaises(ValueError): self.check()

    def test_incomplete_or_additional_baseline_rows_fail(self):
        saved = list(self.rows)
        self.rows.pop()
        with self.assertRaises(ValueError): self.check()
        self.rows = saved + [dict(saved[0])]
        with self.assertRaises(ValueError): self.check()

    def test_held_out_row_is_not_a_development_comparator(self):
        self.rows[0]['task_id'] = next(t for t in self.manifest['all_task_ids']
            if t not in self.manifest['development_ids'])
        with self.assertRaises(ValueError): self.check()

    def test_unknown_score_is_not_treated_as_failure(self):
        for value in ('', None, '0.5', True, 0):
            self.rows[0]['reward'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): self.check()

    def test_missing_safety_or_original_binding_fails(self):
        for name, value in (('cleanup_complete', 'False'), ('model_revoked', ''),
                            ('result_sha256', 'unverified')):
            self.setUp()
            self.rows[0][name] = value
            with self.subTest(name=name), self.assertRaises(ValueError): self.check()

    def test_model_protocol_cannot_drift(self):
        for name, value in (('max_output_tokens', 8192), ('temperature', 0), ('endpoint', 'other'),
                            ('temperature', True), ('top_p', True)):
            with self.subTest(name=name), self.assertRaises(ValueError):
                matched_baselines(self.manifest, self.rows,
                    model_protocol=SETTINGS.document() | {name: value})

    def test_real_export_matches_original_manifest_and_all_twenty_per_baseline(self):
        result = inspect(Path(__file__).resolve().parents[1])
        self.assertEqual(result['paired_task_count'], 20)
        self.assertEqual(len(result['original_results_sha256']), 40)
        for harness in COMPARATORS:
            self.assertEqual(result['conditions'][harness]['attempted'], 20)

    def test_baseline_input_binding_is_checked_before_reading_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / BASELINES).mkdir(parents=True)
            (root / 'stage2/input_manifest.json').write_text(json.dumps(self.manifest))
            (root / BASELINES / 'summary.json').write_text(json.dumps(dict(
                sources_sha256={'input_manifest.json': 'f' * 64})))
            with self.assertRaisesRegex(ValueError, 'Input inventory differs'):
                inspect(root)

    def test_edited_comparator_export_is_not_accepted(self):
        source = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / BASELINES).mkdir(parents=True)
            for relative in (Path('stage2/input_manifest.json'), BASELINES / 'summary.json'):
                (root / relative).write_bytes((source / relative).read_bytes())
            (root / BASELINES / 'development-baselines.csv').write_text('changed export')
            with self.assertRaisesRegex(ValueError, 'CSV differs'):
                inspect(root)


if __name__ == '__main__':
    unittest.main()

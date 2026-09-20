import fcntl
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from final_schedule import schedule
from model_protocol import ModelSettings
from run_baselines import BINDING_FILES, baseline_cells, run, validate_registration


class BaselineRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        for name in BINDING_FILES:
            (self.root / 'stage2' / name).write_text('{}')
        self.tasks = [f'fixture-{i}' for i in range(89)]
        self.manifest = {'development_ids': self.tasks[:20], 'all_task_ids': self.tasks}
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps(self.manifest))
        self.admission = {'gateway_image': 'fixture', 'guard_image': 'fixture',
                          'setup_timeout_seconds': 30}
        self.settings = ModelSettings(64, 1., 'high')
        self.rows, self.calls = {}, []
        for name, options in {
            'validate': dict(return_value=self.settings),
            'source_hashes': dict(return_value={'runtime.py': 'initial'}),
            'assess': dict(return_value={'paid_expansion_allowed': True}),
            'completed_cell': dict(side_effect=lambda root, cell, settings: self.rows.get(cell['trial_id'])),
            'run_trial': dict(side_effect=self.execute),
            'agent_factory': dict(return_value='fixture_factory')}.items():
            p = patch('run_baselines.' + name, **options)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        p = patch('builtins.print')
        self.print_mock = p.start()
        self.addCleanup(p.stop)

    @property
    def registration(self):
        return self.root / '.runtime/stage2/baseline-matrix.json'

    async def execute(self, **kwargs):
        self.assertTrue(self.registration.is_file())
        descriptor = json.loads(self.registration.read_text())
        self.assertIn(kwargs['trial_id'], {cell['trial_id'] for cell in descriptor['cells']})
        self.calls.append(kwargs)
        self.rows[kwargs['trial_id']] = {'verifier_result': {'rewards': {'reward': 0}}}
        attempt = self.root / '.runtime/stage2/scored-trials' / kwargs['trial_id']
        attempt.mkdir(parents=True)
        (attempt / 'result.json').write_text(json.dumps(self.rows[kwargs['trial_id']]))

    def orphan(self, identifier, directory='scored-trials'):
        runtime = self.root / '.runtime/stage2'
        runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        runtime.chmod(0o700)
        (runtime / directory / identifier).mkdir(parents=True)

    async def test_exact_178_canonical_cells_registered_before_dispatch_and_not_replayed(self):
        first = await run(self.root, self.admission, {})
        second = await run(self.root, self.admission, {})
        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 178)
        self.assertEqual(len({call['trial_id'] for call in self.calls}), 178)
        self.assertEqual([call['trial_id'] for call in self.calls],
                         [cell['trial_id'] for cell in baseline_cells(self.tasks)])
        self.assertTrue(all(call['stage'] == 'final' for call in self.calls))
        self.assertTrue(all(sum(call['task_id'] == task for call in self.calls) == 2 for task in self.tasks))
        for condition, parent in [('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')]:
            self.assertEqual(baseline_cells(self.tasks), [cell for cell in schedule(
                self.tasks, custom_condition=condition, custom_parent=parent) if cell['role'] != 'custom'])
        descriptor = validate_registration(self.root, self.admission)
        self.assertEqual(descriptor['planned_final_cells'], 267)
        self.assertFalse(descriptor['additional_baseline_attempts_authorised'])
        self.assertEqual(descriptor['development_task_ids'], self.tasks[:20])
        self.assertTrue(all(set(json.loads(call.args[0])) == {'completed', 'intended', 'trial_id'}
                            for call in self.print_mock.call_args_list))

    async def test_missing_durable_result_stops_without_second_dispatch(self):
        self.run_trial.side_effect = None
        with self.assertRaises(RuntimeError):
            await run(self.root, self.admission, {})
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_incomplete_systemic_qualification_prevents_registration_and_spending(self):
        self.assess.return_value = {'paid_expansion_allowed': False}
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {})
        self.assertFalse(self.registration.exists())
        self.run_trial.assert_not_called()

    async def test_interrupted_registered_attempt_is_not_replayed(self):
        async def interrupted(**kwargs):
            self.orphan(kwargs['trial_id'])
            raise RuntimeError('interrupted')
        self.run_trial.side_effect = interrupted
        with self.assertRaises(RuntimeError):
            await run(self.root, self.admission, {})
        self.completed_cell.side_effect = RuntimeError('Existing attempt requires inspection')
        with self.assertRaises(RuntimeError):
            await run(self.root, self.admission, {})
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_orphan_trial_or_gateway_attempt_without_registration_refused(self):
        identifier = baseline_cells(self.tasks)[0]['trial_id']
        self.orphan(identifier, 'scored-attempts')
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {})
        self.run_trial.assert_not_called()
        self.assertFalse(self.registration.exists())

    async def test_registered_gateway_only_partial_stops_before_trial_dispatch(self):
        self.run_trial.side_effect = RuntimeError('fixture stopped after registration')
        with self.assertRaises(RuntimeError):
            await run(self.root, self.admission, {})
        self.assertTrue(self.registration.is_file())
        self.orphan(baseline_cells(self.tasks)[0]['trial_id'], 'scored-attempts')
        self.run_trial.reset_mock()
        self.run_trial.side_effect = self.execute
        with self.assertRaisesRegex(ValueError, 'gateway attempt lacks trial evidence'):
            await run(self.root, self.admission, {})
        self.run_trial.assert_not_called()
        self.assertEqual(self.calls, [])

    async def test_source_change_between_cells_stops(self):
        async def changed(**kwargs):
            await self.execute(**kwargs)
            (self.root / 'stage2/run_baselines.py').write_text('changed')
        self.run_trial.side_effect = changed
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {})
        self.assertEqual(len(self.calls), 1)

    async def test_review_failure_between_cells_stops(self):
        async def changed(**kwargs):
            await self.execute(**kwargs)
            self.assess.return_value = {'paid_expansion_allowed': False}
        self.run_trial.side_effect = changed
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {})
        self.assertEqual(len(self.calls), 1)

    async def test_admission_review_manifest_and_cells_tampering_refused(self):
        await run(self.root, self.admission, {})
        with self.assertRaises(ValueError):
            validate_registration(self.root, {**self.admission, 'gateway_image': 'changed'})
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {'reviewer': 'changed'})
        original = self.registration.read_text()
        for modify in (
            lambda value: value['cells'].append(value['cells'][0]),
            lambda value: value['cells'][0].update(trial_id='final-terminus-2-99-other'),
            lambda value: value.update(model_protocol_sha256='0' * 64),
        ):
            descriptor = json.loads(original)
            modify(descriptor)
            self.registration.write_text(json.dumps(descriptor))
            with self.assertRaises(ValueError):
                validate_registration(self.root, self.admission)
        self.registration.write_text(original)
        self.manifest['development_ids'] = self.tasks[1:21]
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps(self.manifest))
        with self.assertRaises(ValueError):
            validate_registration(self.root, self.admission)
        self.assertEqual(len(self.calls), 178)

    async def test_unknown_final_attempt_refused(self):
        await run(self.root, self.admission, {})
        self.orphan('final-terminus-2-99-unknown')
        with self.assertRaises(ValueError):
            validate_registration(self.root, self.admission)

    async def test_custom_attempt_requires_matching_later_final_registration(self):
        await run(self.root, self.admission, {})
        final = schedule(self.tasks, custom_condition='C2', custom_parent='C1')
        custom = next(cell for cell in final if cell['role'] == 'custom')
        self.orphan(custom['trial_id'])
        with self.assertRaises(ValueError):
            validate_registration(self.root, self.admission)
        descriptor = {'kind': 'final_evaluation_started', 'cells': final,
            'freeze': {'admission': self.admission,
                       'selection': {'selected': 'C2', 'selected_parent': 'C1'}},
            'baseline_registration_sha256': hashlib.sha256(self.registration.read_bytes()).hexdigest()}
        final_path = self.root / '.runtime/stage2/final-matrix.json'
        final_path.write_text(json.dumps(descriptor))
        self.assertIsNotNone(validate_registration(self.root, self.admission))
        descriptor['baseline_registration_sha256'] = '0' * 64
        final_path.write_text(json.dumps(descriptor))
        with self.assertRaises(ValueError):
            validate_registration(self.root, self.admission)

    async def test_matrix_lock_prevents_competing_execution(self):
        runtime = self.root / '.runtime/stage2'
        runtime.mkdir(parents=True, mode=0o700)
        with (runtime / 'matrix.lock').open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                await run(self.root, self.admission, {})
        self.run_trial.assert_not_called()
        self.assertFalse(self.registration.exists())

    def test_no_registration_returns_none_without_mutation(self):
        self.assertIsNone(validate_registration(self.root, self.admission))
        self.assertFalse((self.root / '.runtime').exists())

    def test_duplicate_or_unsafe_tasks_are_rejected(self):
        with self.assertRaises(ValueError):
            baseline_cells(self.tasks[:-1] + self.tasks[:1])
        with self.assertRaises(ValueError):
            baseline_cells(self.tasks[:-1] + ['../escape'])


if __name__ == '__main__':
    unittest.main()

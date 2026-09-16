import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_protocol import ModelSettings
from run_final import run, prerequisites


class FinalRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        self.tasks = [f'fixture-{i}' for i in range(89)]
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({
            'development_ids': self.tasks[:20], 'all_task_ids': self.tasks}))
        self.freeze = {'admission': {'gateway_image': 'fixture', 'guard_image': 'fixture',
                                    'setup_timeout_seconds': 30}, 'custom_max_model_calls': 100,
                       'selection': {'selected': 'C2', 'selected_parent': 'C1',
                                     'diagnostic': {'condition': 'C1', 'parent': None}}}
        self.rows, self.calls = {}, []
        for name, options in {
            'verify': dict(return_value='C2'),
            'validate': dict(return_value=ModelSettings(64, 1., 'high')),
            'assess': dict(return_value={'paid_expansion_allowed': True}),
            'prerequisites': dict(return_value={'fixture': 'digest'}),
            'completed_cell': dict(side_effect=lambda root, cell, settings: self.rows.get(cell['trial_id'])),
            'run_trial': dict(side_effect=self.execute),
            'agent_factory': dict(return_value='fixture_factory')}.items():
            p = patch('run_final.' + name, **options)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        p = patch('builtins.print')
        p.start()
        self.addCleanup(p.stop)

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        self.rows[kwargs['trial_id']] = {'verifier_result': {'rewards': {'reward': 0}}}

    async def test_exact_267_fresh_cells_and_zero_replay(self):
        first = await run(self.root, self.freeze, {})
        second = await run(self.root, self.freeze, {})
        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 267)
        self.assertEqual(len({call['trial_id'] for call in self.calls}), 267)
        self.assertTrue(all(call['stage'] == 'final' for call in self.calls))
        for task in self.tasks:
            self.assertEqual(sum(call['task_id'] == task for call in self.calls), 3)
        descriptor = json.loads((self.root / '.runtime/stage2/final-matrix.json').read_text())
        self.assertEqual(descriptor['kind'], 'final_evaluation_started')
        self.assertEqual(sum(cell['role'] == 'custom' for cell in descriptor['cells']), 89)
        for call in self.agent_factory.call_args_list:
            self.assertEqual(call.kwargs['custom_max_model_calls'], 100 if call.args[0] == 'C2' else None)

    async def test_incomplete_development_prevents_final(self):
        self.prerequisites.side_effect = ValueError('incomplete')
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.run_trial.assert_not_called()

    async def test_changed_freeze_stops_between_cells(self):
        self.verify.side_effect = ['C2', 'C2', ValueError('changed')]
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.assertEqual(len(self.calls), 1)

    async def test_missing_durable_result_stops(self):
        self.run_trial.side_effect = None
        with self.assertRaises(RuntimeError): await run(self.root, self.freeze, {})
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_changed_evidence_refuses_resume(self):
        await run(self.root, self.freeze, {})
        self.prerequisites.return_value = {'fixture': 'changed'}
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.assertEqual(len(self.calls), 267)

    async def test_rejected_review_never_spends(self):
        self.assess.return_value = {'paid_expansion_allowed': False}
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.run_trial.assert_not_called()

    def test_real_prerequisites_reject_missing_diagnostic_registration(self):
        with self.assertRaises(ValueError):
            prerequisites(self.root, self.freeze, {}, self.tasks[:20], self.validate.return_value)

    def test_real_prerequisites_reaudit_all_40_results(self):
        runtime = self.root / '.runtime/stage2'
        runtime.mkdir(parents=True)
        tasks = self.tasks[:20]
        diagnostic_cells = [dict(trial_id=f'dev-diagnostic-{i:02d}-{task}', task_id=task,
            stage='development', harness='C1', parent=None) for i, task in enumerate(tasks)]
        (runtime / 'diagnostic-block.json').write_text(json.dumps({
            'kind': 'frozen_diagnostic_not_selection', 'freeze': self.freeze,
            'review': {}, 'cells': diagnostic_cells}))
        for prefix in ('openhands', 'diagnostic'):
            for i, task in enumerate(tasks):
                identifier = f'dev-{prefix}-{i:02d}-{task}'
                self.rows[identifier] = {'fixture': True}
                attempt = runtime / 'scored-trials' / identifier
                attempt.mkdir(parents=True)
                (attempt / 'result.json').write_text('{}')
        hashes = prerequisites(self.root, self.freeze, {}, tasks, self.validate.return_value)
        self.assertEqual(len(hashes), 40)
        self.assertEqual(self.completed_cell.call_count, 40)
        del self.rows[diagnostic_cells[-1]['trial_id']]
        with self.assertRaises(ValueError):
            prerequisites(self.root, self.freeze, {}, tasks, self.validate.return_value)

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_protocol import ModelSettings
from run_diagnostic import run


class DiagnosticTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        self.tasks = [f'fixture-{i}' for i in range(20)]
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': self.tasks}))
        self.freeze = {'admission': {'gateway_image': 'fixture', 'guard_image': 'fixture',
                                    'setup_timeout_seconds': 30}, 'custom_max_model_calls': 100,
                       'selection': {'selected': 'C2', 'diagnostic': {
                           'kind': 'ablation', 'condition': 'C1', 'parent': None}}}
        self.rows, self.calls = {}, []
        patches = {
            'verify': dict(return_value='C2'),
            'validate': dict(return_value=ModelSettings(64, 1., 'high')),
            'assess': dict(return_value={'paid_expansion_allowed': True}),
            'completed_cell': dict(side_effect=lambda root, cell, settings: self.rows.get(cell['trial_id'])),
            'run_trial': dict(side_effect=self.execute),
            'agent_factory': dict(return_value='fixture_factory')}
        for name, options in patches.items():
            p = patch('run_diagnostic.' + name, **options)
            setattr(self, name, p.start())
            self.addCleanup(p.stop)
        p = patch('builtins.print')
        p.start()
        self.addCleanup(p.stop)

    async def execute(self, **kwargs):
        self.calls.append(kwargs['trial_id'])
        self.rows[kwargs['trial_id']] = {'verifier_result': {'rewards': {'reward': 0}}}

    async def test_fresh_ids_resume_and_no_reselection(self):
        original = copy.deepcopy(self.freeze)
        first = await run(self.root, self.freeze, {})
        second = await run(self.root, self.freeze, {})
        self.assertEqual(first, second)
        self.assertEqual(len(self.calls), 20)
        self.assertTrue(all(identifier.startswith('dev-diagnostic-') for identifier in self.calls))
        self.assertEqual(original, self.freeze)
        self.agent_factory.assert_called_with('C1', self.validate.return_value,
                                               custom_max_model_calls=100, parent=None)

    async def test_stale_freeze_never_spends(self):
        self.verify.side_effect = ValueError('stale')
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.run_trial.assert_not_called()

    async def test_failed_review_never_spends(self):
        self.assess.return_value = {'paid_expansion_allowed': False}
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.run_trial.assert_not_called()

    async def test_changed_diagnostic_refuses_resume(self):
        await run(self.root, self.freeze, {})
        self.freeze['selection']['diagnostic']['condition'] = 'C0'
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.assertEqual(len(self.calls), 20)

    async def test_no_durable_result_stops(self):
        self.run_trial.side_effect = None
        self.run_trial.return_value = {'status': 'verified'}
        with self.assertRaises(RuntimeError): await run(self.root, self.freeze, {})
        self.assertEqual(self.run_trial.call_count, 1)

    async def test_changed_freeze_mid_block_stops(self):
        self.verify.side_effect = ['C2', 'C2', ValueError('changed')]
        with self.assertRaises(ValueError): await run(self.root, self.freeze, {})
        self.assertEqual(len(self.calls), 1)

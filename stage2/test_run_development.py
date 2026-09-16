import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from model_protocol import ModelSettings
from run_development import run, cells


class DevelopmentRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'stage2').mkdir()
        self.tasks = [f'fixture-{i}' for i in range(20)]
        (self.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': self.tasks}))
        (self.root / 'stage2/custom_execution_limits.json').write_text(json.dumps(
            {'max_model_calls': 100, 'max_repair_cycles': 2}))
        self.settings = ModelSettings(64, 1., 'high')
        self.admission = dict(gateway_image='fixture', guard_image='fixture', setup_timeout_seconds=30)
        self.rows, self.calls = {}, []
        for target, value in [('validate', self.settings), ('assess', {'paid_expansion_allowed': True})]:
            p = patch('run_development.' + target, return_value=value)
            setattr(self, target, p.start())
            self.addCleanup(p.stop)
        p = patch('run_development.completed_cell', side_effect=lambda root, cell, settings: self.rows.get(cell['trial_id']))
        p.start()
        self.addCleanup(p.stop)
        p = patch('run_development.run_trial', side_effect=self.execute)
        self.execute_mock = p.start()
        self.addCleanup(p.stop)
        p = patch('builtins.print')
        p.start()
        self.addCleanup(p.stop)

    async def execute(self, **kwargs):
        self.calls.append(kwargs['trial_id'])
        self.rows[kwargs['trial_id']] = {'verifier_result': {'rewards': {'reward': 0}}}

    async def test_zero_results_retained_on_resume(self):
        first = await run(self.root, self.admission, {}, 'openhands')
        second = await run(self.root, self.admission, {}, 'openhands')
        self.assertEqual(len(self.calls), 20)
        self.assertEqual(first, second)

    async def test_rejected_review_never_spends(self):
        self.assess.return_value = {'paid_expansion_allowed': False}
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {}, 'openhands')
        self.execute_mock.assert_not_called()

    async def test_missing_predecessor_never_spends(self):
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {}, 'C0')
        self.execute_mock.assert_not_called()

    async def test_changed_descriptor_refuses_resume(self):
        await run(self.root, self.admission, {}, 'openhands')
        with self.assertRaises(ValueError):
            await run(self.root, {**self.admission, 'gateway_image': 'changed'}, {}, 'openhands')
        self.assertEqual(len(self.calls), 20)

    async def test_return_without_durable_evidence_stops(self):
        self.execute_mock.side_effect = None
        self.execute_mock.return_value = {'status': 'verified'}
        with self.assertRaises(RuntimeError):
            await run(self.root, self.admission, {}, 'openhands')
        self.assertEqual(self.execute_mock.call_count, 1)

    async def test_orphan_attempt_not_adopted(self):
        path = self.root / '.runtime/stage2/scored-trials/dev-openhands-00-fixture-0'
        path.mkdir(parents=True)
        (self.root / '.runtime/stage2').chmod(0o700)
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {}, 'openhands')
        self.execute_mock.assert_not_called()

    async def test_c2_uses_selected_parent_and_registered_limit(self):
        descriptors = self.root / '.runtime/stage2/development-blocks'
        descriptors.mkdir(parents=True, mode=0o700)
        (self.root / '.runtime/stage2').chmod(0o700)
        for block in ('C0', 'C1'):
            (descriptors / (block + '.json')).write_text(json.dumps({'admission': self.admission,
                'limits': {'max_model_calls': 100, 'max_repair_cycles': 2}}))
        for block in ('openhands', 'C0', 'C1'):
            for cell in cells(block, self.tasks):
                self.rows[cell['trial_id']] = {'fixture': block}
        with patch('run_development.select', return_value={'selected_parent': 'C1'}) as selection, \
             patch('run_development.agent_factory') as factory:
            await run(self.root, self.admission, {}, 'C2')
        selection.assert_called_once()
        factory.assert_called_with('C2', self.settings, custom_max_model_calls=100, parent='C1')
        descriptor = json.loads((self.root / '.runtime/stage2/development-blocks/C2.json').read_text())
        self.assertTrue(all(cell['parent'] == 'C1' for cell in descriptor['cells']))

    async def test_limit_change_stops_before_next_cell(self):
        for cell in cells('openhands', self.tasks):
            self.rows[cell['trial_id']] = {'fixture': True}
        async def change_limit(**kwargs):
            await self.execute(**kwargs)
            (self.root / 'stage2/custom_execution_limits.json').write_text(json.dumps(
                {'max_model_calls': 101, 'max_repair_cycles': 2}))
        self.execute_mock.side_effect = change_limit
        with self.assertRaises(ValueError):
            await run(self.root, self.admission, {}, 'C0')
        self.assertEqual(len(self.calls), 1)

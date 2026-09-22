import ast
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from retry_experiment import cells, coverage
from retry_policy import POLICY, SETTINGS
from recovery_agents import agent_factory


class ExperimentTests(unittest.TestCase):
    def test_178_distinct_cells_original_tasks_order_and_pairing(self):
        manifest = json.loads(Path(__file__).with_name('input_manifest.json').read_text())
        tasks = manifest['all_task_ids']
        matrix = cells(tasks)
        self.assertEqual(len(matrix), 178)
        self.assertEqual(len({c['trial_id'] for c in matrix}), 178)
        for harness in ('terminus-2', 'openhands'):
            self.assertEqual([c['task_id'] for c in matrix if c['harness'] == harness], sorted(tasks))
        self.assertTrue(all(c['trial_id'].startswith('corrected1-') for c in matrix))
    def test_no_financial_cap_and_provider_maximum_shared(self):
        self.assertIsNone(POLICY['per_task_cap_usd'])
        self.assertIsNone(POLICY['project_cap_usd'])
        self.assertEqual(POLICY['reserve_usd'], '0')
        self.assertFalse(POLICY['automatic_top_up'])
        self.assertFalse(POLICY['accounting_blocks_dispatch'])
        self.assertEqual(SETTINGS.max_output_tokens, 384000)
    def test_runner_does_not_admit_through_budget_or_balance(self):
        tree = ast.parse(Path(__file__).with_name('run_corrected.py').read_text())
        calls = [n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertFalse(set(calls) & {'balance', 'reserve', 'key_status', 'generation'})
    def test_partial_trial_is_never_missing(self):
        with tempfile.TemporaryDirectory() as temp:
            trial = Path(temp) / 'scored-trials/corrected1-test'
            trial.mkdir(parents=True)
            done, partial = coverage(temp, [{'trial_id': trial.name, 'task_id': 'x', 'harness': 'openhands'}])
            self.assertEqual(done, {})
            self.assertEqual(partial, [trial.name])
    def test_harness_protocol_matches(self):
        for harness in ('terminus-2', 'openhands'):
            factory = agent_factory(harness, Path('/unused'))
            self.assertEqual(factory.model_protocol_sha256, SETTINGS.fingerprint())
            self.assertEqual(factory.harness, harness)


if __name__ == '__main__': unittest.main()

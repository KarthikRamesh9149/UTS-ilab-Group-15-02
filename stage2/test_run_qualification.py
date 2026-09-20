import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from historical_hold import canonical_hold_document
from model_protocol import ModelSettings
from run_qualification import run


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_finished_zero_rewards_are_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stage2').mkdir()
            tasks = ['fixture-' + str(i) for i in range(20)]
            (root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': tasks}))
            settings = ModelSettings(64, 1., 'high')
            billing = {'billing_verified': True, 'model_protocol_sha256': settings.fingerprint(),
                'charged_usd': '.001', 'requests': 1, 'prompt_tokens': 2, 'completion_tokens': 1,
                'budget_stop_count': 0}
            calls = []
            async def execute(**kwargs):
                calls.append(kwargs['task_id'])
                result = {'trial_id': kwargs['trial_id'], 'task_id': kwargs['task_id'],
                    'stage': 'development', 'harness': 'terminus-2', 'status': 'verified',
                    'model_protocol_sha256': settings.fingerprint(), 'model_revoked': True,
                    'containers_removed': True, 'networks_removed': True, 'volumes_removed': True,
                    'billing': billing, 'verifier_result': {'rewards': {'reward': 0}}}
                attempt = root / '.runtime/stage2/scored-trials' / kwargs['trial_id']
                attempt.mkdir(parents=True)
                (attempt / 'result.json').write_text(json.dumps(result))
                return result
            admission = {'gateway_image': 'fixture', 'guard_image': 'fixture', 'setup_timeout_seconds': 30}
            with patch('run_qualification.validate', return_value=settings), \
                 patch('run_qualification.run_trial', side_effect=execute), \
                 patch('matrix_resume.audit_trial', return_value=billing) as audit, \
                 patch('builtins.print'):
                first = await run(root, admission)
                second = await run(root, admission)
            self.assertEqual(calls, tasks)
            self.assertEqual(audit.call_count, 40)
            self.assertFalse(first['paid_expansion_allowed'])
            self.assertEqual(first, second)

    async def test_interrupted_attempt_is_not_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stage2').mkdir()
            tasks = ['fixture-' + str(i) for i in range(20)]
            (root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': tasks}))
            (root / '.runtime/stage2/scored-trials/dev-terminus-2-00-fixture-0').mkdir(parents=True, mode=0o700)
            (root / '.runtime/stage2').chmod(0o700)
            with patch('run_qualification.validate', return_value=ModelSettings(64, 1., 'high')), \
                 patch('run_qualification.run_trial') as execute:
                with self.assertRaises(RuntimeError): await run(root, {})
                execute.assert_not_called()

    async def test_missing_admission_proof_never_calls_runner(self):
        with tempfile.TemporaryDirectory() as directory, patch('run_qualification.run_trial') as execute:
            with self.assertRaises(ValueError): await run(directory, {})
            execute.assert_not_called()

    def held_setup(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        (root / 'stage2').mkdir()
        tasks = ['video-processing'] + ['fixture-' + str(i) for i in range(1, 20)]
        (root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': tasks}))
        settings = ModelSettings(64, 1., 'high')
        hold = canonical_hold_document()
        hold.update(model_protocol_sha256=settings.fingerprint(), sidecar_sha256='c' * 64,
            budget_stop_count=2, budget_stop_classification='historical_pending_barrier',
            capacity_budget_stop_count=0)
        result = {key: hold[key] for key in ('trial_id', 'task_id', 'harness', 'stage', 'model_protocol_sha256')}
        result.update(status='billing_unresolved', model_revoked=True,
            containers_removed=True, networks_removed=True, volumes_removed=True,
            billing={'billing_verified': False}, verifier_result={'rewards': {'reward': 0}})
        path = root / '.runtime/stage2/scored-trials' / hold['trial_id'] / 'result.json'
        path.parent.mkdir(parents=True)
        (root / '.runtime/stage2').chmod(0o700)
        raw = json.dumps(result).encode()
        path.write_bytes(raw)
        hold['original_result_sha256'] = hashlib.sha256(raw).hexdigest()
        validator = patch('matrix_resume.validate_historical_hold', return_value=hold)
        validator.start()
        self.addCleanup(validator.stop)
        billing = {'billing_verified': True, 'model_protocol_sha256': settings.fingerprint(),
            'charged_usd': '.001', 'requests': 1, 'prompt_tokens': 2, 'completion_tokens': 1,
            'budget_stop_count': 0}
        admission = {'gateway_image': 'fixture', 'guard_image': 'fixture', 'setup_timeout_seconds': 30}
        return root, tasks, settings, result, billing, admission, path, raw

    async def test_held_first_trial_continues_remaining_nineteen_without_replay(self):
        root, tasks, settings, original, billing, admission, path, raw = self.held_setup()
        calls = []

        async def execute(**kwargs):
            calls.append(kwargs['trial_id'])
            result = dict(original, trial_id=kwargs['trial_id'], task_id=kwargs['task_id'],
                          status='verified', billing=billing)
            attempt = root / '.runtime/stage2/scored-trials' / kwargs['trial_id']
            attempt.mkdir()
            (attempt / 'result.json').write_text(json.dumps(result))

        with patch('run_qualification.validate', return_value=settings), \
             patch('run_qualification.run_trial', side_effect=execute), \
             patch('matrix_resume.audit_trial', return_value=billing), patch('builtins.print'):
            first = await run(root, admission)
            second = await run(root, admission)
        self.assertEqual(calls, [f'dev-terminus-2-{i:02d}-{task}' for i, task in enumerate(tasks) if i])
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(first, second)
        self.assertEqual(first['observed_trials'], 20)
        self.assertEqual(first['held_terminal_trials'], 1)
        self.assertFalse(first['paid_expansion_allowed'])
        self.assertIn('systemic_failure_review_required', first['accounting_bounded_reasons'])

    async def test_new_unresolved_billing_stops_after_historical_hold(self):
        root, tasks, settings, original, _, admission, path, raw = self.held_setup()
        calls = []

        async def execute(**kwargs):
            calls.append(kwargs['trial_id'])
            result = dict(original, trial_id=kwargs['trial_id'], task_id=kwargs['task_id'])
            attempt = root / '.runtime/stage2/scored-trials' / kwargs['trial_id']
            attempt.mkdir()
            (attempt / 'result.json').write_text(json.dumps(result))

        with patch('run_qualification.validate', return_value=settings), \
             patch('run_qualification.run_trial', side_effect=execute), patch('builtins.print'):
            with self.assertRaises(RuntimeError):
                await run(root, admission)
        self.assertEqual(calls, [f'dev-terminus-2-01-{tasks[1]}'])
        self.assertEqual(path.read_bytes(), raw)

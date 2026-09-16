import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

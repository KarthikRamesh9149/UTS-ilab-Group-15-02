"""Local real observer/shared lifecycle and durable scored writer; Docker is mocked."""
import asyncio
from copy import copy, deepcopy
from contextlib import ExitStack
import json
from pathlib import Path
import pickle
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import no_cutoff_recovery_result as retained
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_study as study
import scored_trial
from test_no_cutoff_recovery_setup import Environment, SECRET
from trial_execution import execute_phases


class RetentionTests(unittest.IsolatedAsyncioTestCase):
    async def test_success_nonzero_exception_and_not_applicable_retain_only_allowlisted_data(self):
        for environment in (Environment(stdout=SECRET), Environment(code=42, stderr=SECRET),
                Environment(error=RuntimeError(SECRET)), Environment(stdout='UTS_PACKAGE_METADATA_NOT_APPLICABLE\n')):
            with self.subTest(environment=environment):
                observer = retained.RetainedPreparation()
                try: await observer.prepare(environment)
                except RuntimeError: pass
                value = observer.finish()
                self.assertTrue(value['callback_started']); self.assertTrue(value['observation_complete'])
                self.assertNotIn(SECRET, json.dumps(value))
                self.assertFalse(value['paid_launch_ready'])
                self.assertEqual(observer.finish(), value)
                with self.assertRaises(ValueError): await observer.prepare(environment)

    async def test_real_child_setup_cancellation_is_preserved_then_parent_writes_metadata(self):
        observer = retained.RetainedPreparation(); environment = Environment()
        environment.wait = asyncio.Event()
        task = asyncio.create_task(observer.prepare(environment))
        await environment.entered.wait(); task.cancel('local synthetic cancellation')
        with self.assertRaises(asyncio.CancelledError): await task
        value = observer.finish()
        self.assertTrue(value['observation_complete'])
        self.assertEqual(value['observation']['infrastructure_category'], 'preparation_cancelled')
        self.assertIsNone(value['observation']['command']['return_code'])

    async def test_metadata_failure_retains_actual_earlier_observation_incomplete(self):
        observer = retained.RetainedPreparation()
        await observer.prepare(Environment(code=0, stdout=SECRET))
        with patch.object(observer._observer, 'metadata', side_effect=RuntimeError(SECRET)):
            value = observer.finish()
        self.assertFalse(value['observation_complete'])
        self.assertEqual(value['observation']['command']['return_code'], 0)
        self.assertEqual(value['retention_issues'], ['late_metadata_unavailable'])
        self.assertNotIn(SECRET, json.dumps(value))

    async def test_all_diagnostic_reads_failing_do_not_replace_original_exception(self):
        observer = retained.RetainedPreparation(); error = RuntimeError(SECRET)
        with patch.object(observer._observer, 'metadata', side_effect=ValueError(SECRET)):
            with self.assertRaises(RuntimeError) as raised: await observer.prepare(Environment(error=error))
            self.assertIs(raised.exception, error)
            value = observer.finish()
        self.assertIsNone(value['observation']); self.assertFalse(value['observation_complete'])

    async def test_unstarted_settled_and_parent_task_bound(self):
        observer = retained.RetainedPreparation()
        self.assertFalse(observer.finish()['callback_started'])
        other = retained.RetainedPreparation()
        async def cross_task(): return other.finish()
        with self.assertRaises(ValueError): await asyncio.create_task(cross_task())
        for operation in (copy, deepcopy, pickle.dumps):
            with self.assertRaises(TypeError): operation(other)

    async def test_inflight_callback_cannot_be_saved(self):
        observer = retained.RetainedPreparation(); environment = Environment(); environment.wait = asyncio.Event()
        task = asyncio.create_task(observer.prepare(environment)); await environment.entered.wait()
        with self.assertRaises(ValueError): observer.finish()
        environment.wait.set(); await task; self.assertTrue(observer.finish()['observation_complete'])

    async def test_validation_rejects_invented_readiness_completeness_and_diagnostics(self):
        observer = retained.RetainedPreparation(); await observer.prepare(Environment()); value = observer.finish()
        for extra in (dict(paid_launch_ready=True), dict(raw_output=SECRET), dict(observation_complete=False),
                dict(callback_finished=False), dict(retention_issues=['arbitrary'])):
            with self.subTest(extra=extra), self.assertRaises(ValueError): retained.validate(dict(value, **extra))

    def test_empty_shared_context_is_not_agent_execution(self):
        from harbor.models.agent.context import AgentContext
        value = AgentContext().model_dump(mode='json', exclude={'rollout_details'})
        self.assertTrue(retained.empty_agent_context(value))
        self.assertFalse(retained.empty_agent_context(dict(value, n_input_tokens=1)))
        self.assertFalse(retained.empty_agent_context({}))


class ScoredRetentionTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, mode):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        root = Path(temporary.name).resolve(); (root / 'stage2').mkdir()
        (root / 'stage2/input_manifest.json').write_text(json.dumps({'all_task_ids': ['fixture']}))
        observer = retained.RetainedPreparation()
        task = NS(paths=NS(environment_dir=root), has_steps=False, instruction='harmless local fixture',
            config=NS(environment=NS(network_mode=NS(value='public'), build_timeout_sec=1),
                agent=NS(network_mode=None, timeout_sec=180, user=None),
                verifier=NS(network_mode=None, environment=None, timeout_sec=30, user=None)))
        seen = []
        class Env(Environment):
            def __init__(self, **kwargs):
                super().__init__(code=42 if mode == 'nonzero' else 0, stdout=SECRET,
                    error=RuntimeError(SECRET) if mode == 'exception' else None)
            async def exec(self, command, *, timeout_sec):
                if mode == 'cancel': raise asyncio.CancelledError('synthetic')
                return await super().exec(command, timeout_sec=timeout_sec)
            async def start(self, **kwargs): seen.append('start')
            async def stop_service(self, name): seen.append('revoked')
        class Agent:
            async def setup(self, env): seen.append('agent-setup')
            async def run(self, *args): seen.append('agent-run')
        class Verifier:
            def __init__(self, *args): seen.append('verifier')
            async def verify(self): return NS(model_dump=lambda **kwargs: {'rewards': {'reward': 0}})
        class Bridge:
            base_url = 'http://127.0.0.1:1/v1'
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def factory(**kwargs):
            if mode == 'construction': raise RuntimeError('synthetic factory failure')
            return Agent()
        factory.harness = policy.CONDITION
        async def phases(**kwargs):
            self.assertEqual(kwargs['prepare_environment'], observer.prepare)
            return await execute_phases(**kwargs, verifier_factory=Verifier)
        inspection = {'Id': 'a'*64, 'Image': 'sha256:'+'b'*64, 'State': {'Running': False}}
        with ExitStack() as stack:
            replacements = {'check_host': lambda: {}, 'frozen_dataset': lambda _: root,
                'compose_runtime': lambda **kwargs: {}, 'service': lambda *args: inspection,
                'HostModelBridge': Bridge, 'execute_phases': phases, 'docker': lambda *args: '',
                'audit_task': lambda *args: None}
            for key, value in replacements.items(): stack.enter_context(patch.object(scored_trial, key, value))
            stack.enter_context(patch.object(study, 'admit_trial', return_value='c'*64))
            stack.enter_context(patch.object(study, 'preparation', return_value=observer))
            stack.enter_context(patch.object(study, 'require_task_image'))
            stack.enter_context(patch('harbor.models.task.task.Task', return_value=task))
            stack.enter_context(patch('pinned_docker.PinnedImageDockerEnvironment', Env))
            args = dict(root=root, trial_id='synthetic-local', task_id='fixture', stage='final',
                agent_factory=factory, gateway_image=inspection['Image'], guard_image=inspection['Image'],
                setup_timeout_seconds=900, model_settings=policy.SETTINGS,
                accounting_mode='provider-credit-only', recovery=policy.EXPERIMENT)
            if mode in ('cancel', 'construction'):
                with self.assertRaises(asyncio.CancelledError if mode == 'cancel' else RuntimeError):
                    await scored_trial.run_trial(**args)
            else: await scored_trial.run_trial(**args)
            path = root / '.runtime/stage2/scored-trials/synthetic-local/result.json'
            result = json.loads(path.read_bytes())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            before = path.read_bytes()
            with self.assertRaises((FileExistsError, ValueError)): await scored_trial.run_trial(**args)
            self.assertEqual(path.read_bytes(), before)
        return result, seen

    async def test_success_uses_observer_and_original_lifecycle_then_durable_result(self):
        result, seen = await self.run_case('success')
        self.assertEqual(result['status'], 'verified'); self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
        self.assertTrue(result['recovery_preparation']['observation_complete'])
        self.assertIn('agent-run', seen); self.assertIn('verifier', seen)

    async def test_setup_nonzero_and_exception_have_diagnostics_zero_requests_and_no_execution(self):
        for mode in ('nonzero', 'exception'):
            with self.subTest(mode=mode):
                result, seen = await self.run_case(mode)
                self.assertEqual(result['status'], 'setup_failed')
                self.assertTrue(result['recovery_preparation']['observation_complete'])
                self.assertTrue(result['model_revoked']); self.assertEqual(result['billing']['requests'], 0)
                self.assertNotIn('agent-setup', seen); self.assertNotIn('agent-run', seen); self.assertNotIn('verifier', seen)
                self.assertNotIn(SECRET, json.dumps(result))

    async def test_cancellation_result_and_observation_survive_cleanup(self):
        result, seen = await self.run_case('cancel')
        self.assertEqual(result['status'], 'interrupted')
        self.assertTrue(result['recovery_preparation']['observation_complete'])
        self.assertTrue(result['model_revoked']); self.assertEqual(result['billing']['requests'], 0)
        self.assertNotIn('agent-run', seen)
        self.assertTrue(all(result[k+'_removed'] for k in ('containers', 'networks', 'volumes')))

    async def test_pre_callback_failure_is_retained_as_incomplete_not_replayed(self):
        result, seen = await self.run_case('construction')
        self.assertEqual(result['status'], 'infrastructure_failed')
        self.assertFalse(result['recovery_preparation']['callback_started'])
        self.assertFalse(result['recovery_preparation']['observation_complete'])

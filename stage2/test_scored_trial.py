import asyncio
from contextlib import contextmanager, ExitStack
import fcntl
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from scored_trial import run_trial, audit_task
from model_protocol import ModelSettings
from completion_wait import completion_wait_for


class ScoredTrialTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, *, audit_error=False, factory_error=False, leftovers=False,
                       billing_error=False, continuation=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'stage2').mkdir()
            (root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': ['fixture']}))
            task = NS(paths=NS(environment_dir=root), has_steps=False, instruction='fixture',
                config=NS(environment=NS(network_mode=NS(value='public'), build_timeout_sec=1),
                    agent=NS(network_mode=None, timeout_sec=180),
                    verifier=NS(network_mode=None, environment=None)))
            events = []
            class Env:
                def __init__(self, **kwargs): events.append('constructed')
                async def start(self, **kwargs): events.append('start')
                async def stop(self, **kwargs): events.append('stop')
                async def stop_service(self, name): events.append('revoke')
            class Bridge:
                base_url = 'http://127.0.0.1:1234/v1'
                def __init__(bridge_self, container, *, completion_wait_seconds):
                    self.assertEqual(completion_wait_seconds, 240.)
                def __enter__(self): events.append('bridge-start'); return self
                def __exit__(self, *args): events.append('bridge-stop')
            def factory(**kwargs):
                self.assertNotIn('task', kwargs)
                self.assertEqual(kwargs['container_api_base'], 'http://127.0.0.1:8765/v1')
                self.assertEqual(kwargs['agent_timeout_seconds'], 180)
                self.assertEqual(kwargs['completion_wait_seconds'], 240.)
                if factory_error: raise RuntimeError('fixture')
                return object()
            async def phases(**kwargs):
                self.assertIs(kwargs['task'], task)
                self.assertEqual(kwargs['task'].config.agent.timeout_sec, 180)
                await kwargs['revoke_model']()
                events.append('verify')
                return {'status': 'verified', 'model_revoked': True,
                        'verifier_result': {'rewards': {'reward': 0}}}
            def compose(**kwargs):
                self.assertEqual(kwargs['completion_wait_seconds'], 240.)
                return {}
            inspection = {'Id': 'a' * 64, 'Image': 'sha256:' + 'b' * 64, 'State': {'Running': False}}
            args = dict(root=root, trial_id='test', task_id='fixture', stage='development',
                        agent_factory=factory, gateway_image=inspection['Image'],
                        model_settings=ModelSettings(64, 1., 'high'),
                        guard_image=inspection['Image'], setup_timeout_seconds=1)
            with ExitStack() as stack:
                stack.enter_context(patch('deferred_billing.validate_policy',
                                          return_value={'approved': True} if continuation else None))
                def register(runtime, *, kind, trial_id, result_path):
                    saved = json.loads(result_path.read_text())
                    self.assertEqual(saved['status'], 'billing_unresolved')
                    self.assertFalse(saved['billing']['billing_verified'])
                    self.assertTrue(all(saved[key] for key in ('model_revoked', 'containers_removed',
                                                              'networks_removed', 'volumes_removed')))
                    self.assertEqual(kind, 'scored')
                    self.assertEqual(trial_id, 'test')
                    events.append('registered-after-durable-cleanup')
                stack.enter_context(patch('deferred_billing.register_terminal_deferral', side_effect=register))
                derive_wait = stack.enter_context(patch('scored_trial.completion_wait_for',
                                                        wraps=completion_wait_for))
                replacements = {'check_host': lambda: {}, 'frozen_dataset': lambda root: root,
                    'audit_trial': lambda *args: {'billing_verified': True},
                    'collect_receipts': lambda *args, **kwargs: None,
                    'compose_runtime': compose, 'service': lambda *args: inspection,
                    'HostModelBridge': Bridge, 'execute_phases': phases,
                    'docker': lambda *args: 'leftover' if leftovers else ''}
                for key, value in replacements.items(): stack.enter_context(patch('scored_trial.' + key, value))
                if billing_error:
                    stack.enter_context(patch('scored_trial.collect_receipts', side_effect=ValueError('unresolved')))
                stack.enter_context(patch('scored_trial.audit_task', side_effect=RuntimeError('audit') if audit_error else None))
                stack.enter_context(patch('harbor.models.task.task.Task', return_value=task))
                stack.enter_context(patch('pinned_docker.PinnedImageDockerEnvironment', Env))
                if audit_error or factory_error:
                    with self.assertRaises(RuntimeError): await run_trial(**args)
                else:
                    await run_trial(**args)
                derive_wait.assert_called_once_with(180)
                result = json.loads((root / '.runtime/stage2/scored-trials/test/result.json').read_text())
                with self.assertRaises(FileExistsError): await run_trial(**args)
            return result, events

    async def test_shared_phases_and_revocation_are_connected(self):
        result, events = await self.run_case()
        self.assertEqual(result['status'], 'verified')
        self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
        self.assertLess(events.index('revoke'), events.index('verify'))
        self.assertTrue(all(result[x + '_removed'] for x in ['containers', 'networks', 'volumes']))

    async def test_pre_agent_audit_failure_cleans_and_preserves(self):
        result, events = await self.run_case(audit_error=True)
        self.assertEqual(result['status'], 'infrastructure_failed')
        self.assertNotIn('bridge-start', events)
        self.assertIn('stop', events)

    async def test_factory_failure_still_destroys_runtime(self):
        result, events = await self.run_case(factory_error=True)
        self.assertEqual(result['status'], 'infrastructure_failed')
        self.assertIn('stop', events)
        self.assertIn('bridge-stop', events)

    async def test_leftovers_prevent_verified_status(self):
        result, events = await self.run_case(leftovers=True)
        self.assertEqual(result['status'], 'cleanup_failed')

    async def test_terminal_deferral_is_registered_only_after_durable_cleanup(self):
        result, events = await self.run_case(billing_error=True, continuation=True)
        self.assertEqual(result['status'], 'billing_unresolved')
        self.assertFalse(result['billing']['billing_verified'])
        self.assertGreater(events.index('registered-after-durable-cleanup'), events.index('stop'))

    async def test_no_policy_or_failed_cleanup_cannot_register_deferral(self):
        for options in ({'continuation': False}, {'continuation': True, 'leftovers': True}):
            result, events = await self.run_case(billing_error=True, **options)
            self.assertNotIn('registered-after-durable-cleanup', events)

    async def test_live_owner_lock_prevents_even_preflight(self):
        with tempfile.TemporaryDirectory() as directory:
            runtime = Path(directory) / '.runtime/stage2'
            runtime.mkdir(parents=True, mode=0o700)
            with (runtime / 'scored.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                with patch('scored_trial.check_host') as health:
                    with self.assertRaises(BlockingIOError):
                        await run_trial(root=directory, trial_id='x', task_id='x', stage='development',
                            agent_factory=lambda **kwargs: None, gateway_image='', guard_image='', setup_timeout_seconds=1,
                            model_settings=ModelSettings(64, 1., 'high'))
                    health.assert_not_called()


class MountAuditTests(unittest.TestCase):
    def test_unapproved_host_mount_rejected(self):
        config = NS(cpus=1, memory_mb=256)
        paths = NS(agent_dir=Path('/tmp/test-agent'), verifier_dir=Path('/tmp/test-verifier'))
        inspected = {'HostConfig': {'Privileged': False, 'CapAdd': [], 'PortBindings': {},
            'CapDrop': ['NET_ADMIN', 'NET_RAW'], 'NetworkMode': 'container:abc',
            'SecurityOpt': ['no-new-privileges:true'],
            'NanoCpus': 10**9, 'Memory': 256 * 1024**2},
            'Mounts': [{'Type': 'bind', 'Source': str(paths.agent_dir.resolve()), 'Destination': '/logs/agent'},
                       {'Type': 'bind', 'Source': str(paths.verifier_dir.resolve()), 'Destination': '/logs/verifier'}]}
        audit_task(inspected, config, paths)
        inspected['Mounts'].append({'Type': 'bind', 'Source': '/Users', 'Destination': '/host'})
        with self.assertRaises(RuntimeError): audit_task(inspected, config, paths)

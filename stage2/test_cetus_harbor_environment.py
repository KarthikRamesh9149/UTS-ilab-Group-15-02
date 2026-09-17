import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock

from harbor.environments.base import BaseEnvironment
from harbor.models.task.config import EnvironmentConfig, NetworkPolicy, NetworkMode
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from cetus_harbor_environment import CetusAttachedEnvironment
from cetus_instance_transport import CommandResult
from local_trace import PhaseRecorder, TraceSpool
from local_observation import DetailObserver
from trial_execution import execute_phases


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def create(self, root, **overrides):
        transport = AsyncMock()
        transport.exec.return_value = CommandResult(0, b'fixture', b'')
        stop = AsyncMock()
        kwargs = dict(environment_dir=root, environment_name='fixture', session_id='fixture',
                      trial_paths=TrialPaths(root / 'trial'), task_env_config=EnvironmentConfig(),
                      transport=transport, stop_instance=stop,
                      network_policy=NetworkPolicy(network_mode=NetworkMode.NO_NETWORK))
        kwargs.update(overrides)
        return CetusAttachedEnvironment(**kwargs), transport, stop

    async def test_real_base_class_and_exec_result(self):
        with tempfile.TemporaryDirectory() as directory:
            env, transport, stop = self.create(Path(directory))
            self.assertIsInstance(env, BaseEnvironment)
            with self.assertRaises(RuntimeError): await env.exec('true')
            await env.start()
            transport.exec.return_value = CommandResult(7, b'hello\xff', b'err')
            result = await env.exec('fixture', timeout_sec=5)
            self.assertEqual(result.return_code, 7)
            self.assertEqual(result.stdout, 'hello\ufffd')
            await env.stop()
            await env.stop()
            stop.assert_awaited_once()
            with self.assertRaises(RuntimeError): await env.exec('true')
            with self.assertRaises(RuntimeError): await env.start()

    async def test_harbor_scoped_env_user_and_output(self):
        with tempfile.TemporaryDirectory() as directory:
            env, transport, _ = self.create(Path(directory), persistent_env={'X': 'persistent'})
            await env.start()
            callback = AsyncMock()
            with env.with_default_user('root'), env.scoped_exec_env({'X': 'scoped'}), env.scoped_output_callback(callback):
                await env.exec('fixture', env={'X': 'call'})
            self.assertEqual(transport.exec.call_args.kwargs['env']['X'], 'scoped')
            self.assertEqual(transport.exec.call_args.kwargs['user'], 'root')
            callback.assert_awaited_once_with('fixture', 'stdout')
            await env.exec('fixture')
            self.assertEqual(transport.exec.call_args.kwargs['env']['X'], 'persistent')
            self.assertIsNone(transport.exec.call_args.kwargs['user'])

    async def test_all_file_methods_use_transport(self):
        with tempfile.TemporaryDirectory() as directory:
            env, transport, _ = self.create(Path(directory))
            await env.start()
            for name in ('upload_file', 'download_file', 'upload_dir', 'download_dir'):
                await getattr(env, name)('source', 'destination')
                getattr(transport, name).assert_awaited_once_with('source', 'destination')

    async def test_stop_failure_is_retryable(self):
        with tempfile.TemporaryDirectory() as directory:
            env, _, stop = self.create(Path(directory))
            await env.start()
            stop.side_effect = [RuntimeError('fixture'), None]
            with self.assertRaises(RuntimeError): await env.stop()
            with self.assertRaises(RuntimeError): await env.exec('true')
            with self.assertRaises(RuntimeError): await env.start()
            await env.stop()
            self.assertEqual(stop.await_count, 2)

    async def test_failed_start_can_be_cleaned_up(self):
        with tempfile.TemporaryDirectory() as directory:
            env, transport, stop = self.create(Path(directory))
            transport.exec.return_value = CommandResult(1, b'', b'fixture failure')
            with self.assertRaises(RuntimeError): await env.start()
            with self.assertRaises(RuntimeError): await env.start()
            await env.stop()
            stop.assert_awaited_once()

    async def test_no_silent_network_or_resource_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            for kwargs in ({'network_policy': NetworkPolicy()}, {'cpu_enforcement_policy': 'limit'},
                           {'memory_enforcement_policy': 'limit'},
                           {'phase_network_policies': [NetworkPolicy()]}):
                with self.assertRaises((ValueError, NotImplementedError)):
                    self.create(Path(directory), **kwargs)
            env, transport, _ = self.create(Path(directory))
            self.assertFalse(env.resource_capabilities().cpu_limit)
            self.assertFalse(env.resource_capabilities().memory_limit)
            with self.assertRaises(NotImplementedError): await env.start(force_build=True)
            transport.exec.assert_not_awaited()

    async def test_real_harbor_verifier_lifecycle_with_mocked_container(self):
        events = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = Task(Path(__file__).parent / 'fixtures/lifecycle')
            env, transport, stop = self.create(root)
            paths = env.trial_paths
            await env.start()
            async def upload(source, target):
                events.append('upload-tests')
                self.assertEqual(Path(source), task.paths.tests_dir)
                self.assertEqual(target, '/tests')
            async def download(source, target):
                events.append('download-reward')
                Path(target).mkdir(parents=True, exist_ok=True)
                (Path(target) / 'reward.txt').write_text('0\n')
            transport.upload_dir.side_effect = upload
            transport.download_dir.side_effect = download
            async def stop_fixture(): events.append('stop')
            stop.side_effect = stop_fixture
            class Agent:
                async def setup(self, environment): events.append('setup')
                async def run(self, instruction, environment, context):
                    events.append('agent')
                    await environment.exec('fixture-agent-command')
            async def revoke(): events.append('revoke')
            observer = PhaseRecorder(TraceSpool(root / 'spool'), trial_id='fixture-baseline-0',
                task_id='fixture', harness='openhands', protocol_sha256='a' * 64)
            details = DetailObserver(observer)
            env.detail_observer = details
            # Default verifier_factory is the real Harbor Verifier. Only the
            # container is mocked; its synthetic reward is explicitly zero.
            result = await execute_phases(agent=Agent(), environment=env, task=task,
                paths=paths, revoke_model=revoke, setup_timeout_seconds=2, phase_observer=observer)
            self.assertEqual(result['status'], 'verified')
            self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
            self.assertEqual(result['cleanup_errors'], [])
            self.assertLess(events.index('revoke'), events.index('upload-tests'))
            self.assertEqual(events[-1], 'stop')
            traces = observer.spool.events()
            self.assertEqual({e['kind'] for e in traces}, {'setup', 'agent', 'verifier', 'cleanup', 'trial', 'tool'})
            self.assertEqual(next(e['reward'] for e in traces if e['kind'] == 'verifier'), 0)
            tools = [e for e in traces if e['kind'] == 'tool']
            self.assertEqual(len(tools), transport.exec.await_count - 1)  # exclude pre-trial liveness
            self.assertTrue(all(e['metrics']['tool_calls'] == 1 for e in tools))
            self.assertNotIn('fixture-agent-command', str(traces))
            self.assertFalse(details.errors)


if __name__ == '__main__':
    unittest.main()

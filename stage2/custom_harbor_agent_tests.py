import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from harbor.models.agent.context import AgentContext
from custom_harbor_agent import CustomHarborAgent
from custom_runner_tests import SequenceModel, completion
from custom_backend_tests import FakeEnvironment
from langsmith.run_helpers import get_tracing_context


class CustomHarborTests(unittest.IsolatedAsyncioTestCase):
    def make(self, directory, sequence):
        model = SequenceModel()
        model._sequence = sequence
        with patch('custom_harbor_agent.gateway_model', return_value=model):
            agent = CustomHarborAgent(directory, condition='C0', api_base='http://127.0.0.1:123/v1',
                trial_token='synthetic-not-logged', max_output_tokens=64, max_model_calls=4,
                trial_timeout_seconds=10, completion_wait_seconds=721.5)
        return agent

    def test_completion_wait_is_forwarded_without_changing_official_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch('custom_harbor_agent.gateway_model') as model:
                agent = CustomHarborAgent(directory, condition='C0', api_base='http://127.0.0.1:123/v1',
                    trial_token='synthetic', max_output_tokens=64, max_model_calls=4,
                    trial_timeout_seconds=10, completion_wait_seconds=721.5,
                    temperature=1., reasoning_effort='high')
            model.assert_called_once_with('http://127.0.0.1:123/v1', 'synthetic', max_output_tokens=64,
                temperature=1., reasoning_effort='high', completion_wait_seconds=721.5)
            self.assertEqual(agent.timeout, 10)
            self.assertEqual(agent.max_model_calls, 4)

    def test_completion_wait_is_required_and_validated_before_model_construction(self):
        with tempfile.TemporaryDirectory() as directory, patch('custom_harbor_agent.gateway_model') as model:
            args = dict(condition='C0', api_base='http://127.0.0.1:123/v1', trial_token='synthetic',
                max_output_tokens=64, max_model_calls=4, trial_timeout_seconds=10)
            with self.assertRaises(TypeError):
                CustomHarborAgent(directory, **args)
            for value in [True, False, None, '721.5', float('nan'), float('inf'), -1, 0]:
                with self.subTest(value=value), self.assertRaises(ValueError):
                    CustomHarborAgent(directory, **args, completion_wait_seconds=value)
            model.assert_not_called()

    async def test_lifecycle_writes_trajectory_not_secret_or_score(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make(directory, [completion()])
            environment = FakeEnvironment()
            context = AgentContext()
            await agent.setup(environment)
            await agent.run('Synthetic instruction', environment, context)
            path = Path(directory) / 'custom-trajectory.json'
            result = json.loads(path.read_text())
            self.assertEqual(result['model_attempts'], 1)
            self.assertIsNone(result['benchmark_success'])
            self.assertEqual(result['outcome']['outcome'], 'agent_reported_complete')
            self.assertNotIn('synthetic-not-logged', path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIsNone(context.cost_usd)
            with self.assertRaises(RuntimeError):
                await agent.run('Replay', environment, context)

    async def test_failure_writes_partial_evidence_without_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make(directory, [RuntimeError('synthetic failure')])
            context = AgentContext()
            with self.assertRaises(RuntimeError):
                await agent.run('Synthetic', FakeEnvironment(), context)
            result = json.loads((Path(directory) / 'custom-trajectory.json').read_text())
            self.assertEqual(result['error_type'], 'RuntimeError')
            self.assertEqual(result['model_attempts'], 1)
            self.assertIsNone(result['outcome'])

    async def test_existing_attempt_marker_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            first = self.make(directory, [completion()])
            await first.run('Synthetic', FakeEnvironment(), AgentContext())
            second = self.make(directory, [completion()])
            with self.assertRaises(FileExistsError):
                await second.run('Synthetic', FakeEnvironment(), AgentContext())

    async def test_vendor_default_tracing_is_explicitly_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make(directory, [completion()])
            async def run(runner, instruction, **kwargs):
                self.assertIs(get_tracing_context()['enabled'], False)
                return {'outcome': 'synthetic', 'benchmark_success': None}
            with patch('custom_harbor_agent.CustomRunner.run', new=run):
                await agent.run('Synthetic', FakeEnvironment(), AgentContext())

    async def test_cleanup_is_exposed_for_post_verifier_lifecycle(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = self.make(directory, [completion()])
            await agent.run('Synthetic', FakeEnvironment(), AgentContext())
            self.assertTrue(agent.runner.defer_job_cleanup)
            agent.runner.jobs.close = AsyncMock()
            await agent.cleanup_after_verification()
            agent.runner.jobs.close.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()

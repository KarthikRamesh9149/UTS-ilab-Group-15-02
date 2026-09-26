import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from custom_python_runtime import PythonBundle
from custom_portable_backend import ContainerCaptureError, PortableHarborSandbox
from custom_text_transport import TextGatewayChatOpenAI
from portable_custom_agent import PortableCustomHarborAgent
from retry_policy import SETTINGS


class PortableAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = dict(condition='C0', api_base='http://127.0.0.1:9/v1',
            trial_token='synthetic-only', trial_timeout_seconds=90,
            completion_wait_seconds=150, python_bundle=PythonBundle(self.root / 'fixture.tar.gz', 'a' * 64))

    def agent(self):
        return PortableCustomHarborAgent(self.root / 'agent', **self.args)

    def test_revision_is_explicit_and_common_model_limits_stay_unchanged(self):
        agent = self.agent()
        self.assertEqual(agent.version(), 'stage2-candidate-0.3.0')
        self.assertIsInstance(agent.model, TextGatewayChatOpenAI)
        self.assertEqual((agent.model.max_tokens, agent.model.temperature, agent.model.top_p), (384000, 1., 1.))
        self.assertEqual(agent.model.extra_body, {'reasoning': {'effort': 'high'}})
        self.assertEqual(agent.model.max_retries, 0)
        self.assertIsNone(agent.execution_metadata()['max_model_calls'])
        self.assertEqual(agent.execution_metadata()['model_protocol_sha256'], SETTINGS.fingerprint())

    async def test_only_prepared_environment_can_reach_backend(self):
        agent = self.agent()
        environment, prepared = SimpleNamespace(), SimpleNamespace()
        with self.assertRaises(RuntimeError):
            agent.backend(environment)
        with patch('portable_custom_agent.prepare_python', new=AsyncMock(return_value=(prepared, {'sha256': 'a' * 64}))):
            await agent.setup(environment)
            self.assertIsInstance(agent.backend(environment), PortableHarborSandbox)
            self.assertIs(agent.backend(environment).environment, prepared)
            with self.assertRaises(RuntimeError):
                agent.backend(SimpleNamespace())
            with self.assertRaises(RuntimeError):
                await agent.setup(environment)

    def test_failure_metadata_contains_no_private_exception_text(self):
        agent = self.agent()
        for exc in (RuntimeError('private request body'), ContainerCaptureError('helper_exit', 124)):
            try:
                raise exc
            except RuntimeError as captured:
                result = agent.failure_metadata(captured)
            self.assertNotIn('private request body', json.dumps(result))
            self.assertTrue(result['frames'])
        self.assertEqual(result['reason'], 'helper_exit')
        self.assertEqual(result['return_code'], 124)


if __name__ == '__main__':
    unittest.main()

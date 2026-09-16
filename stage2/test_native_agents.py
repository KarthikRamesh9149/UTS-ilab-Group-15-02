import os
os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import tempfile
from unittest.mock import patch

from native_agents import ModelSettings, agent_factory, CompatibleOpenHands
from gateway_policy import MODEL, prepare_request


class FactoryTests(unittest.TestCase):
    def test_real_native_constructors_need_no_provider_key(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = ModelSettings(8192, 1., 'high')
            for name in ['terminus-2', 'openhands']:
                agent = agent_factory(name, settings)(paths=NS(agent_dir=Path(directory)),
                    host_api_base='http://127.0.0.1:1234/v1',
                    container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                    agent_timeout_seconds=60)
                self.assertEqual(agent.model_name, 'openai/' + MODEL)

    def test_explicit_settings_validation(self):
        for args in [(True, 1., 'high'), (2048, float('nan'), 'high'), (2048, 1., 'off')]:
            with self.assertRaises(ValueError): ModelSettings(*args)
        with self.assertRaises(ValueError): agent_factory('other', ModelSettings(2048, 1., 'high'))

    def test_baselines_share_settings_without_equal_iteration_override(self):
        settings = ModelSettings(8192, 1., 'high')
        args = dict(paths=NS(agent_dir=Path('/fixture')), host_api_base='http://127.0.0.1:1234/v1',
                    container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic', agent_timeout_seconds=60)
        with patch('native_agents.NoRetryTerminus') as terminus, patch('native_agents.CompatibleOpenHands') as oh:
            agent_factory('terminus-2', settings)(**args)
            agent_factory('openhands', settings)(**args)
            for constructor in [terminus, oh]:
                cfg = constructor.call_args.kwargs
                self.assertEqual(cfg['model_name'], 'openai/' + MODEL)
                self.assertEqual(cfg['temperature'], 1.)
                self.assertEqual(cfg['reasoning_effort'], 'high')
                self.assertEqual(cfg['model_info']['max_output_tokens'], 8192)
                self.assertNotIn('max_turns', cfg)
                self.assertNotIn('max_iterations', cfg)
            self.assertEqual(oh.call_args.kwargs['version'], '0.62.0')
            self.assertEqual(oh.call_args.kwargs['python_version'], '3.12')
            self.assertEqual(terminus.call_args.kwargs['llm_kwargs']['num_retries'], 0)

    def test_reasoning_alias_has_identical_canonical_request(self):
        base = dict(model=MODEL, max_tokens=8192, messages=[{'role': 'user', 'content': 'fixture'}])
        left = prepare_request(dict(base, reasoning_effort='high'))
        right = prepare_request(dict(base, reasoning={'effort': 'high'}))
        self.assertEqual(left, right)
        for value in ['off', None, True]:
            with self.assertRaises(ValueError): prepare_request(dict(base, reasoning_effort=value))
        with self.assertRaises(ValueError):
            prepare_request(dict(base, reasoning_effort='high', reasoning={'effort': 'low'}))


class InstallerTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_compatibility_pins_are_added(self):
        calls = []
        class Receiver:
            async def ensure_system_dependencies(self, env, deps): calls.append(deps)
            async def exec_as_root(self, env, command): calls.append(command)
            async def exec_as_agent(self, env, command): calls.append(command)
        await CompatibleOpenHands.install(Receiver(), NS(default_user='root'))
        for package in ['openhands-ai==0.62.0', 'openhands-agent-server==1.0.0a6',
                        'openhands-sdk==1.0.0a6', 'openhands-tools==1.0.0a6']:
            self.assertIn(package, calls[-1])
        self.assertIn('uv python install 3.12', calls[-1])
        self.assertIn('openhands.core.main --version', calls[-1])

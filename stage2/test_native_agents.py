import os
os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
import tempfile
import ast
import json
import re
from unittest.mock import patch, AsyncMock

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
                    agent_timeout_seconds=60, completion_wait_seconds=720)
                self.assertEqual(agent.model_name, 'openai/' + MODEL)
                if name == 'terminus-2':
                    self.assertEqual(agent._llm._llm_kwargs['timeout'], 720.)
                    self.assertEqual(agent._llm._llm_kwargs['num_retries'], 0)
                else:
                    self.assertEqual(agent._get_env('LLM_TIMEOUT'), '720')

    def test_terminus_preserves_fractional_completion_wait(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = agent_factory('terminus-2', ModelSettings(8192, 1., 'high'))(
                paths=NS(agent_dir=Path(directory)), host_api_base='http://127.0.0.1:1234/v1',
                container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                agent_timeout_seconds=60, completion_wait_seconds=721.5)
            self.assertEqual(agent._llm._llm_kwargs['timeout'], 721.5)

    def test_openhands_rejects_fractional_wait_before_constructor(self):
        with patch('native_agents.CompatibleOpenHands') as constructor:
            with self.assertRaisesRegex(ValueError, 'integral completion wait'):
                agent_factory('openhands', ModelSettings(8192, 1., 'high'))(
                    paths=NS(agent_dir=Path('/fixture')), host_api_base='http://127.0.0.1:1234/v1',
                    container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                    agent_timeout_seconds=60, completion_wait_seconds=721.5)
            constructor.assert_not_called()

    def test_openhands_integral_wait_retains_integer_environment_format(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = agent_factory('openhands', ModelSettings(8192, 1., 'high'))(
                paths=NS(agent_dir=Path(directory)), host_api_base='http://127.0.0.1:1234/v1',
                container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                agent_timeout_seconds=180, completion_wait_seconds=240.0)
            timeout_env = agent._get_env('LLM_TIMEOUT')
            self.assertEqual(timeout_env, '240')
            self.assertEqual(int(timeout_env), 240)

    def test_real_custom_constructors_preserve_supplied_wait_and_official_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            for name, parent in [('C0', None), ('C1', None), ('C2', 'C1')]:
                with self.subTest(harness=name):
                    agent = agent_factory(name, ModelSettings(8192, 1., 'high'),
                        custom_max_model_calls=4, parent=parent)(
                        paths=NS(agent_dir=Path(directory)), host_api_base='http://127.0.0.1:1234/v1',
                        container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                        agent_timeout_seconds=60, completion_wait_seconds=721.5)
                    self.assertEqual(agent.model.request_timeout, 721.5)
                    self.assertEqual(agent.model.max_retries, 0)
                    self.assertEqual(agent.model.max_tokens, 8192)
                    self.assertEqual(agent.max_model_calls, 4)
                    self.assertEqual(agent.timeout, 60)
                    self.assertEqual(agent.condition.parent, parent)

    def test_all_factories_require_valid_explicit_completion_wait(self):
        args = dict(paths=NS(agent_dir=Path('/fixture')), host_api_base='http://127.0.0.1:1234/v1',
                    container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                    agent_timeout_seconds=60)
        for name in ['terminus-2', 'openhands', 'C0', 'C1', 'C2']:
            create = agent_factory(name, ModelSettings(8192, 1., 'high'),
                custom_max_model_calls=4 if name.startswith('C') else None,
                parent='C0' if name == 'C2' else None)
            with self.subTest(harness=name, value='missing'), self.assertRaises(TypeError):
                create(**args)
            for value in [True, False, None, '721.5', float('nan'), float('inf'), -1, 0]:
                with self.subTest(harness=name, value=value), self.assertRaises(ValueError):
                    create(**args, completion_wait_seconds=value)

    def test_explicit_settings_validation(self):
        for args in [(True, 1., 'high'), (2048, float('nan'), 'high'), (2048, 1., 'off')]:
            with self.assertRaises(ValueError): ModelSettings(*args)
        with self.assertRaises(ValueError): agent_factory('other', ModelSettings(2048, 1., 'high'))

    def test_baselines_share_settings_without_equal_iteration_override(self):
        settings = ModelSettings(8192, 1., 'high')
        args = dict(paths=NS(agent_dir=Path('/fixture')), host_api_base='http://127.0.0.1:1234/v1',
                    container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                    agent_timeout_seconds=60, completion_wait_seconds=720)
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
            self.assertEqual(ast.literal_eval(oh.call_args.kwargs['extra_env']['LLM_COMPLETION_KWARGS']),
                             {'extra_body': {'reasoning': {'effort': 'high'}}})
            self.assertEqual(oh.call_args.kwargs['extra_env']['LLM_TIMEOUT'], '720')
            self.assertEqual(terminus.call_args.kwargs['llm_kwargs']['timeout'], 720.)
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


class TerminusRetryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.agent = agent_factory('terminus-2', ModelSettings(8192, 1., 'high'))(
            paths=NS(agent_dir=Path(directory.name)), host_api_base='http://127.0.0.1:1234/v1',
            container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
            agent_timeout_seconds=60, completion_wait_seconds=721.5)

    async def test_native_query_does_not_retry_uncertain_connection_failure(self):
        for failure in (TimeoutError('synthetic timeout'), ConnectionError('synthetic disconnect')):
            with self.subTest(failure=type(failure).__name__):
                chat = NS(chat=AsyncMock(side_effect=failure))
                with patch.object(self.agent.logger, 'error') as log_error:
                    with self.assertRaises(type(failure)) as caught:
                        await self.agent._query_llm(chat, 'synthetic prompt',
                            original_instruction='synthetic instruction', session=NS())
                self.assertIs(caught.exception, failure)
                chat.chat.assert_awaited_once_with('synthetic prompt', **self.agent._llm_call_kwargs)
                log_error.assert_called_once()
                self.assertEqual(self.agent._api_request_times, [])

    async def test_native_query_preserves_success_response_settings_and_timing(self):
        response = NS(content='synthetic response')
        chat = NS(chat=AsyncMock(return_value=response))
        result = await self.agent._query_llm(chat, 'synthetic prompt',
            original_instruction='synthetic instruction', session=NS())
        self.assertIs(result, response)
        chat.chat.assert_awaited_once_with('synthetic prompt', max_tokens=8192,
            extra_body={'reasoning': {'effort': 'high'}})
        self.assertEqual(len(self.agent._api_request_times), 1)
        self.assertGreaterEqual(self.agent._api_request_times[0], 0)


class InstallerTests(unittest.IsolatedAsyncioTestCase):
    async def test_connection_extras_reach_native_run_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            agent = agent_factory('openhands', ModelSettings(8192, 1., 'high'))(
                paths=NS(agent_dir=Path(directory)), host_api_base='http://127.0.0.1:1234/v1',
                container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                agent_timeout_seconds=60, completion_wait_seconds=720)
            original = {'LLM_MODEL': agent.model_name}
            with patch('harbor.agents.installed.openhands.OpenHands.exec_as_agent', new_callable=AsyncMock) as execute:
                await agent.exec_as_agent(NS(), command='native-command', env=original)
                forwarded = execute.call_args.kwargs['env']
                self.assertEqual(forwarded['LLM_TIMEOUT'], '720')
                self.assertEqual(ast.literal_eval(forwarded['LLM_COMPLETION_KWARGS']),
                                 {'extra_body': {'reasoning': {'effort': 'high'}}})
                self.assertEqual(original, {'LLM_MODEL': agent.model_name})

    async def test_only_compatibility_pins_are_added(self):
        calls = []
        class Receiver:
            async def ensure_system_dependencies(self, env, deps): calls.append(deps)
            async def exec_as_root(self, env, command): calls.append(command)
            async def exec_as_agent(self, env, command): calls.append(command)
        uploads = []
        async def upload_file(**kwargs): uploads.append(kwargs)
        await CompatibleOpenHands.install(Receiver(), NS(default_user='root', upload_file=upload_file))
        self.assertEqual(uploads[0]['source_path'], Path(__file__).with_name('openhands-requirements.lock'))
        self.assertEqual(uploads[0]['target_path'], '/opt/openhands-requirements.lock')
        self.assertIn('--require-hashes -r /opt/openhands-requirements.lock', calls[-1])
        self.assertIn('uv python install 3.12', calls[-1])
        self.assertIn('openhands.core.main --version', calls[-1])

    def test_lock_preserves_fixture_versions_and_hashes(self):
        stage = Path(__file__).parent
        normalize = lambda name: re.sub(r'[-_.]+', '-', name).lower()
        expected = {normalize(name): version for name, version in
                    json.loads((stage / 'openhands_fixture_audit.json').read_text())['installed_packages']}
        raw = (stage / 'openhands-requirements.lock').read_text()
        entries = re.findall(r'^([\w.-]+)==([^\s]+) \\\n((?:    --hash=sha256:[a-f0-9]{64}(?: \\)?\n)+)', raw, re.M)
        actual = {normalize(name): version for name, version, hashes in entries}
        self.assertEqual(actual, expected)
        self.assertEqual(len(entries), 350)

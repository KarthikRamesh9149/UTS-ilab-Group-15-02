"""Offline candidate checks: real graph/client, synthetic task and provider."""
import asyncio
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from harbor.models.agent.context import AgentContext
from langchain_core.messages import AIMessage
from langsmith.run_helpers import get_tracing_context

from corrected_custom_agent import CorrectedCustomHarborAgent, agent_factory
from custom_backend import HarborSandbox
from custom_backend_tests import FakeEnvironment
from custom_control import Condition
from custom_harbor_agent import CustomHarborAgent
from custom_model import gateway_model
from custom_runner import CustomRunner, ModelLimitReached, TrialModelLimit
from custom_runner_tests import SequenceModel, completion
from credit_only_accounting import summarise
from credit_only_policy import POLICY as CREDIT_POLICY, POLICY_FILE as CREDIT_FILE
from gateway_policy import MODEL
from host_model_bridge import HostModelBridge
from retry_gateway import RetrySession
from retry_policy import SETTINGS, POLICY, POLICY_FILE
from retry_runtime import activate, deadline_for
from scored_gateway import durable_json, private_directory
from test_retry_gateway import Clock, Event, Flaky


class CorrectedRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_graph_can_exceed_historical_100_calls(self):
        model = SequenceModel()
        model._sequence = [AIMessage(content='', tool_calls=[dict(
            name='execute', id=f'synthetic-{i}', args={'command': 'printf fixture'})])
            for i in range(103)] + [completion()]
        runner = CustomRunner(model, HarborSandbox(FakeEnvironment(), identifier='offline'),
            Condition('C0'), max_model_calls=None)
        outcome = await runner.run('Synthetic commands only', timeout_seconds=45)
        self.assertEqual(runner.model_limit.attempts, 104)
        self.assertEqual(len(model._calls), 104)
        self.assertEqual(outcome['outcome'], 'agent_reported_complete')
        self.assertIsNone(outcome['benchmark_success'])
        self.assertEqual(runner.graph_recursion_limit, sys.maxsize)
        self.assertFalse({'task', 'write_todos'} & model._tool_names)

    async def test_explicit_legacy_limits_are_unchanged(self):
        model = SequenceModel()
        model._sequence = [AIMessage(content='Incomplete'), completion()]
        runner = CustomRunner(model, HarborSandbox(FakeEnvironment(), identifier='offline'),
            Condition('C0'), max_model_calls=1)
        with self.assertRaises(ModelLimitReached):
            await runner.run('Synthetic', timeout_seconds=10)
        self.assertEqual(runner.graph_recursion_limit, 10000)
        self.assertEqual(runner.model_limit.attempts, 1)

    async def test_no_call_cap_does_not_disable_wall_clock_timeout(self):
        model = SequenceModel()
        runner = CustomRunner(model, HarborSandbox(FakeEnvironment(), identifier='offline'),
            Condition('C0'), max_model_calls=None)
        async def stalled(*args, **kwargs):
            await asyncio.sleep(10)
            yield {'messages': []}
        runner.graph.astream = stalled
        runner.jobs.close = AsyncMock()
        with self.assertRaises(TimeoutError):
            await runner.run('Synthetic', timeout_seconds=.01)
        runner.jobs.close.assert_awaited_once()

    async def test_none_is_explicit_not_a_zero_or_omitted_default(self):
        backend = HarborSandbox(FakeEnvironment(), identifier='offline')
        for value in (0, -1, True, False, 1., '100', float('inf'), float('nan')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CustomRunner(SequenceModel(), backend, Condition('C0'), max_model_calls=value)
        with self.assertRaises(TypeError):
            CustomRunner(SequenceModel(), backend, Condition('C0'))
        counter = TrialModelLimit(None)
        for _ in range(101):
            await counter.abefore_model({}, None)
        self.assertEqual(counter.attempts, 101)


class CorrectedAdapterTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.arguments = dict(condition='C0', api_base='http://127.0.0.1:123/v1',
            trial_token='synthetic-private-token', trial_timeout_seconds=10,
            completion_wait_seconds=70)

    def agent(self, sequence, **overrides):
        model = SequenceModel()
        model._sequence = sequence
        with patch('corrected_custom_agent.gateway_model', return_value=model):
            agent = CorrectedCustomHarborAgent(self.root / 'agent', **(self.arguments | overrides))
        return agent

    def test_client_matches_corrected_protocol_and_has_no_sdk_retries(self):
        agent = CorrectedCustomHarborAgent(self.root / 'agent', **self.arguments)
        self.assertEqual(agent.model.model_name, MODEL)
        self.assertEqual(agent.model.max_tokens, 384000)
        self.assertEqual(agent.model.temperature, 1.)
        self.assertEqual(agent.model.top_p, 1.)
        self.assertEqual(agent.model.extra_body, {'reasoning': {'effort': 'high'}})
        self.assertEqual(agent.model.max_retries, 0)
        self.assertEqual(agent.model.root_async_client.max_retries, 0)
        self.assertEqual(agent.model.request_timeout, 70)
        self.assertEqual(agent.timeout, 10)
        self.assertEqual(agent.execution_metadata()['model_protocol_sha256'], SETTINGS.fingerprint())
        self.assertIsNone(agent.execution_metadata()['max_model_calls'])

    def test_model_call_budget_and_sampling_overrides_are_not_accepted(self):
        for name, value in dict(model_name='other', max_model_calls=100,
                max_output_tokens=8192, temperature=0., top_p=.5,
                reasoning_effort='low', budget_usd='.023').items():
            with self.subTest(name=name), self.assertRaises(TypeError):
                CorrectedCustomHarborAgent(self.root / 'agent', **self.arguments, **{name: value})

    def test_invalid_deadlines_fail_before_client_construction(self):
        for name in ('trial_timeout_seconds', 'completion_wait_seconds'):
            for value in (None, True, False, 0, -1, '900', float('nan'), float('inf'), 10**400):
                with self.subTest(name=name, value=value), patch('corrected_custom_agent.gateway_model') as model:
                    with self.assertRaises(ValueError):
                        CorrectedCustomHarborAgent(self.root / 'agent', **(self.arguments | {name: value}))
                    model.assert_not_called()

    def test_legacy_adapter_still_requires_a_positive_call_cap(self):
        with self.assertRaises(ValueError):
            CustomHarborAgent(self.root / 'legacy', **self.arguments,
                max_output_tokens=64, max_model_calls=None)

    def test_top_p_validation_is_explicit(self):
        for value in (True, False, 0, 2, '1', float('nan'), float('inf')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                gateway_model(self.arguments['api_base'], 'synthetic',
                    max_output_tokens=384000, completion_wait_seconds=70, top_p=value)

    async def test_setup_checks_the_python_binary_actually_used_by_backend(self):
        agent = self.agent([completion()])
        environment = FakeEnvironment()
        await agent.setup(environment)
        self.assertIn('command -v python3', environment.calls[0][0])
        environment.exec = AsyncMock(return_value=SimpleNamespace(return_code=1))
        with self.assertRaises(RuntimeError):
            await agent.setup(environment)

    async def test_private_evidence_retains_version_count_and_unknown_score(self):
        agent = self.agent([completion()])
        context = AgentContext(metadata={'preserved': True})
        await agent.run('Synthetic fixture', FakeEnvironment(), context)
        path = self.root / 'agent/custom-trajectory.json'
        result = json.loads(path.read_text())
        self.assertEqual(result['version'], 'stage2-candidate-0.2.0')
        self.assertEqual(result['model_attempts'], 1)
        self.assertIsNone(result['max_model_calls'])
        self.assertIsNone(result['benchmark_success'])
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn(self.arguments['trial_token'], path.read_text())
        self.assertTrue(context.metadata['preserved'])
        self.assertIsNone(context.cost_usd)
        self.assertEqual(context.metadata['billing_source'], 'passive_gateway_physical_request_evidence')
        self.assertEqual(result['model_protocol_sha256'], SETTINGS.fingerprint())

    async def test_agent_or_disk_marker_cannot_replay_attempt(self):
        agent = self.agent([completion()])
        await agent.run('Synthetic', FakeEnvironment(), AgentContext())
        path = self.root / 'agent/custom-trajectory.json'
        original = path.read_bytes()
        with self.assertRaises(RuntimeError):
            await agent.run('Replay', FakeEnvironment(), AgentContext())
        second = self.agent([completion()])
        with self.assertRaises(FileExistsError):
            await second.run('Replay', FakeEnvironment(), AgentContext())
        self.assertEqual(path.read_bytes(), original)
        self.assertIsNone(second.runner)

    async def test_failure_is_not_an_outer_retry_or_a_verifier_fail(self):
        agent = self.agent([RuntimeError('Synthetic transport failure'), completion()])
        context = AgentContext()
        with self.assertRaises(RuntimeError):
            await agent.run('Synthetic', FakeEnvironment(), context)
        result = json.loads((self.root / 'agent/custom-trajectory.json').read_text())
        self.assertEqual(result['model_attempts'], 1)
        self.assertEqual(result['error_type'], 'RuntimeError')
        self.assertIsNone(result['benchmark_success'])
        self.assertIsNone(result['outcome'])

    async def test_cancelled_attempt_retains_evidence_and_propagates_cancellation(self):
        agent = self.agent([])
        with patch.object(CustomRunner, 'run', side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                await agent.run('Synthetic', FakeEnvironment(), AgentContext())
        result = json.loads((self.root / 'agent/custom-trajectory.json').read_text())
        self.assertEqual(result['error_type'], 'CancelledError')
        self.assertIsNone(result['benchmark_success'])
        self.assertTrue(agent.used)

    async def test_every_variant_keeps_the_same_execution_protocol(self):
        checks = [dict(criterion='Synthetic marker', observation='Fixture readback', satisfied=True)]
        for condition, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            agent = self.agent([completion(checks=checks)], condition=condition, parent=parent)
            # Each synthetic variant must have its own immutable attempt path.
            agent.logs_dir = self.root / (condition + '-' + str(parent))
            context = AgentContext()
            await agent.run('Synthetic', FakeEnvironment(), context)
            self.assertIsNone(agent.runner.model_limit.limit)
            self.assertEqual(context.metadata['model_protocol_sha256'], SETTINGS.fingerprint())
            self.assertEqual(context.metadata['custom_outcome']['outcome'], 'agent_reported_complete')
            self.assertIsNone(context.metadata['benchmark_success'])

    def test_parent_must_be_declared_before_a_c2_factory_can_exist(self):
        for condition, parent in (('C2', None), ('C2', 'C2'), ('C0', 'C1'), ('other', None)):
            with self.subTest(condition=condition, parent=parent), self.assertRaises(ValueError):
                agent_factory(self.root, condition, parent=parent)

    async def test_task_jobs_survive_until_after_verifier_and_vendor_tracing_is_off(self):
        agent = self.agent([])
        async def run(runner, *args, **kwargs):
            self.assertIs(get_tracing_context()['enabled'], False)
            self.assertTrue(runner.defer_job_cleanup)
            runner.jobs.close = AsyncMock()
            return {'outcome': 'fixture', 'benchmark_success': None}
        with patch.object(CustomRunner, 'run', new=run):
            await agent.run('Synthetic', FakeEnvironment(), AgentContext())
        agent.runner.jobs.close.assert_not_awaited()
        await agent.cleanup_after_verification()
        agent.runner.jobs.close.assert_awaited_once()

    async def test_factory_uses_shared_deadline_only_when_agent_starts(self):
        model = SequenceModel()
        model._sequence = [completion()]
        paths = SimpleNamespace(agent_dir=self.root / 'factory/agent', trial_dir=Path('custom-synthetic'))
        factory = agent_factory(self.root, 'C1')
        self.assertEqual(factory.harness, 'C1')
        self.assertEqual(factory.model_protocol_sha256, SETTINGS.fingerprint())
        with patch('corrected_custom_agent.gateway_model', return_value=model):
            agent = factory(paths=paths, host_api_base=self.arguments['api_base'],
                container_api_base='http://127.0.0.1:8765/v1', trial_token='synthetic',
                agent_timeout_seconds=900, completion_wait_seconds=960)
        runtime = self.root / '.runtime/stage2'
        runtime.mkdir(parents=True, mode=0o700)
        await agent.setup(FakeEnvironment())
        self.assertFalse((runtime / 'retry-lifecycle').exists())
        clock = Clock()
        with patch('retry_runtime.Clock', return_value=clock):
            await agent.run('Synthetic', FakeEnvironment(), AgentContext())
        self.assertEqual(deadline_for(runtime, 'custom-synthetic', SETTINGS, clock), 1000.)


class CorrectedClientGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_graph_client_bridge_and_shared_retry_with_no_paid_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = private_directory(root / '.runtime/stage2')
            durable_json(runtime / CREDIT_FILE, CREDIT_POLICY)
            durable_json(runtime / POLICY_FILE, POLICY)
            clock = Clock()
            activate(runtime, 'synthetic-custom', 900, SETTINGS, clock)
            client = Flaky(clock, [(429, ['1'])])
            client.response['usage']['cost'] = '0.00042'
            client.response.update(object='chat.completion', created=1, choices=[dict(
                index=0, finish_reason='tool_calls', message=dict(role='assistant', content=None,
                    tool_calls=[dict(id='synthetic-completion', type='function', function=dict(
                        name='complete_task', arguments=json.dumps({'summary': 'Synthetic fixture complete'})))]))])
            token = 'c' * 64  # Synthetic only; same length as a real trial token.
            with RetrySession(root, 'synthetic-custom', 'final', token, client,
                    settings=SETTINGS, clock=clock) as session:
                session.cancelled = Event(clock)
                rpc_errors = []
                def rpc(command, **kwargs):
                    envelope = json.loads(kwargs['input'])
                    try:
                        body = session.complete(envelope['token'], envelope['payload'])
                    except Exception as exc:
                        rpc_errors.append(repr(exc))
                        raise
                    return SimpleNamespace(returncode=0,
                        stdout=json.dumps({'status': 200, 'body': body}).encode())
                with HostModelBridge('b' * 64, completion_wait_seconds=960) as bridge:
                    bridge.gateway.run = rpc  # Docker RPC only; never a real provider.
                    agent = CorrectedCustomHarborAgent(root / 'agent', condition='C0',
                        api_base=bridge.base_url, trial_token=token,
                        trial_timeout_seconds=900, completion_wait_seconds=960)
                    context = AgentContext()
                    try:
                        await agent.run('Synthetic fixture only', FakeEnvironment(), context)
                    except Exception:
                        if rpc_errors:
                            self.fail('Synthetic gateway failure: ' + ', '.join(rpc_errors))
                        raise
                    self.assertEqual(context.metadata['model_attempts'], 1)
                    self.assertEqual(context.metadata['custom_outcome']['outcome'], 'agent_reported_complete')
                    await agent.cleanup_after_verification()
                self.assertTrue(bridge.gateway.revoked)
                self.assertFalse(bridge.thread.is_alive())
                self.assertEqual(len(client.calls), 2)
                self.assertEqual(client.calls[0], client.calls[1])
                for request in client.calls:
                    self.assertEqual(request['model'], MODEL)
                    self.assertEqual(request['max_tokens'], 384000)
                    self.assertEqual(request['temperature'], 1.)
                    self.assertEqual(request['top_p'], 1.)
                    self.assertEqual(request['reasoning'], {'effort': 'high'})
                    self.assertEqual(request['provider']['only'], ['deepinfra/fp8'])
                    self.assertFalse(request['provider']['allow_fallbacks'])
                    self.assertNotIn('max_price', request['provider'])
                accounting = summarise(runtime, session.trial_id)
                self.assertEqual(accounting['requests'], 2)
                self.assertEqual(accounting['unknown_cost_requests'], 1)
                self.assertIsNone(accounting['charged_usd'])
                self.assertFalse(list(runtime.glob('*.sqlite')))


if __name__ == '__main__':
    unittest.main()

"""Local C3 adapter checks. Runtime and task setup are synthetic, not qualified."""
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from harbor.models.agent.context import AgentContext

from custom_backend_tests import FakeEnvironment
from custom_control import Condition
from custom_deadline_guidance import MARKER
from custom_deadline_execution import DeadlineCondition, DeadlineCompletionControl, DeadlineJobs
from custom_python_runtime import PythonBundle
from custom_runner_tests import SequenceModel, completion
from custom_text_transport import TextGatewayChatOpenAI
from deadline_custom_agent import CANDIDATE_VERSION, DeadlineCustomHarborAgent, agent_factory
from portable_custom_policy import block_path
from retry_policy import SETTINGS
from retry_runtime import activate, deadline_for
from scored_gateway import private_directory
from test_retry_gateway import Clock


class DeadlineAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.clock = Clock()
        self.args = dict(root=self.root, trial_id='synthetic-c3', base_condition=Condition('C0'),
            python_bundle=PythonBundle(self.root / 'synthetic.tar.gz', 'a' * 64),
            api_base='http://127.0.0.1:9/v1', trial_token='synthetic-token',
            trial_timeout_seconds=900, completion_wait_seconds=960)

    def agent(self, sequence=None, **overrides):
        model = SequenceModel()
        model._sequence = sequence or [completion()]
        with patch('corrected_custom_agent.gateway_model', return_value=model):
            agent = DeadlineCustomHarborAgent(self.root / 'agent', **(self.args | overrides))
        return agent

    async def prepare(self, agent):
        environment = FakeEnvironment()
        with patch('portable_custom_agent.prepare_python',
                new=AsyncMock(return_value=(environment, {'sha256': 'a' * 64}))):
            await agent.setup(environment)
        return environment

    def test_factory_and_version_do_not_impersonate_old_parent(self):
        for condition, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            factory = agent_factory(self.root, condition, base_parent=parent)
            self.assertEqual(factory.harness, 'C3')
            self.assertEqual(factory.custom_parent, condition)
            self.assertEqual(factory.custom_base_parent, parent)
            self.assertEqual(factory.custom_version, CANDIDATE_VERSION)
            self.assertEqual(factory.model_protocol_sha256, SETTINGS.fingerprint())
        with self.assertRaises(ValueError):
            block_path(self.runtime, 'C3')

    def test_bad_parent_and_trial_identity_are_rejected(self):
        for base in ('C0', None, {'name': 'C0'}):
            with self.assertRaises(ValueError):
                self.agent(base_condition=base)
        for trial in ('../private', '', None, 'x' * 121):
            with self.assertRaises(ValueError):
                self.agent(trial_id=trial)
        for name, parent in (('C3', None), ('C2', None), ('C0', 'C1')):
            with self.assertRaises(ValueError):
                agent_factory(self.root, name, base_parent=parent)

    def test_exact_client_configuration_has_no_new_call_or_financial_ceiling(self):
        agent = DeadlineCustomHarborAgent(self.root / 'agent', **self.args)
        self.assertIsInstance(agent.model, TextGatewayChatOpenAI)
        self.assertEqual((agent.model.max_tokens, agent.model.temperature, agent.model.top_p), (384000,1.,1.))
        self.assertEqual(agent.model.extra_body, {'reasoning': {'effort': 'high'}})
        self.assertEqual(agent.model.max_retries, 0)
        self.assertIsNone(agent.execution_metadata()['max_model_calls'])
        for name, value in (('max_model_calls', 10), ('temperature', 0), ('budget_usd', 1)):
            with self.assertRaises(TypeError):
                DeadlineCustomHarborAgent(self.root / 'other', **self.args, **{name: value})

    async def test_read_clock_after_setup_without_resetting_it(self):
        agent = self.agent()
        environment = await self.prepare(agent)
        activate(self.runtime, self.args['trial_id'], 900, SETTINGS, self.clock)
        before = (self.runtime / 'retry-lifecycle/synthetic-c3.json').read_bytes()
        self.clock.now = 180
        with patch('deadline_custom_agent.Clock', return_value=self.clock):
            context = AgentContext(metadata={'preserved': True})
            await agent.run('Synthetic fixture', environment, context)
        self.assertEqual((self.runtime / 'retry-lifecycle/synthetic-c3.json').read_bytes(), before)
        self.assertEqual(agent.guidance.events[0]['remaining_seconds'], 820)
        self.assertEqual(context.metadata['custom_condition'], 'C3')
        self.assertEqual(context.metadata['custom_parent'], 'C0')
        self.assertTrue(context.metadata['preserved'])
        self.assertEqual(context.metadata['custom_version'], CANDIDATE_VERSION)
        self.assertIsNone(context.metadata['benchmark_success'])
        path = agent.logs_dir / 'custom-trajectory.json'
        document = json.loads(path.read_text())
        self.assertEqual(document['condition'], 'C3')
        self.assertEqual(document['deadline_guidance']['model_requests'], 1)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('synthetic-token', path.read_text())
        self.assertNotIn(MARKER, json.dumps(document['messages']))
        saved = path.read_bytes()
        with patch('deadline_custom_agent.Clock', return_value=self.clock), self.assertRaises(RuntimeError):
            await agent.run('Replay', environment, AgentContext())
        self.assertEqual(path.read_bytes(), saved)

    async def test_missing_clock_fails_before_first_model_call(self):
        agent = self.agent()
        environment = await self.prepare(agent)
        with patch('deadline_custom_agent.Clock', return_value=self.clock), self.assertRaises(FileNotFoundError):
            await agent.run('Synthetic', environment, AgentContext())
        self.assertEqual(agent.model._calls, [])
        self.assertIsNone(agent.runner)

    async def test_wrong_trial_protocol_or_boot_identity_is_not_accepted(self):
        for field, value in (('trial_id', 'different'), ('model_protocol_sha256', 'b' * 64),
                             ('boot_id', 'other-boot')):
            agent = self.agent()
            environment = await self.prepare(agent)
            path = self.runtime / 'retry-lifecycle/synthetic-c3.json'
            if not path.exists():
                activate(self.runtime, self.args['trial_id'], 900, SETTINGS, self.clock)
            record = json.loads(path.read_text())
            record.update(trial_id='synthetic-c3', model_protocol_sha256=SETTINGS.fingerprint(), boot_id=self.clock.boot_id)
            record[field] = value
            path.write_text(json.dumps(record))
            with patch('deadline_custom_agent.Clock', return_value=self.clock), self.assertRaises(ValueError):
                await agent.run('Synthetic', environment, AgentContext())
            self.assertEqual(agent.model._calls, [])

    async def test_every_parent_retains_its_prompt_and_completion_contract(self):
        checks = [dict(criterion='Fixture', observation='Read fixture', satisfied=True)]
        for name, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            condition = Condition(name, parent)
            trial = 'fixture-' + name + '-' + str(parent)
            agent = self.agent([completion(checks=checks)], base_condition=condition, trial_id=trial)
            agent.logs_dir = self.root / trial / 'agent'
            environment = await self.prepare(agent)
            activate(self.runtime, trial, 900, SETTINGS, self.clock)
            with patch('deadline_custom_agent.Clock', return_value=self.clock):
                context = AgentContext()
                await agent.run('Synthetic', environment, context)
            self.assertEqual(agent.runner.control.condition, DeadlineCondition(name, parent))
            self.assertIn(DeadlineCondition(name, parent).prompt, agent.model._calls[0][0].text)
            self.assertIsInstance(agent.runner.control, DeadlineCompletionControl)
            self.assertIsInstance(agent.runner.jobs, DeadlineJobs)
            contract = context.metadata['custom_execution_contract']
            for key in ('completion_repair_count_cap', 'background_active_count_cap',
                        'background_lifetime_count_cap', 'model_call_cap'):
                self.assertIsNone(contract[key])
            self.assertEqual(context.metadata['custom_parent'], name)
            self.assertEqual(context.metadata['custom_base_parent'], parent)
            self.assertIsNone(agent.runner.model_limit.limit)

    async def test_factory_clock_starts_after_setup_and_uses_exact_deadline(self):
        model = SequenceModel()
        model._sequence = [completion()]
        factory = agent_factory(self.root, 'C0')
        paths = SimpleNamespace(agent_dir=self.root / 'factory/agent', trial_dir=Path('factory-c3'))
        with patch('corrected_custom_agent.gateway_model', return_value=model):
            agent = factory(paths=paths, host_api_base=self.args['api_base'],
                container_api_base='http://unused/v1', trial_token='synthetic-token',
                agent_timeout_seconds=900, completion_wait_seconds=960)
        environment = await self.prepare(agent)
        self.assertFalse((self.runtime / 'retry-lifecycle').exists())
        with patch('retry_runtime.Clock', return_value=self.clock), patch('deadline_custom_agent.Clock', return_value=self.clock):
            await agent.run('Synthetic', environment, AgentContext())
        self.assertEqual(deadline_for(self.runtime, 'factory-c3', SETTINGS, self.clock), 1000)
        self.assertEqual(agent.guidance.deadline, 1000)

    async def test_cancellation_records_metadata_without_outer_retry(self):
        agent = self.agent()
        environment = await self.prepare(agent)
        activate(self.runtime, 'synthetic-c3', 900, SETTINGS, self.clock)
        with patch('deadline_custom_agent.Clock', return_value=self.clock), \
                patch('custom_runner.CustomRunner.run', side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError):
                await agent.run('Synthetic', environment, AgentContext())
        record = json.loads((agent.logs_dir / 'custom-trajectory.json').read_text())
        self.assertEqual(record['error_type'], 'CancelledError')
        self.assertIsNone(record['benchmark_success'])
        self.assertEqual(agent.model._calls, [])

    async def test_jobs_are_preserved_for_verifier_then_cleaned(self):
        agent = self.agent()
        environment = await self.prepare(agent)
        activate(self.runtime, 'synthetic-c3', 900, SETTINGS, self.clock)
        async def run(runner, *args, **kwargs):
            self.assertTrue(runner.defer_job_cleanup)
            runner.jobs.close = AsyncMock()
            return {'outcome': 'fixture', 'benchmark_success': None}
        with patch('deadline_custom_agent.Clock', return_value=self.clock), \
                patch('custom_runner.CustomRunner.run', new=run):
            await agent.run('Synthetic', environment, AgentContext())
        agent.runner.jobs.close.assert_not_awaited()
        await agent.cleanup_after_verification()
        agent.runner.jobs.close.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()

"""Final adapter tests using fake models, clocks and container environments."""
import asyncio
import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from harbor.models.agent.context import AgentContext
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from .fixtures import FakeEnvironment
from uts_harness.control import Condition, CompletionControl
from uts_harness.deadlines import (TaskDeadline, DeadlineCondition,
    DeadlineCompletionControl, DeadlineJobs, LEGACY_REPAIR_NOTICE)
from uts_harness.deadline_guidance import MARKER
from uts_harness.python_runtime import PythonBundle
from .fixtures import SequenceModel, completion
from uts_harness.text_transport import TextGatewayChatOpenAI
from uts_harness.agent import NoCutoffCustomHarborAgent, NoCutoffCustomRunner, agent_factory
from uts_harness.execution_contract import (CANDIDATE_VERSION, EXECUTION_POLICY_VERSION,
    execution_contract, revision_name)
from uts_harness.settings import SETTINGS
from uts_harness.lifecycle import activate, deadline_for
from uts_harness.private_io import private_directory
from .fixtures import Clock


def incomplete(index):
    return AIMessage(content='', tool_calls=[dict(name='complete_task',
        id=f'repair-{index}', args={'summary': ''})])


class NoCutoffAgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        self.clock = Clock()
        self.args = dict(root=self.root, trial_id='synthetic-nc', base_condition=Condition('C0'),
            python_bundle=PythonBundle(self.root / 'synthetic.tar.gz', 'a' * 64),
            api_base='http://127.0.0.1:9/v1', trial_token='synthetic-token',
            trial_timeout_seconds=900, completion_wait_seconds=960)

    def agent(self, sequence=None, **overrides):
        model = SequenceModel()
        model._sequence = [completion()] if sequence is None else sequence
        with patch('uts_harness.harbor_agent.gateway_model', return_value=model):
            return NoCutoffCustomHarborAgent(self.root / 'agent', **(self.args | overrides))

    async def prepare(self, agent):
        environment = FakeEnvironment()
        with patch('uts_harness.portable_agent.prepare_python',
                new=AsyncMock(return_value=(environment, {'sha256': 'a' * 64}))):
            await agent.setup(environment)
        return environment

    async def run_fixture(self, agent, *, environment=None):
        environment = environment or await self.prepare(agent)
        path = self.runtime / 'retry-lifecycle' / (agent.trial_id + '.json')
        if not path.exists():
            activate(self.runtime, agent.trial_id, agent.timeout, SETTINGS, self.clock)
        context = AgentContext(metadata={'preserved': True})
        with patch('uts_harness.agent.Clock', return_value=self.clock):
            await agent.run('Synthetic task only', environment, context)
        return environment, context

    def test_factory_labels_revision_instead_of_reusing_measured_identity(self):
        for name, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            factory = agent_factory(self.root, name, base_parent=parent)
            self.assertEqual(factory.harness, name + '-NC')
            self.assertEqual(factory.custom_parent, name)
            self.assertEqual(factory.custom_base_parent, parent)
            self.assertEqual(factory.custom_version, CANDIDATE_VERSION)
            self.assertEqual(factory.custom_design_lever, EXECUTION_POLICY_VERSION)
            self.assertEqual(factory.model_protocol_sha256, SETTINGS.fingerprint())

    def test_invalid_parent_or_trial_cannot_impersonate_a_registered_variant(self):
        for name, parent in (('C3', None), ('C0-NC', None), ('C2', None), ('C0', 'C1')):
            with self.assertRaises(ValueError): agent_factory(self.root, name, base_parent=parent)
        for value in ('C0', None, {'name': 'C0'}):
            with self.assertRaises(ValueError): self.agent(base_condition=value)
        for value in ('../private', '', None, 'x' * 121):
            with self.assertRaises(ValueError): self.agent(trial_id=value)
        with self.assertRaises(ValueError): revision_name('C3')

    def test_contract_removes_only_identified_cutoffs_not_actual_boundaries(self):
        contract = execution_contract()
        self.assertFalse(contract['remaining_time_guidance'])
        for key in ('model_call_cap', 'completion_repair_count_cap',
                    'background_active_count_cap', 'background_lifetime_count_cap'):
            self.assertIsNone(contract[key])
        self.assertEqual(contract['default_command_timeout'], 'remaining-official-task-time')
        self.assertEqual(contract['overall_deadline'], 'official-authoritative-unchanged')
        self.assertEqual(contract['container_isolation'], 'unchanged')
        self.assertEqual(contract['provider_auth_credit_identity'], 'enforced')
        self.assertEqual(contract['output_and_context_windows'], 'finite-unchanged')
        self.assertTrue(contract['no_replay'])

    def test_exact_model_configuration_and_no_new_count_or_spending_override(self):
        agent = NoCutoffCustomHarborAgent(self.root / 'agent', **self.args)
        self.assertIsInstance(agent.model, TextGatewayChatOpenAI)
        self.assertEqual((agent.model.max_tokens, agent.model.temperature, agent.model.top_p), (384000, 1., 1.))
        self.assertEqual(agent.model.extra_body, {'reasoning': {'effort': 'high'}})
        self.assertEqual(agent.model.max_retries, 0)
        self.assertIsNone(agent.execution_metadata()['max_model_calls'])
        for name in ('max_model_calls', 'temperature', 'budget_usd'):
            with self.assertRaises(TypeError):
                NoCutoffCustomHarborAgent(self.root / 'other', **self.args, **{name: 1})

    async def test_parent_prompt_is_preserved_except_the_explicit_cutoff_contract(self):
        checks = [dict(criterion='Fixture', observation='Read fixture', satisfied=True)]
        for name, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            trial = 'fixture-' + name + '-' + str(parent)
            agent = self.agent([completion(checks=checks)], base_condition=Condition(name, parent), trial_id=trial)
            agent.logs_dir = self.root / trial / 'agent'
            _, context = await self.run_fixture(agent)
            prompt = agent.model._calls[0][0].text
            self.assertIn(DeadlineCondition(name, parent).prompt, prompt)
            self.assertNotIn(MARKER, prompt)
            self.assertIsInstance(agent.runner.control, DeadlineCompletionControl)
            self.assertIsInstance(agent.runner.jobs, DeadlineJobs)
            self.assertEqual(context.metadata['custom_condition'], name + '-NC')
            self.assertEqual(context.metadata['custom_parent'], name)
            self.assertEqual(context.metadata['custom_base_parent'], parent)
            self.assertFalse(context.metadata['custom_execution_contract']['remaining_time_guidance'])

    async def test_more_than_one_hundred_calls_and_repairs_without_time_advice(self):
        agent = self.agent([incomplete(i) for i in range(104)] + [completion()])
        await self.run_fixture(agent)
        self.assertEqual(agent.runner.control.repairs_used, 104)
        self.assertEqual(agent.runner.model_limit.attempts, 105)
        self.assertIsNone(agent.runner.model_limit.limit)
        self.assertEqual(agent.runner.control.outcome, 'agent_reported_complete')
        for messages in agent.model._calls:
            self.assertNotIn(MARKER, messages[0].text)

    async def test_c2_still_requires_real_reported_checks_after_many_repairs(self):
        checks = [dict(criterion='Fixture', observation='Read fixture', satisfied=True)]
        calls = [AIMessage(content='', tool_calls=[dict(name='complete_task', id=f'check-{i}',
            args={'summary': 'Missing checks'})]) for i in range(8)] + [completion(checks=checks)]
        agent = self.agent(calls, base_condition=Condition('C2', 'C0'))
        await self.run_fixture(agent)
        self.assertEqual(agent.runner.control.repairs_used, 8)
        self.assertEqual(agent.runner.control.outcome, 'agent_reported_complete')

    async def test_existing_clock_is_read_without_reset_or_dynamic_prompt(self):
        agent = self.agent()
        environment = await self.prepare(agent)
        activate(self.runtime, agent.trial_id, 900, SETTINGS, self.clock)
        path = self.runtime / 'retry-lifecycle/synthetic-nc.json'
        before = path.read_bytes()
        self.clock.now += 80
        _, context = await self.run_fixture(agent, environment=environment)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(agent.task_deadline.remaining(), 820)
        self.assertTrue(context.metadata['preserved'])
        self.assertIsNone(context.metadata['benchmark_success'])
        self.assertNotIn('deadline_guidance_model_requests', context.metadata)

    async def test_factory_starts_same_authoritative_clock_after_setup(self):
        factory = agent_factory(self.root, 'C0')
        model = SequenceModel(); model._sequence = [completion()]
        paths = SimpleNamespace(agent_dir=self.root / 'factory/agent', trial_dir=Path('factory-nc'))
        with patch('uts_harness.harbor_agent.gateway_model', return_value=model):
            agent = factory(paths=paths, host_api_base=self.args['api_base'], container_api_base='http://unused/v1',
                trial_token='synthetic-token', agent_timeout_seconds=900, completion_wait_seconds=960)
        environment = await self.prepare(agent)
        self.assertFalse((self.runtime / 'retry-lifecycle').exists())
        with patch('uts_harness.lifecycle.Clock', return_value=self.clock), patch('uts_harness.agent.Clock', return_value=self.clock):
            await agent.run('Synthetic', environment, AgentContext())
        self.assertEqual(deadline_for(self.runtime, 'factory-nc', SETTINGS, self.clock), 1000)
        self.assertEqual(agent.task_deadline.deadline, 1000)

    async def test_missing_clock_fails_before_model_dispatch(self):
        agent = self.agent(); environment = await self.prepare(agent)
        with patch('uts_harness.agent.Clock', return_value=self.clock), self.assertRaises(FileNotFoundError):
            await agent.run('Synthetic', environment, AgentContext())
        self.assertEqual(agent.model._calls, [])
        self.assertIsNone(agent.runner)

    async def test_mismatched_clock_identity_is_rejected(self):
        for field, value in (('trial_id', 'other'), ('model_protocol_sha256', 'b' * 64), ('boot_id', 'other-boot')):
            agent = self.agent(); environment = await self.prepare(agent)
            path = self.runtime / 'retry-lifecycle/synthetic-nc.json'
            if not path.exists(): activate(self.runtime, agent.trial_id, 900, SETTINGS, self.clock)
            record = json.loads(path.read_text())
            record.update(trial_id=agent.trial_id, model_protocol_sha256=SETTINGS.fingerprint(), boot_id=self.clock.boot_id)
            record[field] = value
            path.write_text(json.dumps(record))
            with patch('uts_harness.agent.Clock', return_value=self.clock), self.assertRaises(ValueError):
                await agent.run('Synthetic', environment, AgentContext())
            self.assertEqual(agent.model._calls, [])

    async def test_real_graph_execute_default_uses_remaining_time(self):
        call = AIMessage(content='', tool_calls=[dict(name='execute', id='default', args={'command': 'printf fixture'})])
        agent = self.agent([call, completion()])
        environment = await self.prepare(agent)
        activate(self.runtime, agent.trial_id, 900, SETTINGS, self.clock)
        self.clock.now += 40
        await self.run_fixture(agent, environment=environment)
        self.assertEqual(environment.calls[0][1], 870)  # 860 task seconds + transport grace

    async def test_real_graph_accepts_explicit_command_over_one_hour(self):
        call = AIMessage(content='', tool_calls=[dict(name='execute', id='long', args={'command': 'printf fixture', 'timeout': 4000})])
        agent = self.agent([call, completion()], trial_timeout_seconds=7200, completion_wait_seconds=7260)
        environment, _ = await self.run_fixture(agent)
        self.assertEqual(environment.calls[0][1], 4010)

    async def test_agent_can_choose_shorter_timeout(self):
        call = AIMessage(content='', tool_calls=[dict(name='execute', id='short', args={'command': 'printf fixture', 'timeout': 2})])
        agent = self.agent([call, completion()])
        environment, _ = await self.run_fixture(agent)
        self.assertEqual(environment.calls[0][1], 12)

    async def test_start_tool_has_no_sixty_second_default_or_handle_quota(self):
        call = AIMessage(content='', tool_calls=[dict(name='start_command', id='background', args={'command': 'printf fixture'})])
        agent = self.agent([call, completion()])
        environment, _ = await self.run_fixture(agent)
        self.assertEqual(environment.calls[0][1], 910)
        release = asyncio.Event()
        async def wait(command, timeout):
            await release.wait()
            return SimpleNamespace(output='fixture', exit_code=0, truncated=False)
        agent.runner.jobs.backend.aexecute = wait
        try:
            for _ in range(80): await agent.runner.jobs.start('printf fixture')
            await asyncio.sleep(0)
            self.assertEqual(len(agent.runner.jobs.jobs), 81)
            self.assertEqual(sum(not task.done() for task, _ in agent.runner.jobs.jobs.values()), 80)
        finally:
            release.set()
            await asyncio.gather(*(task for task, _ in agent.runner.jobs.jobs.values()))

    async def test_official_deadline_still_ends_unlimited_repairs(self):
        class SlowIncompleteModel(SequenceModel):
            async def _agenerate(self, messages, **kwargs):
                self._calls.append(messages)
                await asyncio.sleep(.005)
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='Still working'))])
        deadline = TaskDeadline(deadline_monotonic=time.monotonic()+1,
            official_timeout_seconds=1, monotonic=time.monotonic)
        from uts_harness.deadlines import DeadlineHarborSandbox
        backend = DeadlineHarborSandbox(FakeEnvironment(), identifier='synthetic', deadline=deadline)
        runner = NoCutoffCustomRunner(SlowIncompleteModel(), backend, Condition('C0'), deadline=deadline,
            defer_job_cleanup=False)
        with self.assertRaises(TimeoutError): await runner.run('Synthetic', timeout_seconds=1)
        self.assertGreater(runner.control.repairs_used, 2)
        self.assertIsNone(runner.control.outcome)
        with self.assertRaises(RuntimeError): await runner.run('No replay', timeout_seconds=1)

    async def test_runner_cannot_extend_or_restart_official_allowance(self):
        agent = self.agent(); await self.run_fixture(agent)
        for timeout in (901, True, None):
            with self.assertRaises(ValueError): await agent.runner.run('Synthetic', timeout_seconds=timeout)
        self.clock.now += 900
        with self.assertRaises(TimeoutError): agent.task_deadline.command_timeout()

    async def test_completed_attempt_cannot_overwrite_evidence(self):
        agent = self.agent(); environment, _ = await self.run_fixture(agent)
        path = agent.logs_dir / 'custom-trajectory.json'
        before = path.read_bytes()
        with patch('uts_harness.agent.Clock', return_value=self.clock), self.assertRaises(RuntimeError):
            await agent.run('No replay', environment, AgentContext())
        self.assertEqual(path.read_bytes(), before)

    async def test_cancellation_records_truthful_revision_metadata_and_propagates(self):
        agent = self.agent()
        with patch('uts_harness.controller.CustomRunner.run', side_effect=asyncio.CancelledError):
            with self.assertRaises(asyncio.CancelledError): await self.run_fixture(agent)
        record = json.loads((agent.logs_dir / 'custom-trajectory.json').read_text())
        self.assertEqual(record['error_type'], 'CancelledError')
        self.assertEqual(record['condition'], 'C0-NC')
        self.assertEqual(record['parent'], 'C0')
        self.assertIsNone(record['benchmark_success'])
        self.assertEqual(agent.model._calls, [])

    async def test_jobs_live_through_verification_then_cleanup(self):
        agent = self.agent()
        async def run(runner, *args, **kwargs):
            self.assertTrue(runner.defer_job_cleanup)
            runner.jobs.close = AsyncMock()
            return {'outcome': 'fixture', 'benchmark_success': None}
        with patch('uts_harness.controller.CustomRunner.run', new=run): await self.run_fixture(agent)
        agent.runner.jobs.close.assert_not_awaited()
        await agent.cleanup_after_verification()
        agent.runner.jobs.close.assert_awaited_once()

    async def test_private_trajectory_does_not_serialize_credentials_or_new_time_advice(self):
        agent = self.agent(); await self.run_fixture(agent)
        path = agent.logs_dir / 'custom-trajectory.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('synthetic-token', path.read_text())
        self.assertNotIn(MARKER, path.read_text())
        self.assertEqual(json.loads(path.read_text())['version'], CANDIDATE_VERSION)

    async def test_only_the_prepared_container_can_be_used(self):
        agent = self.agent()
        with self.assertRaises(RuntimeError): agent.backend(FakeEnvironment())
        environment = await self.prepare(agent)
        with self.assertRaises(RuntimeError): agent.backend(FakeEnvironment())
        with self.assertRaises(RuntimeError): await agent.setup(environment)
        with self.assertRaises(RuntimeError): agent.make_runner(None)

    def test_original_parent_controls_stay_unchanged(self):
        original = CompletionControl(Condition('C0'))
        for _ in range(3): original.complete('')
        self.assertEqual(original.outcome, 'repair_exhausted')
        self.assertIn(LEGACY_REPAIR_NOTICE, Condition('C0').prompt)


if __name__ == '__main__':
    unittest.main()

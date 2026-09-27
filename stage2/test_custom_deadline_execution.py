"""Deadline-governed C3: synthetic clocks/models plus local process fixtures.

No native benchmark tasks, provider credentials, network requests or paid calls.
"""
import asyncio
import json
import shlex
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from deepagents.backends.protocol import ExecuteResponse
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from custom_backend_tests import FakeEnvironment
from custom_control import Condition, CompletionControl, PLAN_PROMPT, CHECK_PROMPT
from custom_deadline_execution import (TaskDeadline, DeadlineCondition, DeadlineCompletionControl,
    DeadlineHarborSandbox, DeadlineJobs, DeadlineCustomRunner, LEGACY_REPAIR_NOTICE,
    DEADLINE_REPAIR_NOTICE, execution_contract)
from custom_deadline_guidance import DeadlineGuidance
from custom_portable_backend import ContainerCaptureError
from custom_runner import CustomRunner
from custom_runner_tests import SequenceModel, completion
from test_retry_gateway import Clock


def task_deadline(clock, duration=900):
    return TaskDeadline(deadline_monotonic=clock.monotonic() + duration,
        official_timeout_seconds=duration, monotonic=clock.monotonic)


def step_completion(step, *, summary='', checks=None):
    # Each provider response must be a new message/tool-call identity. Reusing
    # one AIMessage object tests LangGraph deduplication, not repair handling.
    return AIMessage(content='', tool_calls=[dict(name='complete_task',
        id=f'completion-{step}', args=dict(summary=summary, checks=checks))])


class DeadlinePolicyTests(unittest.TestCase):
    def test_repair_count_is_no_longer_a_stop_condition(self):
        control = DeadlineCompletionControl(DeadlineCondition('C2', 'C0'))
        for attempt in range(150):
            result = control.complete('Needs actual checks')
            self.assertEqual(result['repair_number'], attempt + 1)
            self.assertFalse(result['terminal'])
        self.assertFalse(control.terminal)
        self.assertIsNone(control.outcome)
        checks = [dict(criterion='Output', observation='Read back fixture', satisfied=True)]
        self.assertEqual(control.complete('Done', checks)['status'], 'agent_reported_complete')

    def test_abandon_and_valid_completion_are_still_terminal(self):
        for action in ('complete', 'abandon'):
            control = DeadlineCompletionControl(DeadlineCondition('C0'))
            getattr(control, action)('Synthetic')
            self.assertTrue(control.terminal)
            before = list(control.events)
            self.assertTrue(control.incomplete('No further call')['terminal'])
            self.assertEqual(control.events, before)

    def test_old_controls_and_prompts_stay_unchanged(self):
        old = CompletionControl(Condition('C0'))
        for _ in range(3): old.complete('')
        self.assertEqual(old.outcome, 'repair_exhausted')
        self.assertIn(LEGACY_REPAIR_NOTICE, Condition('C0').prompt)
        for name, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            original = Condition(name, parent).prompt
            revised = DeadlineCondition(name, parent).prompt
            self.assertEqual(revised, original.replace(LEGACY_REPAIR_NOTICE, DEADLINE_REPAIR_NOTICE)
                .replace('use the remaining repair allowance', 'use the remaining official task time'))
            self.assertNotIn('At most two', revised)
            self.assertNotIn('remaining repair allowance', revised)
            if name == 'C1' or parent == 'C1': self.assertIn(PLAN_PROMPT, revised)
            if name == 'C2': self.assertIn(CHECK_PROMPT.split('If checks')[0], revised)

    def test_changed_parent_contract_must_be_reviewed(self):
        with patch('custom_control.BASE_PROMPT', 'Different parent'):
            with self.assertRaises(ValueError):
                _ = DeadlineCondition('C0').prompt

    def test_no_quota_claim_does_not_remove_isolation_or_provider_constraints(self):
        contract = execution_contract()
        self.assertTrue(all(contract[k] is None for k in ('completion_repair_count_cap',
            'background_active_count_cap', 'background_lifetime_count_cap', 'model_call_cap')))
        self.assertEqual(contract['container_isolation'], 'unchanged')
        self.assertEqual(contract['provider_auth_credit_identity'], 'enforced')
        self.assertTrue(contract['no_replay'])
        self.assertEqual(contract['output_and_context_windows'], 'finite-unchanged')

    def test_clock_uses_remaining_time_not_a_new_full_allowance(self):
        clock = Clock()
        deadline = task_deadline(clock, 7200)
        self.assertEqual(deadline.command_timeout(), 7200)
        clock.now += 5100
        self.assertEqual(deadline.command_timeout(), 2100)
        self.assertEqual(deadline.command_timeout(9999), 2100)
        self.assertEqual(deadline.command_timeout(17.5), 17.5)
        clock.now += 2100
        with self.assertRaises(TimeoutError): deadline.command_timeout()

    def test_invalid_and_backwards_clock_does_not_extend_trial(self):
        for value in (True, None, '100', float('nan'), float('inf'), -1):
            with self.assertRaises(ValueError):
                TaskDeadline(deadline_monotonic=value, official_timeout_seconds=900, monotonic=lambda: 100)
        clock = Clock(); deadline = task_deadline(clock)
        deadline.remaining(); clock.now -= 1
        with self.assertRaises(ValueError): deadline.remaining()
        future = TaskDeadline(deadline_monotonic=1000, official_timeout_seconds=1, monotonic=lambda: 100)
        with self.assertRaises(ValueError): future.remaining()
        for value in (True, False, -1, 0, float('nan'), float('inf'), '30'):
            with self.assertRaises(ValueError): task_deadline(Clock()).command_timeout(value)


class DeadlineBackendTests(unittest.IsolatedAsyncioTestCase):
    async def test_ordinary_command_gets_full_remaining_allowance(self):
        clock = Clock(); deadline = task_deadline(clock, 7200)
        environment = FakeEnvironment()
        backend = DeadlineHarborSandbox(environment, identifier='synthetic', deadline=deadline)
        clock.now += 10
        result = await backend.aexecute('printf fixture')
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(environment.calls[-1][1], 7190 + 10)
        self.assertIn('7190.0', environment.calls[-1][0])
        self.assertIsNone(backend.command_timeout)

    async def test_explicit_agent_timeout_is_optional_and_bounded_only_by_task(self):
        clock = Clock(); deadline = task_deadline(clock, 7200)
        environment = FakeEnvironment()
        backend = DeadlineHarborSandbox(environment, identifier='synthetic', deadline=deadline)
        for requested, expected in ((3601,3601), (8000,7200), (1.5,1.5)):
            await backend.aexecute('printf fixture', timeout=requested)
            self.assertEqual(environment.calls[-1][1], expected + 10)

    async def test_expired_deadline_cannot_start_another_command(self):
        clock = Clock(); deadline = task_deadline(clock, 20)
        environment = FakeEnvironment()
        backend = DeadlineHarborSandbox(environment, identifier='synthetic', deadline=deadline)
        clock.now += 20
        with self.assertRaises(TimeoutError): await backend.aexecute('printf too-late')
        self.assertEqual(environment.calls, [])

    async def test_tool_errors_and_real_transport_failures_stay_distinct(self):
        clock = Clock(); deadline = task_deadline(clock)
        environment = SimpleNamespace(exec=AsyncMock(return_value=SimpleNamespace(return_code=0,
            stdout=json.dumps(dict(output='fixture', exit_code=7, truncated=False)))))
        backend = DeadlineHarborSandbox(environment, identifier='synthetic', deadline=deadline)
        self.assertEqual((await backend.aexecute('fixture')).exit_code, 7)
        environment.exec.return_value = SimpleNamespace(return_code=137, stdout='private error')
        with self.assertRaises(ContainerCaptureError) as caught:
            await backend.aexecute('fixture')
        self.assertNotIn('private error', str(caught.exception))

    async def test_sync_bridge_keeps_same_deadline(self):
        clock = Clock(); deadline = task_deadline(clock, 123)
        environment = FakeEnvironment()
        backend = DeadlineHarborSandbox(environment, identifier='synthetic', deadline=deadline)
        await asyncio.to_thread(backend.execute, 'printf fixture')
        self.assertEqual(environment.calls[0][1], 133)


class DeadlineJobTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock(); self.deadline = task_deadline(self.clock, 7200)
        self.started = []
        self.release = asyncio.Event()
        async def execute(command, timeout):
            self.started.append((command, timeout))
            await self.release.wait()
            return ExecuteResponse(output='fixture', exit_code=0, truncated=False)
        self.backend = SimpleNamespace(aexecute=execute,
            environment=SimpleNamespace(exec=AsyncMock(return_value=SimpleNamespace(return_code=0,stdout='23456'))))
        self.jobs = DeadlineJobs(self.backend, self.deadline)

    async def asyncTearDown(self):
        for task, _ in self.jobs.jobs.values(): task.cancel()
        await asyncio.gather(*(t for t, _ in self.jobs.jobs.values()), return_exceptions=True)

    async def test_more_than_four_active_and_sixty_four_total_handles(self):
        handles = [(await self.jobs.start('printf fixture'))['job_id'] for _ in range(80)]
        await asyncio.sleep(0)
        self.assertEqual(len(set(handles)), 80)
        self.assertEqual(len(self.started), 80)
        self.assertEqual(sum(not t.done() for t, _ in self.jobs.jobs.values()), 80)
        self.assertTrue(all(timeout == 7200 for _, timeout in self.started))
        self.release.set()
        await asyncio.gather(*(t for t, _ in self.jobs.jobs.values()))
        await self.jobs.close()
        for identifier in handles:
            self.assertEqual(self.jobs.poll(identifier)['exit_code'], 0)
        await self.jobs.start('printf eighty-one')
        self.assertEqual(len(self.jobs.jobs), 81)

    async def test_no_one_hour_ceiling_and_no_new_clock_on_next_handle(self):
        await self.jobs.start('printf explicit', 4000)
        self.clock.now += 5000
        await self.jobs.start('printf implicit')
        await asyncio.sleep(0)
        self.assertEqual([t for _,t in self.started], [4000,2200])

    async def test_invalid_arguments_do_not_consume_a_handle(self):
        for command in ('', None, ' ', '\x00'):
            with self.assertRaises(ValueError): await self.jobs.start(command)
        for timeout in (True,False,0,-1,float('nan'),float('inf'),'100'):
            with self.assertRaises(ValueError): await self.jobs.start('printf fixture', timeout)
        self.assertEqual(self.jobs.jobs, {})

    async def test_expired_trial_and_unknown_handles_still_fail_closed(self):
        with self.assertRaises(KeyError): self.jobs.poll('unknown')
        with self.assertRaises(KeyError): await self.jobs.interrupt('unknown')
        self.clock.now += 7200
        with self.assertRaises(TimeoutError): await self.jobs.start('printf too-late')
        self.assertEqual(self.jobs.jobs, {})
        self.backend.environment.exec.assert_not_awaited()

    async def test_interrupt_stays_inside_container_and_preserves_observation(self):
        identifier = (await self.jobs.start('printf fixture'))['job_id']
        await asyncio.sleep(0)
        async def rpc(command, timeout_sec):
            if command.startswith('kill -TERM'): self.release.set()
            return SimpleNamespace(return_code=0, stdout='23456')
        self.backend.environment.exec.side_effect = rpc
        result = await self.jobs.interrupt(identifier)
        self.assertEqual(result['exit_code'], 0)
        commands = [c.args[0] for c in self.backend.environment.exec.await_args_list]
        self.assertTrue(any(c == 'kill -TERM -- -23456' for c in commands))
        self.assertTrue(all(c.startswith(('cat ', 'kill ')) for c in commands))


class DeadlineRunnerTests(unittest.IsolatedAsyncioTestCase):
    def make(self, sequence, *, duration=900, condition=Condition('C0'), clock=None):
        clock = clock or Clock(); deadline = task_deadline(clock, duration)
        guidance = DeadlineGuidance(deadline_monotonic=deadline.deadline,
            official_timeout_seconds=duration, monotonic=clock.monotonic)
        model = SequenceModel(); model._sequence = sequence
        environment = FakeEnvironment()
        backend = DeadlineHarborSandbox(environment, identifier='synthetic', deadline=deadline)
        runner = DeadlineCustomRunner(model, backend, condition,
            deadline=deadline, guidance=guidance, defer_job_cleanup=False)
        return model, runner, environment, clock

    async def test_real_graph_retries_more_than_two_incomplete_completions(self):
        checks = [dict(criterion='Output', observation='Read fixture', satisfied=True)]
        sequence = [step_completion(i) for i in range(8)] + [
            step_completion(8, summary='Done', checks=checks)]
        model, runner, _, _ = self.make(sequence, condition=Condition('C2', 'C0'))
        result = await runner.run('Synthetic task', timeout_seconds=900)
        self.assertEqual(result['repair_cycles'], 8)
        self.assertEqual(result['outcome'], 'agent_reported_complete')
        self.assertEqual(len(model._calls), 9)
        self.assertIsNone(result['benchmark_success'])
        self.assertIsNone(runner.model_limit.limit)

    async def test_real_execute_tool_accepts_more_than_one_hour_and_uses_backend(self):
        calls = [AIMessage(content='', tool_calls=[dict(name='execute', id='long',
            args={'command':'printf fixture','timeout':4000})]), completion()]
        model, runner, environment, _ = self.make(calls, duration=7200)
        await runner.run('Synthetic task', timeout_seconds=7200)
        self.assertEqual(len(environment.calls), 1)
        self.assertEqual(environment.calls[0][1], 4010)
        self.assertEqual(len(model._calls), 2)

    async def test_default_execute_tool_uses_all_remaining_time(self):
        calls = [AIMessage(content='', tool_calls=[dict(name='execute', id='default',
            args={'command':'printf fixture'})]), completion()]
        _, runner, environment, clock = self.make(calls)
        clock.now += 40
        await runner.run('Synthetic task', timeout_seconds=900)
        self.assertEqual(environment.calls[0][1], 870)

    async def test_real_graph_start_tool_has_no_sixty_second_default(self):
        calls = [AIMessage(content='', tool_calls=[dict(name='start_command', id='background',
            args={'command':'printf fixture'})]), completion()]
        model, runner, environment, _ = self.make(calls)
        await runner.run('Synthetic task', timeout_seconds=900)
        self.assertEqual(len(environment.calls), 1)
        self.assertEqual(environment.calls[0][1], 910)
        self.assertEqual(len(model._calls), 2)
        self.assertTrue(runner.jobs.jobs)

    async def test_forever_incomplete_model_ends_at_deadline_not_repair_count(self):
        class IncompleteModel(SequenceModel):
            async def _agenerate(self, messages, **kwargs):
                self._calls.append(messages)
                await asyncio.sleep(.005)
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='Still working'))])
        clock = SimpleNamespace(monotonic=time.monotonic)
        _, runner, _, _ = self.make([], duration=1, clock=clock)
        model = IncompleteModel()
        backend = runner.jobs.backend
        runner = DeadlineCustomRunner(model, backend, Condition('C0'), deadline=runner.deadline,
            guidance=DeadlineGuidance(deadline_monotonic=runner.deadline.deadline,
                official_timeout_seconds=1, monotonic=time.monotonic), defer_job_cleanup=False)
        with self.assertRaises(TimeoutError):
            await runner.run('Synthetic only', timeout_seconds=1)
        self.assertGreater(runner.control.repairs_used, 2)
        self.assertFalse(runner.control.terminal)
        self.assertIsNone(runner.control.outcome)
        self.assertTrue(runner.used)
        with self.assertRaises(RuntimeError):
            await runner.run('No replay', timeout_seconds=1)

    async def test_graph_cancellation_still_propagates_and_cleans_jobs(self):
        _, runner, _, _ = self.make([])
        async def cancelled(*args, **kwargs):
            raise asyncio.CancelledError
            yield  # pragma: no cover - async-generator protocol
        runner.graph.astream = cancelled
        runner.jobs.close = AsyncMock()
        with self.assertRaises(asyncio.CancelledError):
            await runner.run('Synthetic', timeout_seconds=900)
        runner.jobs.close.assert_awaited_once()

    async def test_cannot_override_official_total_or_reset_deadline(self):
        _, runner, _, clock = self.make([completion()])
        for duration in (60, 901, None, True, float('inf')):
            with self.assertRaises(ValueError):
                await runner.run('Synthetic', timeout_seconds=duration)
        clock.now += 900
        with self.assertRaises(TimeoutError):
            await runner.run('Too late', timeout_seconds=900)

    async def test_legacy_runner_remains_at_two_repairs(self):
        model = SequenceModel(); model._sequence = [step_completion(i) for i in range(4)]
        legacy = CustomRunner(model, legacy_backend(), Condition('C0'), max_model_calls=None)
        result = await legacy.run('Synthetic', timeout_seconds=10)
        self.assertEqual(result['outcome'], 'repair_exhausted')
        self.assertEqual(len(model._calls), 3)


def legacy_backend():
    from custom_backend import HarborSandbox
    return HarborSandbox(FakeEnvironment(), identifier='synthetic-legacy')


class RealCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_command_can_pass_sixty_seconds_without_being_killed(self):
        # Only this predetermined harmless fixture runs locally. Production
        # backends execute through Harbor; no agent controls the local host.
        with tempfile.TemporaryDirectory() as directory:
            async def local_fixture(command, timeout_sec):
                argv = shlex.split(command)
                self.assertEqual(argv[:2], ['python3','-c'])
                self.assertEqual(len(argv), 3)
                process = await asyncio.create_subprocess_exec(sys.executable,'-c',argv[2],
                    cwd=directory, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout_sec)
                finally:
                    if process.returncode is None:
                        process.kill(); await process.wait()
                return SimpleNamespace(return_code=process.returncode,stdout=stdout.decode(),stderr=stderr.decode())
            deadline = TaskDeadline(deadline_monotonic=time.monotonic()+75,
                official_timeout_seconds=75, monotonic=time.monotonic)
            backend = DeadlineHarborSandbox(SimpleNamespace(exec=local_fixture),
                identifier='local-predetermined-fixture',deadline=deadline)
            started = time.monotonic()
            result = await backend.aexecute('sleep 60.2; printf after-sixty')
            self.assertGreaterEqual(time.monotonic()-started, 60)
            self.assertEqual(result,ExecuteResponse(output='after-sixty',exit_code=0,truncated=False))


if __name__ == '__main__':
    unittest.main()

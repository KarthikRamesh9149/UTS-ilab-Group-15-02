"""Offline command recovery fixtures, without provider access or task scores."""
import asyncio
import json
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from langchain_core.messages import AIMessage, ToolMessage
from custom_backend_tests import FakeEnvironment
from custom_deadline_execution import DeadlineJobs, TaskDeadline
from custom_runner_tests import SequenceModel, completion
from gemini_laptop_agent import GeminiRunner
from gemini_laptop_policy import MODEL
from gemini_recovery_agent import RecoveringDeadlineJobs, RecoveryGeminiRunner
from no_cutoff_capture_backend import NoCutoffHarborSandbox


def deadline():
    return TaskDeadline(deadline_monotonic=time.monotonic() + 30,
                        official_timeout_seconds=30, monotonic=time.monotonic)


class JobRecoveryChecks(unittest.IsolatedAsyncioTestCase):
    def make(self):
        backend = SimpleNamespace(aexecute=AsyncMock(),
            environment=SimpleNamespace(exec=AsyncMock()))
        return RecoveringDeadlineJobs(backend, deadline()), backend

    async def test_unknown_handles_return_feedback_without_execution(self):
        jobs, backend = self.make()
        for identifier in ('unknown', '', None, [], {}):
            for result in (jobs.poll(identifier), await jobs.interrupt(identifier)):
                self.assertEqual(result['error'], 'unknown_command_handle')
                self.assertIn('start_command', result['message'])
        self.assertEqual(jobs.jobs, {})
        backend.aexecute.assert_not_awaited()
        backend.environment.exec.assert_not_awaited()
        await jobs.close()

    async def test_registered_job_results_are_preserved(self):
        jobs, _ = self.make()
        future = asyncio.get_running_loop().create_future()
        jobs.jobs['known'] = (future, '/tmp/synthetic')
        self.assertEqual(jobs.poll('known')['status'], 'running')
        future.set_result(SimpleNamespace(exit_code=7, output='fixture', truncated=True))
        result = jobs.poll('known')
        self.assertEqual(result['exit_code'], 7)
        self.assertEqual(result['output'], 'fixture')
        self.assertTrue(result['truncated'])
        self.assertEqual(await jobs.interrupt('known'), result)
        await jobs.close()

    async def test_real_job_failure_and_cleanup_are_not_hidden(self):
        jobs, _ = self.make()
        future = asyncio.get_running_loop().create_future()
        future.set_exception(ConnectionError('synthetic transport failure'))
        jobs.jobs['known'] = (future, '/tmp/synthetic')
        with self.assertRaises(ConnectionError):
            jobs.poll('known')
        with self.assertRaises(ConnectionError):
            await jobs.interrupt('known')
        with self.assertRaises(RuntimeError):
            await jobs.close()

    async def test_deadline_still_blocks_new_command(self):
        backend = SimpleNamespace(aexecute=AsyncMock())
        clock = [0]
        task_deadline = TaskDeadline(deadline_monotonic=30,
            official_timeout_seconds=30, monotonic=lambda: clock[0])
        jobs = RecoveringDeadlineJobs(backend, task_deadline)
        clock[0] = 30
        with self.assertRaises(TimeoutError):
            await jobs.start('printf fixture')
        backend.aexecute.assert_not_awaited()

    async def test_historical_registry_still_raises_unknown_handle(self):
        jobs = DeadlineJobs(SimpleNamespace(), deadline())
        with self.assertRaises(KeyError):
            jobs.poll('unknown')
        with self.assertRaises(KeyError):
            await jobs.interrupt('unknown')


class GraphRecoveryChecks(unittest.IsolatedAsyncioTestCase):
    async def test_fake_graph_receives_feedback_and_continues(self):
        model = SequenceModel(model_name=MODEL)
        model._sequence = [AIMessage(content='', tool_calls=[dict(name='poll_command',
            id='invalid-poll', args={'job_id': 'not-started'})]),
            AIMessage(content='', tool_calls=[dict(name='interrupt_command',
            id='invalid-interrupt', args={'job_id': 'not-started'})]), completion()]
        task_deadline = deadline()
        environment = FakeEnvironment()
        backend = NoCutoffHarborSandbox(environment, identifier='synthetic-recovery', deadline=task_deadline)
        runner = RecoveryGeminiRunner(model, backend, task_deadline)
        result = await runner.run('Synthetic fixture only', timeout_seconds=30)
        self.assertEqual(result['outcome'], 'agent_reported_complete')
        self.assertIsNone(result['benchmark_success'])
        self.assertEqual(len(model._calls), 3)
        feedback = [json.loads(message.content) for message in runner.state['messages']
                    if isinstance(message, ToolMessage) and message.tool_call_id in
                    ('invalid-poll', 'invalid-interrupt')]
        self.assertEqual(len(feedback), 2)
        self.assertTrue(all(row['error'] == 'unknown_command_handle' for row in feedback))
        self.assertEqual(environment.calls, [])
        self.assertIsNone(runner.model_limit.limit)
        await runner.jobs.close()
        historical = GeminiRunner(SequenceModel(model_name=MODEL), backend, task_deadline)
        self.assertIs(type(historical.jobs), DeadlineJobs)


if __name__ == '__main__':
    unittest.main()

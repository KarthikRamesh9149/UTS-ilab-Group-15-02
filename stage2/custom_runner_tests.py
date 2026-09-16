import unittest
from pydantic import PrivateAttr
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatResult, ChatGeneration
from custom_agent_probe import ScriptedModel
from custom_backend import HarborSandbox
from custom_backend_tests import FakeEnvironment
from custom_control import Condition
from custom_runner import CustomRunner, ModelLimitReached


def completion(summary='Done', checks=None):
    return AIMessage(content='', tool_calls=[{'name': 'complete_task', 'id': 'completion',
        'args': {'summary': summary, 'checks': checks}}])


class SequenceModel(ScriptedModel):
    _sequence: list = PrivateAttr(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self._calls.append(messages)
        response = self._sequence.pop(0)
        if isinstance(response, Exception):
            raise response
        return ChatResult(generations=[ChatGeneration(message=response)])


class RunnerTests(unittest.IsolatedAsyncioTestCase):
    def make(self, sequence, condition=Condition('C0'), limit=10):
        model = SequenceModel()
        model._sequence = sequence
        runner = CustomRunner(model, HarborSandbox(FakeEnvironment(), identifier='test'),
                              condition, max_model_calls=limit)
        return model, runner

    async def test_two_repairs_then_success_in_every_condition(self):
        checks = [{'criterion': 'Required output', 'observation': 'Read back expected content', 'satisfied': True}]
        for condition in [Condition('C0'), Condition('C1'), Condition('C2', 'C0'), Condition('C2', 'C1')]:
            model, runner = self.make([AIMessage(content='Premature final'), completion(''), completion(checks=checks)], condition)
            result = await runner.run('Synthetic task', timeout_seconds=20)
            self.assertEqual(result['repair_cycles'], 2)
            self.assertEqual(result['outcome'], 'agent_reported_complete')
            self.assertIsNone(result['benchmark_success'])
            self.assertEqual(len(model._calls), 3)
            self.assertNotIn('task', model._tool_names)
            self.assertNotIn('write_todos', model._tool_names)

    async def test_stops_after_three_incomplete_attempts(self):
        model, runner = self.make([AIMessage(content='No completion')] * 4)
        result = await runner.run('Synthetic task', timeout_seconds=20)
        self.assertEqual(result['outcome'], 'repair_exhausted')
        self.assertEqual(len(model._calls), 3)

    async def test_transport_failure_is_not_repaired_or_retried(self):
        model, runner = self.make([RuntimeError('Simulated gateway block')])
        with self.assertRaises(RuntimeError):
            await runner.run('Synthetic task', timeout_seconds=20)
        self.assertEqual(len(model._calls), 1)
        self.assertEqual(runner.control.repairs_used, 0)

    async def test_call_limit_survives_repair_invocations(self):
        model, runner = self.make([AIMessage(content='No completion')] * 4, limit=1)
        with self.assertRaises(ModelLimitReached):
            await runner.run('Synthetic task', timeout_seconds=20)
        self.assertEqual(len(model._calls), 1)

    async def test_runner_cannot_replay_a_trial(self):
        model, runner = self.make([completion()])
        await runner.run('Synthetic task', timeout_seconds=20)
        with self.assertRaises(RuntimeError):
            await runner.run('Synthetic task', timeout_seconds=20)
        self.assertEqual(len(model._calls), 1)

    async def test_timeout_is_required_and_bounded(self):
        _, runner = self.make([])
        for value in [None, True, 0, float('inf'), float('nan')]:
            with self.assertRaises(ValueError):
                await runner.run('x', timeout_seconds=value)


if __name__ == '__main__':
    unittest.main()

"""Synthetic clocks and real LangGraph loops; no paid provider or native task."""
import asyncio
from copy import deepcopy
import json
import sys
import unittest
from unittest.mock import AsyncMock

from langchain.agents.middleware import ModelRequest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import PrivateAttr

from custom_backend import HarborSandbox
from custom_backend_tests import FakeEnvironment
from custom_control import Condition
from custom_deadline_guidance import DeadlineGuidance, MARKER
from custom_runner import CustomRunner
from custom_runner_tests import SequenceModel, completion
from test_retry_gateway import Clock


class GuidanceTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.guidance = DeadlineGuidance(deadline_monotonic=1000,
            official_timeout_seconds=900, monotonic=self.clock.monotonic)

    def request(self, system=None):
        return ModelRequest(model=SequenceModel(), system_message=system,
            messages=[HumanMessage(content='Synthetic instruction'),
                AIMessage(content='', tool_calls=[dict(name='execute', id='same-id',
                    args={'command': 'printf fixture'})]),
                ToolMessage(content='Fixture observation', tool_call_id='same-id')],
            model_settings={'temperature': 1., 'top_p': 1., 'max_tokens': 384000},
            tools=[{'name': 'execute'}], tool_choice='auto', state={'fixture': True})

    def test_invalid_clock_and_deadline_configuration(self):
        for name in ('deadline_monotonic', 'official_timeout_seconds'):
            for value in (None, True, False, -1, '90', float('nan'), float('inf'), 10**400):
                options = dict(deadline_monotonic=1000, official_timeout_seconds=900,
                    monotonic=self.clock.monotonic)
                options[name] = value
                with self.subTest(name=name, value=value), self.assertRaises(ValueError):
                    DeadlineGuidance(**options)
        with self.assertRaises(ValueError):
            DeadlineGuidance(deadline_monotonic=1000, official_timeout_seconds=0, monotonic=lambda: 100)
        with self.assertRaises(ValueError):
            DeadlineGuidance(deadline_monotonic=1000, official_timeout_seconds=900, monotonic=100)

    def test_fraction_thresholds_and_expiry_are_exact(self):
        for now, remaining, phase in ((100,900,'work'),(819.999,180,'work'),
                (820,180,'verify'),(954.999,45,'verify'),(955,45,'finish'),
                (999.9,0,'finish'),(1000,0,'expired'),(1100,0,'expired')):
            self.clock.now = now
            self.guidance.note()
            event = self.guidance.events[-1]
            self.assertEqual((event['remaining_seconds'], event['phase']), (remaining, phase))
        self.assertEqual(self.guidance.deadline, 1000)

    def test_same_fraction_policy_scales_with_official_duration(self):
        for duration in (1., 60., 900., 7200.):
            guidance = DeadlineGuidance(deadline_monotonic=duration,
                official_timeout_seconds=duration, monotonic=lambda: duration * .8)
            self.assertIn('running short', guidance.note())
            self.assertEqual(guidance.events[-1]['phase'], 'verify')

    def test_transient_note_does_not_mutate_history_or_request_fields(self):
        original = self.request(SystemMessage(content='Preserved instructions', id='system-id',
            additional_kwargs={'fixture': 'preserved'}))
        messages = deepcopy(original.messages)
        updated = self.guidance.prepare(original)
        self.assertIsNot(original, updated)
        self.assertEqual(original.system_message.content, 'Preserved instructions')
        self.assertEqual(updated.system_message.id, 'system-id')
        self.assertEqual(updated.system_message.additional_kwargs, {'fixture': 'preserved'})
        self.assertEqual(updated.messages, messages)
        for field in ('model', 'messages', 'tools', 'tool_choice', 'response_format',
                      'model_settings', 'state', 'runtime'):
            self.assertIs(getattr(original, field), getattr(updated, field))
        self.assertEqual(updated.system_message.content.count(MARKER), 1)

    def test_structured_system_content_is_preserved_and_not_aliased(self):
        system = SystemMessage(content=[{'type': 'text', 'text': 'Existing policy',
            'cache_control': {'type': 'ephemeral'}}])
        original = self.request(system)
        before = deepcopy(system.content)
        updated = self.guidance.prepare(original)
        self.assertEqual(system.content, before)
        self.assertEqual(updated.system_message.content[:-1], before)
        updated.system_message.content[0]['cache_control']['type'] = 'changed'
        self.assertEqual(system.content, before)

    def test_request_without_system_message_gets_one_note(self):
        original = self.request()
        updated = self.guidance.prepare(original)
        self.assertIsNone(original.system_message)
        self.assertIn(MARKER, updated.system_message.content)

    def test_repeated_requests_do_not_accumulate_stale_time_messages(self):
        request = self.request(SystemMessage(content='Stable prefix'))
        first = self.guidance.prepare(request)
        self.clock.now = 821
        second = self.guidance.prepare(request)
        self.assertIn('900 seconds', first.system_message.content)
        self.assertIn('179 seconds', second.system_message.content)
        self.assertNotIn('900 seconds', second.system_message.content)
        self.assertEqual(second.system_message.content.count(MARKER), 1)
        self.assertEqual(request.system_message.content, 'Stable prefix')

    def test_malformed_or_backwards_clock_is_not_silently_reset(self):
        self.guidance.note()
        for value in (99, None, True, '100', float('nan'), float('inf'), -1):
            self.clock.now = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.guidance.note()
        self.assertEqual(len(self.guidance.events), 1)

    def test_future_deadline_does_not_grant_more_than_official_time(self):
        self.clock.now = 99
        with self.assertRaises(ValueError):
            self.guidance.note()
        self.assertEqual(self.guidance.events, [])

    def test_metadata_has_no_task_text_tools_or_raw_monotonic_deadline(self):
        self.guidance.prepare(self.request(SystemMessage(content='Private content')))
        metadata = self.guidance.metadata()
        encoded = json.dumps(metadata)
        for value in ('Private content', 'Synthetic instruction', 'Fixture observation',
                      'printf fixture', 'deadline_monotonic'):
            self.assertNotIn(value, encoded)
        metadata['events'][0]['phase'] = 'changed'
        self.assertEqual(self.guidance.events[0]['phase'], 'work')

    def test_expiry_does_not_create_a_new_early_stop_or_call_cap(self):
        self.clock.now = 1001
        called = []
        reply = AIMessage(content='Fixture')
        result = self.guidance.wrap_model_call(self.request(), lambda r: called.append(r) or reply)
        self.assertIs(result, reply)
        self.assertEqual(len(called), 1)
        self.assertEqual(self.guidance.events[0]['phase'], 'expired')

    async def test_async_handler_is_invoked_once_without_retry(self):
        handler = AsyncMock(return_value=AIMessage(content='Fixture'))
        result = await self.guidance.awrap_model_call(self.request(), handler)
        self.assertIs(result, handler.return_value)
        handler.assert_awaited_once()
        failing = AsyncMock(side_effect=RuntimeError('Synthetic transport error'))
        with self.assertRaises(RuntimeError):
            await self.guidance.awrap_model_call(self.request(), failing)
        failing.assert_awaited_once()

    async def test_cancellation_is_preserved(self):
        handler = AsyncMock(side_effect=asyncio.CancelledError)
        with self.assertRaises(asyncio.CancelledError):
            await self.guidance.awrap_model_call(self.request(), handler)
        handler.assert_awaited_once()


class AdvancingModel(SequenceModel):
    _clock: object = PrivateAttr()
    _advance: float = PrivateAttr(default=150.)

    def _generate(self, *args, **kwargs):
        response = super()._generate(*args, **kwargs)
        self._clock.now += self._advance
        return response


class GuidanceGraphTests(unittest.IsolatedAsyncioTestCase):
    def make(self, *, condition=Condition('C0'), sequence=None):
        clock = Clock()
        guidance = DeadlineGuidance(deadline_monotonic=1000,
            official_timeout_seconds=900, monotonic=clock.monotonic)
        model = AdvancingModel()
        model._clock = clock
        model._sequence = sequence or [AIMessage(content='', tool_calls=[dict(
            name='execute', id='fixture-tool', args={'command': 'printf fixture'})]), completion()]
        runner = CustomRunner(model, HarborSandbox(FakeEnvironment(), identifier='synthetic'),
            condition, max_model_calls=None, model_middleware=(guidance,))
        return model, runner, guidance

    async def test_real_graph_sees_current_time_without_persisting_it(self):
        model, runner, guidance = self.make()
        result = await runner.run('Synthetic only', timeout_seconds=10)
        self.assertEqual(result['outcome'], 'agent_reported_complete')
        self.assertIsNone(result['benchmark_success'])
        self.assertEqual(len(model._calls), 2)
        for index, remaining in enumerate((900, 750)):
            system = next(m for m in model._calls[index] if isinstance(m, SystemMessage))
            self.assertIn(f'{remaining} seconds', system.text)
            self.assertEqual(system.text.count(MARKER), 1)
        self.assertTrue(any(isinstance(m, ToolMessage) and m.tool_call_id == 'fixture-tool'
            for m in model._calls[1]))
        self.assertFalse(any(MARKER in str(m.content) for m in runner.state['messages']))
        self.assertEqual(len(guidance.events), runner.model_limit.attempts)
        self.assertEqual(runner.graph_recursion_limit, sys.maxsize)

    async def test_completion_gate_and_repair_reinvocations_keep_parent_behaviour(self):
        checks = [dict(criterion='Fixture', observation='Read fixture', satisfied=True)]
        model, runner, guidance = self.make(condition=Condition('C2', 'C1'),
            sequence=[completion(), completion(checks=checks)])
        result = await runner.run('Synthetic only', timeout_seconds=10)
        self.assertEqual(result['repair_cycles'], 1)
        self.assertEqual(result['outcome'], 'agent_reported_complete')
        self.assertEqual(runner.control.condition, Condition('C2', 'C1'))
        self.assertEqual([r['remaining_seconds'] for r in guidance.events], [900, 750])
        self.assertEqual(len(model._calls), 2)

    async def test_hard_timeout_and_cleanup_are_not_replaced_by_advice(self):
        _, runner, _ = self.make()
        async def stall(*args, **kwargs):
            await asyncio.sleep(5)
            yield {'messages': []}
        runner.graph.astream = stall
        runner.jobs.close = AsyncMock()
        with self.assertRaises(TimeoutError):
            await runner.run('Synthetic only', timeout_seconds=.01)
        runner.jobs.close.assert_awaited_once()
        with self.assertRaises(RuntimeError):
            await runner.run('No replay', timeout_seconds=10)

    async def test_more_than_100_calls_remain_possible(self):
        calls = [AIMessage(content='', tool_calls=[dict(name='execute', id=f'synthetic-{i}',
            args={'command': 'printf fixture'})]) for i in range(103)] + [completion()]
        model, runner, guidance = self.make(sequence=calls)
        model._advance = .1
        await runner.run('Synthetic only', timeout_seconds=45)
        self.assertEqual(len(model._calls), 104)
        self.assertEqual(len(guidance.events), 104)
        self.assertIsNone(runner.model_limit.limit)

    async def test_new_extension_requires_an_explicit_middleware_tuple(self):
        for value in (None, [], [object()], (object(),), 'middleware'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                CustomRunner(SequenceModel(), HarborSandbox(FakeEnvironment(), identifier='synthetic'),
                    Condition('C0'), max_model_calls=None, model_middleware=value)


if __name__ == '__main__':
    unittest.main()

"""Fake-model and budget checks; no paid inference and no benchmark score."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from decimal import Decimal
from aiohttp import ClientSession, web
from langchain_core.messages import AIMessage
from custom_runner_tests import SequenceModel, completion
from custom_backend_tests import FakeEnvironment
from custom_deadline_execution import TaskDeadline
from no_cutoff_capture_backend import NoCutoffHarborSandbox
from gemini_laptop_agent import GeminiRunner
from gemini_laptop_gateway import Gateway
from gemini_laptop_policy import (MODEL, SNAPSHOT, PROVIDER, PROTOCOL, CAP,
    CONTEXT, MAX_OUTPUT, INPUT_PRICE, OUTPUT_PRICE, RESERVATION, Ledger, BudgetStop, wire)


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'ledger.json'

    def test_reservation_bounds_full_context_and_output(self):
        self.assertGreater(RESERVATION, CONTEXT * INPUT_PRICE + MAX_OUTPUT * OUTPUT_PRICE)

    def test_unresolved_requests_survive_restart_and_block_overspend(self):
        ledger = Ledger(self.path, 20)
        for _ in range(18):
            ledger.reserve('fixture', 20)
        with self.assertRaises(BudgetStop):
            ledger.reserve('fixture', 20)
        self.assertEqual(Ledger(self.path, 30).unresolved, Decimal('19.80'))
        self.assertEqual(Ledger(self.path, 30).data['cap_usd'], '20')

    def test_actual_cost_frees_only_settled_reservation(self):
        ledger = Ledger(self.path, 2)
        row = ledger.reserve('fixture', 2)
        with self.assertRaises(BudgetStop):
            ledger.reserve('fixture', 2)
        ledger.settle(row, '.10')
        ledger.reserve('fixture', 1.9)
        self.assertEqual(ledger.known, Decimal('.10'))

    def test_lower_credit_and_pending_charge(self):
        ledger = Ledger(self.path, 20)
        ledger.reserve('fixture', 20)
        with self.assertRaises(BudgetStop):
            ledger.reserve('fixture', '2.10')
        with self.assertRaises(ValueError):
            Ledger(self.path.with_name('bad.json'), 'NaN')
        with self.assertRaises(RuntimeError):
            ledger.settle(ledger.data['requests'][0], '1.11')

    def test_wire_forces_same_model_and_route(self):
        request = wire(dict(model=MODEL, messages=[{'role':'user','content':'synthetic'}],
            temperature=0, max_tokens=1, reasoning={'effort':'low'}))
        self.assertEqual(request['model'], MODEL)
        self.assertEqual(request['provider']['only'], [PROVIDER])
        self.assertFalse(request['provider']['allow_fallbacks'])
        self.assertEqual(request['reasoning']['effort'], 'high')
        self.assertEqual(request['max_tokens'], MAX_OUTPUT)
        for override in ({'model': 'other'}, {'plugins': [{'id':'web'}]}, {'stream':True},
                {'messages':[{'role':'user','content':[{'type':'image_url'}]}]}):
            with self.assertRaises(ValueError):
                wire(dict(model=MODEL, messages=[{'role':'user','content':'fixture'}]) | override)


class Response:
    status = 200
    def __init__(self, body): self.body = body
    async def __aenter__(self): return self
    async def __aexit__(self, *args): pass
    async def json(self): return self.body


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.gateway = Gateway('synthetic-key', Path(self.temp.name))
        async def metadata(path):
            if path == '/key': return dict(limit=30, limit_remaining=20, usage=10)
            if path == '/credits': return dict(total_credits=30,total_usage=10)
            if path.startswith('/generation'): return dict(total_cost='.01',model=SNAPSHOT,provider_name='Google AI Studio')
            return {'endpoints':[dict(tag=PROVIDER,context_length=CONTEXT,
                max_completion_tokens=MAX_OUTPUT,pricing=dict(prompt=str(INPUT_PRICE),completion=str(OUTPUT_PRICE)),name=SNAPSHOT)]}
        self.gateway.get = metadata
        await self.gateway.start()
        self.addAsyncCleanup(self.gateway.close)
        import time
        self.gateway.activate('synthetic', time.monotonic()+60)

    async def test_loopback_auth_route_and_revocation(self):
        body = dict(id='synthetic-generation',model=SNAPSHOT,provider='Google AI Studio',
            choices=[dict(index=0, finish_reason='stop', message=dict(role='assistant',content='synthetic'))],usage={'cost':'.01'})
        with patch.object(self.gateway.session, 'post', return_value=Response(body)) as posted:
            async with ClientSession() as client:
                url = self.gateway.url + '/chat/completions'
                payload = dict(model=MODEL,messages=[dict(role='user',content='synthetic')])
                async with client.post(url,json=payload) as response:
                    self.assertEqual(response.status,403)
                async with client.post(url,json=payload,headers={'Authorization':'Bearer '+self.gateway.token}) as response:
                    self.assertEqual(response.status,200)
                self.assertEqual(posted.call_args.kwargs['json']['provider']['only'],[PROVIDER])
                await self.gateway.revoke()
                async with client.post(url,json=payload,headers={'Authorization':'Bearer '+self.gateway.token}) as response:
                    self.assertEqual(response.status,403)
        self.assertEqual(self.gateway.ledger.known,Decimal('.01'))

    async def test_route_mismatch_stops_study(self):
        with patch.object(self.gateway.session,'post',return_value=Response(
                dict(id='fake',model='other',provider='other',usage={'cost':'.01'}))):
            response = await self.gateway.dispatch(wire(dict(model=MODEL,messages=[dict(role='user',content='fixture')])),self.gateway.active)
            self.assertEqual(response.status,502)
            self.assertEqual(self.gateway.stop_reason,'routing_mismatch')

    async def test_transport_failure_retains_reservation_no_retry(self):
        with patch.object(self.gateway.session,'post',side_effect=TimeoutError) as posted:
            await self.gateway.dispatch(wire(dict(model=MODEL,messages=[dict(role='user',content='fixture')])),self.gateway.active)
            self.assertEqual(posted.call_count,1)
        self.assertEqual(self.gateway.ledger.unresolved, RESERVATION)
        self.assertEqual(self.gateway.stop_reason,'provider_transport_failure')


class ModelTests(unittest.IsolatedAsyncioTestCase):
    def test_langfuse_gemini_track_metadata_only(self):
        from local_trace import observation
        from local_langfuse import payload
        event = observation(trial_id='synthetic',task_id='fixture',harness='C0-NC',
            protocol_sha256='a'*64,kind='trial',sequence=0,started_ns=1,ended_ns=2)
        exported = json.dumps(payload([event],track='gemini-laptop'))
        self.assertIn('gemini-laptop',exported)
        self.assertNotIn('messages',exported)

    async def test_gemini_runner_fake_completion_and_model_check(self):
        import time
        deadline = TaskDeadline(deadline_monotonic=time.monotonic()+30,official_timeout_seconds=30,monotonic=time.monotonic)
        model = SequenceModel(model_name=MODEL)
        model._sequence = [AIMessage(content='synthetic incomplete'), completion()]
        backend = NoCutoffHarborSandbox(FakeEnvironment(),identifier='synthetic',deadline=deadline)
        runner = GeminiRunner(model,backend,deadline)
        result = await runner.run('Synthetic only',timeout_seconds=30)
        self.assertEqual(result['outcome'],'agent_reported_complete')
        self.assertEqual(len(model._calls),2)
        self.assertIsNone(runner.model_limit.limit)
        self.assertNotIn('task',model._tool_names)
        self.assertNotIn('write_todos',model._tool_names)
        await runner.jobs.close()
        with self.assertRaises(ValueError):
            GeminiRunner(SequenceModel(),backend,deadline)


if __name__ == '__main__':
    unittest.main()

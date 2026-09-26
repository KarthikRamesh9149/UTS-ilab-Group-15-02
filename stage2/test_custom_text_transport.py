"""Synthetic text/media messages only; no task trajectories or paid provider."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

import httpx
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI

from credit_only_gateway import prepare_credit_request
from custom_model import gateway_model
from custom_text_transport import ATTACHMENT_NOTICE, TEXT_PROFILE, TextGatewayChatOpenAI, text_content
from gateway_policy import MODEL
from retry_policy import SETTINGS
from custom_backend import HarborSandbox
from custom_control import Condition
from custom_runner import CustomRunner


class TextTransportTests(unittest.TestCase):
    def model(self, **overrides):
        return gateway_model('http://127.0.0.1:9/v1', 'synthetic-only',
            max_output_tokens=384000, completion_wait_seconds=60,
            temperature=1., top_p=1., reasoning_effort='high', **overrides)

    def test_legacy_default_is_unchanged(self):
        self.assertIs(type(self.model()), ChatOpenAI)

    def test_explicit_transport_profile_and_protocol(self):
        model = self.model(text_only_transport=True)
        self.assertIsInstance(model, TextGatewayChatOpenAI)
        self.assertEqual(model.profile, TEXT_PROFILE)
        self.assertEqual((model.max_tokens, model.temperature, model.top_p), (384000, 1., 1.))
        self.assertEqual(model.max_retries, 0)
        self.assertEqual(model.extra_body, {'reasoning': {'effort': 'high'}})
        for invalid in (None, 0, 1, 'yes'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.model(text_only_transport=invalid)

    def test_text_is_preserved_and_input_is_not_mutated(self):
        content = [{'type': 'text', 'text': 'alpha'}, 'beta', {'type': 'text', 'text': 'gamma'}]
        before = deepcopy(content)
        self.assertEqual(text_content(content), 'alpha\nbeta\ngamma')
        self.assertEqual(content, before)
        self.assertEqual(text_content('unchanged'), 'unchanged')
        self.assertIsNone(text_content(None))
        self.assertEqual(text_content([]), '')

    def test_attachment_bytes_and_urls_are_never_sent_as_text(self):
        for block in ({'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,SECRET'}},
                      {'type': 'image', 'base64': 'SECRET'},
                      {'type': 'file', 'file': {'file_data': 'SECRET'}},
                      {'type': 'input_audio', 'input_audio': {'data': 'SECRET'}},
                      {'type': 'video', 'url': 'https://private.invalid/SECRET'},
                      {'type': 'unknown', 'text': 'SECRET'}):
            with self.subTest(kind=block['type']):
                self.assertEqual(text_content([block]), ATTACHMENT_NOTICE)

    def test_real_client_serialization_accepts_multimedia_tool_history_as_text(self):
        model = self.model(text_only_transport=True)
        messages = [HumanMessage(content='Synthetic file read'),
            AIMessage(content='', tool_calls=[{'name': 'read_file', 'id': 'file-read', 'args': {'file_path': '/tmp/fixture.png'}}]),
            ToolMessage(content=[{'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,SECRET'}}], tool_call_id='file-read')]
        payload = model._get_request_payload(messages)
        # The OpenAI SDK merges extra_body before sending; reproduce that
        # merge here for the pure shared-gateway admission check.
        payload.update(payload.pop('extra_body', {}))
        request = prepare_credit_request(payload, SETTINGS)
        self.assertEqual(request['messages'][-1]['content'], ATTACHMENT_NOTICE)
        self.assertEqual(request['messages'][-1]['tool_call_id'], 'file-read')
        self.assertEqual(request['messages'][-2]['tool_calls'][0]['id'], 'file-read')
        self.assertNotIn('SECRET', json.dumps(request))
        self.assertNotIn('max_price', request['provider'])

    def test_actual_sdk_wire_uses_shared_gateway_protocol(self):
        seen = []
        def respond(request):
            payload = json.loads(request.content)
            seen.append(prepare_credit_request(payload, SETTINGS))
            return httpx.Response(200, json={'id': 'synthetic-response', 'object': 'chat.completion',
                'created': 1, 'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
                'message': {'role': 'assistant', 'content': 'fixture acknowledged'}}]})
        model = self.model(text_only_transport=True)
        client = httpx.Client(transport=httpx.MockTransport(respond))
        original = model.root_client._client
        model.root_client._client = client
        try:
            response = model.invoke([HumanMessage(content=[{'type': 'text', 'text': 'fixture'},
                {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,SECRET'}}])])
            self.assertEqual(response.content, 'fixture acknowledged')
            self.assertEqual(len(seen), 1)
            self.assertEqual(seen[0]['messages'][0]['content'], 'fixture\n' + ATTACHMENT_NOTICE)
            self.assertEqual(seen[0]['reasoning'], {'effort': 'high'})
            self.assertFalse(seen[0]['stream'])
        finally:
            model.root_client._client = original
            client.close()


class GraphFileTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_deepagents_file_tool_round_trip_is_text_only(self):
        requests, commands = [], []
        async def execute(command, **kwargs):
            commands.append(command)
            # Real BaseSandbox parsing and real filesystem middleware; only
            # container IO and provider responses are synthetic here.
            output = json.dumps({'encoding': 'base64', 'content': 'U1lOVEhFVElD'})
            return SimpleNamespace(return_code=0, stdout=json.dumps(dict(
                output=output, exit_code=0, truncated=False)))
        async def respond(request):
            wire = json.loads(request.content)
            requests.append(prepare_credit_request(wire, SETTINGS))
            name = 'read_file' if len(requests) == 1 else 'complete_task'
            args = {'file_path': '/tmp/synthetic.png'} if len(requests) == 1 else {'summary': 'Synthetic check complete'}
            return httpx.Response(200, json={'id': 'fixture-' + str(len(requests)),
                'object': 'chat.completion', 'created': 1, 'model': MODEL,
                'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                    'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'call-' + str(len(requests)),
                        'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}}]})
        model = gateway_model('http://127.0.0.1:9/v1', 'synthetic-only',
            max_output_tokens=384000, completion_wait_seconds=60,
            temperature=1., top_p=1., reasoning_effort='high', text_only_transport=True)
        original = model.root_async_client._client
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            model.root_async_client._client = client
            try:
                runner = CustomRunner(model, HarborSandbox(SimpleNamespace(exec=execute), identifier='fixture'),
                    Condition('C0'), max_model_calls=None)
                outcome = await runner.run('Read the synthetic image, then report completion.', timeout_seconds=15)
            finally:
                model.root_async_client._client = original
        self.assertEqual(outcome['outcome'], 'agent_reported_complete')
        self.assertEqual(len(requests), 2)
        self.assertEqual(len(commands), 1)
        wire = requests[-1]['messages']
        self.assertTrue(all(message.get('content') is None or isinstance(message['content'], str) for message in wire))
        self.assertNotIn('U1lOVEhFVElD', json.dumps(wire))
        self.assertTrue(any('not attached' in (message.get('content') or '')
            or ATTACHMENT_NOTICE in (message.get('content') or '') for message in wire))
        self.assertEqual(requests[0]['provider'], requests[1]['provider'])


if __name__ == '__main__':
    unittest.main()

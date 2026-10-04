"""Offline tests for the OpenRouter client. No network access; no paid calls."""
import asyncio
from decimal import Decimal
from pathlib import Path
import sys
import unittest
from unittest import mock

import httpx

from saranya_harness import openrouter
from saranya_harness.openrouter import ModelError, OpenRouterClient, build_payload, estimate_cost

STAGE2 = Path(__file__).resolve().parents[3] / 'stage2'


def ok_body(**usage):
    return {'id': 'gen-1', 'model': openrouter.MODEL, 'provider': 'DeepInfra',
            'choices': [{'message': {'content': 'DONE'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 20, **usage}}


def client_with(handler, sleeps=None):
    async def sleep(seconds):
        if sleeps is not None:
            sleeps.append(seconds)
    return OpenRouterClient('test-key', transport=httpx.MockTransport(handler), sleep=sleep)


class Stage2ParityTest(unittest.TestCase):
    """Reads Karthik's Stage 2 settings (read-only) and checks this harness matches them."""

    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True  # never write __pycache__ into stage2/
        sys.path.insert(0, str(STAGE2))
        import gateway_policy, retry_policy
        cls.gateway_policy, cls.settings = gateway_policy, retry_policy.SETTINGS

    @classmethod
    def tearDownClass(cls):
        sys.path.remove(str(STAGE2))

    def test_payload_matches_stage2_request(self):
        messages = [{'role': 'user', 'content': 'x'}]
        stage2 = self.gateway_policy.prepare_request({
            'model': self.gateway_policy.MODEL, 'messages': messages,
            'max_tokens': self.settings.max_output_tokens, 'temperature': self.settings.temperature,
            'reasoning_effort': self.settings.reasoning_effort})
        # The corrected baselines and C0 removed the price filter (credit_only_gateway.py).
        stage2['provider'].pop('max_price')
        stage2['top_p'] = 1.0  # added by model_protocol.enforce
        self.assertEqual(build_payload(messages), stage2)

    def test_prices_match_stage2_model_info(self):
        info = self.settings.model_info
        self.assertEqual(float(openrouter.INPUT_PRICE), info['input_cost_per_token'])
        self.assertEqual(float(openrouter.OUTPUT_PRICE), info['output_cost_per_token'])


class ClientTest(unittest.TestCase):
    def test_reported_cost_and_tokens_are_parsed(self):
        client = client_with(lambda request: httpx.Response(200, json=ok_body(
            cost=0.0012, prompt_tokens_details={'cached_tokens': 40})))
        result = asyncio.run(client.complete([{'role': 'user', 'content': 'x'}]))
        self.assertEqual(result.reported_cost_usd, Decimal('0.0012'))
        self.assertEqual((result.prompt_tokens, result.completion_tokens, result.cached_tokens), (100, 20, 40))
        self.assertEqual(result.provider, 'DeepInfra')

    def test_rate_limits_are_retried_without_count_cap(self):
        calls, sleeps = [], []

        def handler(request):
            calls.append(request)
            if len(calls) <= 5:
                return httpx.Response(429, headers={'retry-after': '3'}, json={'error': {}})
            return httpx.Response(200, json=ok_body())
        result = asyncio.run(client_with(handler, sleeps).complete([{'role': 'user', 'content': 'x'}]))
        self.assertEqual(result.retries, 5)
        self.assertEqual(sleeps, [3.0] * 5)

    def test_bad_request_raises_without_leaking_key(self):
        client = client_with(lambda request: httpx.Response(
            400, json={'error': {'code': 400, 'metadata': {'error_type': 'context_length_exceeded'}}}))
        with self.assertRaises(ModelError) as caught:
            asyncio.run(client.complete([{'role': 'user', 'content': 'x'}]))
        self.assertEqual(caught.exception.error_type, 'context_length_exceeded')
        self.assertNotIn('test-key', str(caught.exception))

    def test_request_sends_key_from_constructor_only_in_header(self):
        seen = {}

        def handler(request):
            seen['auth'] = request.headers['authorization']
            seen['body'] = request.content.decode()
            return httpx.Response(200, json=ok_body())
        asyncio.run(client_with(handler).complete([{'role': 'user', 'content': 'x'}]))
        self.assertEqual(seen['auth'], 'Bearer test-key')
        self.assertNotIn('test-key', seen['body'])

    def test_missing_key_is_refused(self):
        with mock.patch.dict('os.environ', {}, clear=True):
            with self.assertRaises(ModelError):
                OpenRouterClient()

    def test_estimate_cost(self):
        self.assertEqual(estimate_cost(1_000_000, 1_000_000), Decimal('0.24'))
        self.assertIsNone(estimate_cost(None, 5))


if __name__ == '__main__':
    unittest.main()

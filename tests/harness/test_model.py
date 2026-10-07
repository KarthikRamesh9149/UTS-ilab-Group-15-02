"""Pinned client configuration and immutable model protocol, without model calls."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from uts_harness.model import gateway_model
from uts_harness.model_protocol import MODEL, ENDPOINT, ModelSettings, freeze_protocol, read_protocol
from uts_harness.private_io import private_directory
from uts_harness.settings import SETTINGS


class ModelProtocolTests(unittest.TestCase):
    def test_settings_match_measured_configuration(self):
        self.assertEqual(SETTINGS.document(), dict(schema_version=1, model=MODEL,
            endpoint=ENDPOINT, top_p=1., max_output_tokens=384000,
            temperature=1., reasoning_effort='high'))
        self.assertEqual(len(SETTINGS.fingerprint()), 64)

    def test_settings_refuse_invalid_limits_sampling_and_reasoning(self):
        for tokens in (0, -1, True, 384001, '100'):
            with self.assertRaises(ValueError):
                ModelSettings(tokens, 1., 'high')
        for temperature in (True, None, -1, 3, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                ModelSettings(384000, temperature, 'high')
        for reasoning in (None, '', 'maximum'):
            with self.assertRaises(ValueError):
                ModelSettings(384000, 1., reasoning)

    def test_request_validation_preserves_data_and_pins_sampling(self):
        request = dict(model=MODEL, max_tokens=200, temperature=1.,
            reasoning={'effort': 'high'}, messages=[{'role': 'user', 'content': 'fixture'}])
        before = deepcopy(request)
        validated = SETTINGS.enforce(request)
        self.assertEqual(request, before)
        self.assertEqual(validated, dict(request, top_p=1.))
        for override in ({'model': 'other'}, {'max_tokens': True}, {'max_tokens': 384001},
                {'temperature': 0.}, {'reasoning': {'effort': 'low'}}, {'seed': 1},
                {'top_p': .9}, {'top_p': True}):
            with self.subTest(override=override), self.assertRaises(ValueError):
                SETTINGS.enforce(request | override)

    def test_frozen_protocol_cannot_be_changed(self):
        with tempfile.TemporaryDirectory() as folder:
            runtime = private_directory(Path(folder) / 'runtime')
            self.assertEqual(freeze_protocol(runtime, SETTINGS), SETTINGS.fingerprint())
            self.assertEqual(read_protocol(runtime), SETTINGS)
            self.assertEqual(freeze_protocol(runtime, SETTINGS), SETTINGS.fingerprint())
            with self.assertRaises(ValueError):
                freeze_protocol(runtime, ModelSettings(100, 1., 'high'))
            self.assertEqual(read_protocol(runtime), SETTINGS)


class LoopbackClientTests(unittest.TestCase):
    def create(self, url, **options):
        return gateway_model(url, 'fixture-token', max_output_tokens=384000,
            completion_wait_seconds=60, temperature=1., top_p=1., reasoning_effort='high', **options)

    def test_direct_provider_and_unexpected_urls_are_rejected(self):
        for url in ('https://openrouter.ai/api/v1', 'http://localhost:9/v1',
                'http://0.0.0.0:9/v1', 'http://127.0.0.1/v1', 'http://127.0.0.1:9',
                'http://127.0.0.1:9/v1?x=1', 'http://127.0.0.1:9/v1#x',
                'http://user:pass@127.0.0.1:9/v1', 'https://127.0.0.1:9/v1'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.create(url)

    def test_client_configuration_is_nonstreaming_and_no_sdk_retries(self):
        client = self.create('http://127.0.0.1:9/v1')
        self.assertEqual(client.model_name, MODEL)
        self.assertEqual(client.max_retries, 0)
        self.assertFalse(client.streaming)
        self.assertFalse(client.use_responses_api)
        self.assertEqual(client.extra_body, {'reasoning': {'effort': 'high'}})


if __name__ == '__main__':
    unittest.main()

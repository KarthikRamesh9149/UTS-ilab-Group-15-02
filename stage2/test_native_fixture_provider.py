"""Validate scripted wire fixtures; these are not model evaluations."""
import json
import unittest
from unittest.mock import patch

from production_runtime_probe import gateway_fixture


class NativeFixtureProviderTests(unittest.TestCase):
    def run_sequence(self, custom):
        names = ('execute', 'complete_task') if custom else ('execute_bash', 'finish')
        def serve(*args):
            from openrouter_transport import OpenRouter
            provider = OpenRouter('synthetic')
            request = {'reasoning': {'effort': 'high'}, 'temperature': 1., 'max_tokens': 8192,
                       'tools': [{'function': {'name': name}} for name in names]}
            for expected in names:
                reply = provider.complete(request)
                call = reply['choices'][0]['message']['tool_calls'][0]['function']
                self.assertEqual(call['name'], expected)
                arguments = json.loads(call['arguments'])
                self.assertIn('command' if expected == names[0] else 'summary' if custom else 'message', arguments)
                self.assertEqual(provider.generation(reply['id'])['total_cost'], '.000001')
            with self.assertRaises(ValueError): provider.complete(request)
        with patch('scored_gateway.serve', side_effect=serve), patch('scored_gateway.durable_json'):
            gateway_fixture(native_openhands=not custom, native_custom=custom)

    def test_custom_tool_sequence(self): self.run_sequence(True)

    def test_openhands_tool_sequence(self): self.run_sequence(False)

    def test_ambiguous_harness_rejected(self):
        with self.assertRaises(ValueError): gateway_fixture(True, True)

    def test_model_settings_drift_rejected(self):
        def serve(*args):
            from openrouter_transport import OpenRouter
            with self.assertRaises(ValueError):
                OpenRouter('synthetic').complete({'temperature': 0})
        with patch('scored_gateway.serve', side_effect=serve):
            gateway_fixture(native_custom=True)

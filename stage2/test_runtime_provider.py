import unittest
from unittest.mock import patch
from production_runtime_probe import gateway_fixture


class ProviderFixtureTests(unittest.TestCase):
    def request(self):
        return {'temperature': 1., 'reasoning': {'effort': 'high'}, 'max_tokens': 8192,
                'tools': [{'function': {'name': name}} for name in ['execute_bash', 'finish']]}

    def with_provider(self, check):
        def serve(*args, completion_wait_seconds):
            self.assertEqual(completion_wait_seconds, 240.)
            from openrouter_transport import OpenRouter
            check(OpenRouter())  # Patched by the fixture; never a real transport.
        with patch('scored_gateway.serve', side_effect=serve), patch('scored_gateway.durable_json'):
            gateway_fixture(native_openhands=True, completion_wait_seconds=240.)

    def test_native_tool_sequence_and_no_third_call(self):
        def check(provider):
            for name in ['execute_bash', 'finish']:
                response = provider.complete(self.request())
                self.assertEqual(response['choices'][0]['message']['tool_calls'][0]['function']['name'], name)
            with self.assertRaises(ValueError): provider.complete(self.request())
        self.with_provider(check)

    def test_dropped_reasoning_or_changed_limit_is_not_a_pass(self):
        for key in ['reasoning', 'temperature', 'max_tokens']:
            def check(provider):
                request = self.request()
                del request[key]
                with self.assertRaises(ValueError): provider.complete(request)
            self.with_provider(check)

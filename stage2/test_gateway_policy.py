import unittest
from gateway_policy import MODEL, prepare_request


class GatewayPolicyTests(unittest.TestCase):
    def test_completion_limit_alias_is_canonical_without_mutation(self):
        original = self.request()
        original['max_completion_tokens'] = original.pop('max_tokens')
        result = prepare_request(original)
        self.assertEqual(result['max_tokens'], 32)
        self.assertNotIn('max_completion_tokens', result)
        self.assertNotIn('max_tokens', original)

    def test_ambiguous_and_invalid_completion_alias_rejected(self):
        with self.assertRaises(ValueError):
            prepare_request(self.request(max_completion_tokens=32))
        for value in [True, None, 0, 384001, 2.5]:
            request = self.request()
            del request['max_tokens']
            request['max_completion_tokens'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                prepare_request(request)

    def request(self, **extra):
        return dict({'model': MODEL, 'messages': [{'role': 'user', 'content': 'fixture'}],
                     'max_tokens': 32}, **extra)

    def test_routing_pinned_and_fallback_disabled(self):
        original = self.request()
        prepared = prepare_request(original)
        self.assertNotIn('provider', original)
        self.assertEqual(prepared['provider']['only'], ['deepinfra/fp8'])
        self.assertFalse(prepared['provider']['allow_fallbacks'])
        self.assertEqual(prepared['messages'], original['messages'])

    def test_bypass_fields_rejected(self):
        for field, value in [('provider', {}), ('models', ['other']), ('plugins', [{}]),
                             ('transforms', ['middle-out']), ('api_key', 'fixture')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                prepare_request(self.request(**{field: value}))

    def test_unqualified_features_rejected(self):
        for override in [{'stream': True}, {'model': 'other'}, {'max_tokens': None},
                         {'max_tokens': True}, {'temperature': float('nan')},
                         {'messages': [{'role': 'user', 'content': [{'type': 'image_url'}]}]}]:
            with self.subTest(override=override), self.assertRaises(ValueError):
                prepare_request(self.request(**override))

    def test_tool_calls_and_reasoning_preserved(self):
        original = self.request(tools=[{'type':'function','function':{'name':'exec','parameters':{'type':'object'}}}],
                                reasoning={'effort':'low'})
        prepared = prepare_request(original)
        self.assertEqual(prepared['tools'], original['tools'])
        self.assertEqual(prepared['reasoning'], original['reasoning'])

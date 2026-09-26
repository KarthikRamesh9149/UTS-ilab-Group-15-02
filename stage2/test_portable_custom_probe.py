"""Synthetic rehearsal contract tests, never a scored or provider request."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from gateway_policy import ENDPOINT
from openrouter_transport import TransportError
from portable_custom_probe import SyntheticProvider, PREPARE, PNG, EXPECTED_LOGICAL
from portable_custom_policy import SETTINGS
from portable_custom_study import PROBE_CASES, probe_checks
from test_retry_gateway import Clock


class ProviderFixtureTests(unittest.TestCase):
    def request(self, content=None):
        return dict(max_tokens=SETTINGS.max_output_tokens, temperature=1., top_p=1.,
            provider={'only': [ENDPOINT], 'allow_fallbacks': False}, reasoning={'effort': 'high'},
            messages=[] if content is None else [{'role': 'tool', 'content': content}],
            tools=[{'function': {'name': n}} for n in ['execute', 'read_file', 'edit_file',
                'start_command', 'poll_command', 'complete_task']])

    def test_only_fake_credential_and_exact_protocol_are_accepted(self):
        with self.assertRaises(ValueError): SyntheticProvider('not-the-fixture', clock=Clock())
        provider = SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        for change in ({'temperature': 0}, {'max_tokens': 100}, {'provider': {'only': ['other']}},
                       {'messages': [{'role': 'tool', 'content': [{'type': 'image'}]}]}):
            with self.assertRaises((AssertionError, KeyError)):
                provider.complete(self.request() | change, on_response_headers=lambda _: None)
        self.assertEqual(provider.calls, 0)

    def test_full_script_requires_observed_tool_results(self):
        provider = SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        with self.assertRaises(TransportError):
            provider.complete(self.request(), on_response_headers=lambda _: None)
        results = [None, 'BACKGROUND_READY', 'image not attached', 'row-00000', 'row-15999',
            'Successfully edited file', '{"job_id":"fixture"}', 'WAITED', '{"exit_code":124}', '']
        names = []
        for value in results:
            response = provider.complete(self.request(value), on_response_headers=lambda _: None)
            names.append(response['choices'][0]['message']['tool_calls'][0]['function']['name'])
        self.assertEqual(len(names), EXPECTED_LOGICAL)
        self.assertEqual(names[-1], 'complete_task')
        self.assertEqual(provider.calls, EXPECTED_LOGICAL + 1)
        with self.assertRaises(ValueError):
            provider.complete(self.request('extra'), on_response_headers=lambda _: None)

    def test_fixture_does_not_accept_fake_success_for_media_tail_or_timeout(self):
        for calls, bad in [(3, 'silently omitted'), (5, 'wrong tail'), (9, '{"exit_code":0}')]:
            provider = SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
            provider.calls = calls
            with self.assertRaises(AssertionError):
                provider.complete(self.request(bad), on_response_headers=lambda _: None)

    def test_case_matrix_covers_four_variants_cancellation_and_stop(self):
        self.assertEqual(len(PROBE_CASES), 6)
        for condition, parent, mode in PROBE_CASES:
            checks = probe_checks(mode)
            self.assertIn('runtime_archive_bound', checks)
            self.assertIn('model_revoked', checks)
        self.assertIn('cancelled_setup_evidence', probe_checks('cancel_setup'))
        self.assertIn('no_next_dispatch', probe_checks('boundary_stop'))
        with self.assertRaises(ValueError): probe_checks('paid')

    def test_media_notice_can_follow_the_tool_acknowledgement(self):
        provider = SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        provider.calls = 3
        request = self.request('Image read; attachment follows.')
        request['messages'].append({'role': 'user', 'content': 'image not attached'})
        response = provider.complete(request, on_response_headers=lambda _: None)
        self.assertEqual(response['choices'][0]['message']['tool_calls'][0]['function']['name'], 'read_file')

    def test_fixture_creation_command_is_not_an_attached_file_observation(self):
        request = self.request('image not attached')
        request['messages'].insert(0, {'role': 'assistant', 'content': None,
            'tool_calls': [{'function': {'name': 'execute', 'arguments': json.dumps({'command': PREPARE})}}]})
        provider = SyntheticProvider('synthetic-not-a-real-key', clock=Clock())
        provider.calls = 3
        provider.complete(request, on_response_headers=lambda _: None)
        provider.calls = 3
        request['messages'][-1]['content'] += PNG
        with self.assertRaises(AssertionError):
            provider.complete(request, on_response_headers=lambda _: None)

    def test_native_fixture_source_is_not_a_task_solution_or_real_provider(self):
        root = Path(__file__).parent
        source = (root / 'portable_custom_probe.py').read_text()
        self.assertIn("gateway['network_mode'] = 'none'", source)
        self.assertIn('client_factory=SyntheticProvider', source)
        self.assertNotIn('OPENROUTER_API_KEY=' + 'sk-', source)
        self.assertIn('sleep 110 &', PREPARE)


if __name__ == '__main__': unittest.main()

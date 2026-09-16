from pathlib import Path
from decimal import Decimal
import unittest
from unittest.mock import patch

from trial_estimator import estimate_details
from setup_probe import full_context_bound


class EstimatorTests(unittest.TestCase):
    def request(self, **kwargs):
        return {'messages': [{'role': 'user', 'content': 'café 東京'}], 'max_tokens': 64, **kwargs}

    @patch('trial_estimator.token_candidates', return_value={'test': {'rendered_utf8_bytes': 200}})
    def test_margin_and_hard_bound(self, _):
        result = estimate_details(Path('.'), self.request())
        self.assertEqual(result['estimated_input_tokens'], 2 * (result['wire_bytes'] + 200) + 8192)
        self.assertLess(Decimal(result['estimated_usd']), full_context_bound(self.request()))
        self.assertFalse(result['provider_guaranteed'])

    @patch('trial_estimator.token_candidates', return_value={'test': {'rendered_utf8_bytes': 2000000}})
    def test_saturates_at_full_context_bound(self, _):
        result = estimate_details(Path('.'), self.request())
        self.assertEqual(Decimal(result['estimated_usd']), full_context_bound(self.request()))

    def test_unsupported_message_and_server_tool_fail_closed(self):
        requests = [self.request(messages=[{'role': 'user', 'content': [], 'images': []}]),
            self.request(messages=[{'role': 'assistant', 'reasoning_details': []}]),
            self.request(tools=[{'type': 'web_search'}])]
        for request in requests:
            with self.assertRaises(ValueError):
                estimate_details(Path('.'), request)


if __name__ == '__main__':
    unittest.main()

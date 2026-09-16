from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from model_protocol import ModelSettings, freeze_protocol, read_protocol
from gateway_core import Gateway, Trial, token_digest
from gateway_policy import MODEL


class ProtocolTests(unittest.TestCase):
    def setUp(self):
        self.settings = ModelSettings(8192, 1., 'high')
        self.request = {'model': MODEL, 'max_tokens': 8192, 'temperature': 1.,
                        'reasoning': {'effort': 'high'},
                        'messages': [{'role': 'user', 'content': 'synthetic'}]}

    def test_uniform_nucleus_default_preserves_messages_and_original(self):
        result = self.settings.enforce(self.request)
        self.assertEqual(result['top_p'], 1.)
        self.assertEqual(result['messages'], self.request['messages'])
        self.assertNotIn('top_p', self.request)

    def test_drift_rejected_before_billing_or_provider(self):
        ledger, upstream, balance = Mock(), Mock(), Mock()
        gateway = Gateway(ledger, Trial('fixture', 'development', token_digest('token')),
                          balance, Mock(), upstream, Mock(), request_policy=self.settings.enforce)
        for change in [{'temperature': 0.}, {'temperature': True}, {'reasoning': {'effort': 'low'}},
                       {'max_tokens': 8193}, {'top_p': .95}, {'seed': 42}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                gateway.complete('token', dict(self.request, **change))
        ledger.reserve.assert_not_called()
        balance.assert_not_called()
        upstream.assert_not_called()

    def test_missing_reasoning_is_not_silently_accepted(self):
        request = dict(self.request)
        del request['reasoning']
        with self.assertRaises(ValueError): self.settings.enforce(request)

    def test_freeze_is_idempotent_but_cannot_change(self):
        with tempfile.TemporaryDirectory() as directory:
            first = freeze_protocol(directory, self.settings)
            self.assertEqual(first, freeze_protocol(directory, self.settings))
            with self.assertRaises(ValueError): freeze_protocol(directory, ModelSettings(4096, 1., 'high'))
            self.assertEqual(read_protocol(directory), self.settings)
            self.assertEqual((Path(directory) / 'model-protocol.json').stat().st_mode & 0o777, 0o600)

    def test_missing_protocol_is_not_created_by_reader(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError): read_protocol(directory)
            self.assertFalse(list(Path(directory).iterdir()))

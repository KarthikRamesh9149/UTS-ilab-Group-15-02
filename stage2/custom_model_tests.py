"""Actual LangChain client -> gateway -> synthetic ledger/provider only."""
import os
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
from pathlib import Path
import tempfile
import threading
import unittest

from budget_ledger import Ledger
from custom_model import gateway_model
from gateway_core import Gateway, Trial, token_digest
from gateway_http import make_server
from gateway_policy import MODEL


class CustomModelTests(unittest.TestCase):
    def test_rejects_nonlocal_urls_and_unbounded_output(self):
        for url in ['https://openrouter.ai/api/v1', 'http://localhost:123/v1',
                    'http://127.0.0.1:123/v1?x=y', 'http://user@127.0.0.1:123/v1']:
            with self.assertRaises(ValueError):
                gateway_model(url, 'fixture', max_output_tokens=64)
        for value in [None, True, 0, 384001]:
            with self.assertRaises(ValueError):
                gateway_model('http://127.0.0.1:123/v1', 'fixture', max_output_tokens=value)

    def test_native_client_sends_one_admitted_request(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, ledgers = [], []
            def upstream(request):
                calls.append(request)
                return {'id': 'synthetic-custom-client', 'object': 'chat.completion', 'created': 1,
                    'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
                        'message': {'role': 'assistant', 'content': 'UTS_CUSTOM_CLIENT_OK'}}],
                    'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8, 'cost': '.001'}}
            def factory():
                ledger = Ledger(Path(directory) / 'synthetic.sqlite', '.1', '.055')
                ledgers.append(ledger)
                return Gateway(ledger, Trial('custom-client', 'development', token_digest('synthetic')),
                    lambda: '25', lambda req: '.01', upstream,
                    lambda identifier: {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.001'})
            server = make_server(factory)
            def serve():
                try:
                    server.serve_forever()
                finally:
                    for ledger in ledgers:
                        ledger.close()
            thread = threading.Thread(target=serve)
            thread.start()
            try:
                model = gateway_model('http://127.0.0.1:' + str(server.server_address[1]) + '/v1',
                                      'synthetic', max_output_tokens=64)
                result = model.invoke('Synthetic fixture only')
                self.assertEqual(result.content, 'UTS_CUSTOM_CLIENT_OK')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]['model'], MODEL)
                self.assertEqual(calls[0]['max_tokens'], 64)
                self.assertEqual(calls[0]['provider']['only'], ['deepinfra/fp8'])
                self.assertFalse(calls[0]['provider']['allow_fallbacks'])
                self.assertEqual(model.max_retries, 0)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()

"""Real installed Harbor client -> real local HTTP -> gateway -> scripted model.

No upstream model traffic. This is client integration, not an agent/task run.
"""
import os
os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
from pathlib import Path
from decimal import Decimal
import tempfile
import threading
import unittest

from harbor.llms.lite_llm import LiteLLM
from budget_ledger import Ledger
from gateway_core import Gateway, Trial, token_digest
from gateway_http import make_server
from gateway_policy import MODEL


class HarborGatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_client_uses_local_gateway_once(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            ledgers = []
            def upstream(request):
                calls.append(request)
                return {'id':'synthetic-harbor', 'object':'chat.completion', 'created':1,
                        'model':MODEL, 'choices':[{'index':0,'finish_reason':'stop',
                        'message':{'role':'assistant','content':'UTS_FIXTURE'}}],
                        'usage':{'prompt_tokens':5,'completion_tokens':3,'total_tokens':8,'cost':Decimal('.001')}}
            def factory():
                ledger = Ledger(Path(directory)/'ledger.sqlite', '.1', '.055')
                ledgers.append(ledger)
                return Gateway(ledger, Trial('harbor-client','development',token_digest('fixture')),
                    lambda:'25', lambda req:'.01', upstream,
                    lambda identifier:{'id':identifier,'model':MODEL,'provider_name':'DeepInfra','total_cost':'.001'})
            server = make_server(factory)
            def serve():
                try:
                    server.serve_forever()
                finally:
                    for ledger in ledgers:
                        ledger.close()
            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            try:
                client = LiteLLM('openai/' + MODEL, temperature=0,
                    api_base='http://127.0.0.1:' + str(server.server_address[1]) + '/v1',
                    api_key='fixture', num_retries=0, timeout=5,
                    model_info={'max_input_tokens':1048576,'max_output_tokens':64,
                                'input_cost_per_token':.00000006,'output_cost_per_token':.00000018,
                                'cache_read_input_token_cost':.000000015,
                                'cache_creation_input_token_cost':0})
                # Bypass only Harbor's outer retry decorator for this fixture;
                # the actual native client body and HTTP serialization run.
                response = await client.call.__wrapped__(client, 'Synthetic client fixture', max_tokens=64)
                self.assertEqual(response.content, 'UTS_FIXTURE')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]['model'], MODEL)
                self.assertFalse(calls[0]['provider']['allow_fallbacks'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

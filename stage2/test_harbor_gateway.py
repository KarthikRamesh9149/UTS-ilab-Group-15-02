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
from native_agents import ModelSettings, agent_factory
from types import SimpleNamespace


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
                base = 'http://127.0.0.1:' + str(server.server_address[1]) + '/v1'
                agent = agent_factory('terminus-2', ModelSettings(64, 1., 'high'))(
                    paths=SimpleNamespace(agent_dir=Path(directory)), host_api_base=base,
                    container_api_base='http://127.0.0.1:8765/v1', trial_token='fixture',
                    agent_timeout_seconds=60, completion_wait_seconds=721.5)
                # Actual production factory and its native client serialization.
                response = await agent._llm.call('Synthetic client fixture', **agent._llm_call_kwargs)
                self.assertEqual(response.content, 'UTS_FIXTURE')
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0]['model'], MODEL)
                self.assertEqual(calls[0]['temperature'], 1.)
                self.assertEqual(calls[0]['reasoning'], {'effort': 'high'})
                self.assertFalse(calls[0]['provider']['allow_fallbacks'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)

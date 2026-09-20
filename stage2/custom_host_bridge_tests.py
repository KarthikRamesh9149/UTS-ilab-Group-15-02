"""Native custom client -> host HTTP bridge; Docker RPC is synthetic here."""
import json
import os
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest

os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
from custom_model import gateway_model
from gateway_policy import MODEL
from host_model_bridge import HostModelBridge
from custom_harbor_agent import CustomHarborAgent
from custom_backend_tests import FakeEnvironment
from harbor.models.agent.context import AgentContext


class NativeHostBridgeTests(unittest.TestCase):
    def test_native_client_preserves_request_through_host_bridge(self):
        calls = []
        def rpc(command, **kwargs):
            calls.append(json.loads(kwargs['input']))
            body = {'id': 'synthetic-native-bridge', 'model': MODEL,
                'object': 'chat.completion', 'created': 1,
                'choices': [{'index': 0, 'finish_reason': 'stop',
                    'message': {'role': 'assistant', 'content': 'UTS_BRIDGE_OK'}}],
                'usage': {'prompt_tokens': 5, 'completion_tokens': 3, 'total_tokens': 8}}
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 200, 'body': body}).encode())
        with HostModelBridge('a' * 64, completion_wait_seconds=721.5) as bridge:
            bridge.gateway.run = rpc
            model = gateway_model(bridge.base_url, 'synthetic-token', max_output_tokens=64,
                                  completion_wait_seconds=721.5)
            response = model.invoke('Synthetic transport fixture')
            self.assertEqual(response.content, 'UTS_BRIDGE_OK')
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0]['token'], 'synthetic-token')
            self.assertEqual(calls[0]['payload']['model'], MODEL)
            self.assertEqual(calls[0]['payload']['messages'][0]['content'], 'Synthetic transport fixture')
        self.assertTrue(bridge.gateway.revoked)
        self.assertFalse(bridge.thread.is_alive())


class NativeGraphBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_graph_uses_nonstreaming_native_client(self):
        calls = []
        def rpc(command, **kwargs):
            envelope = json.loads(kwargs['input'])
            calls.append(envelope)
            self.assertFalse(envelope['payload'].get('stream', False))
            names = {t['function']['name'] for t in envelope['payload']['tools']}
            self.assertIn('complete_task', names)
            self.assertNotIn('task', names)
            body = {'id': 'synthetic-native-graph', 'model': MODEL,
                'object': 'chat.completion', 'created': 1,
                'choices': [{'index': 0, 'finish_reason': 'tool_calls', 'message': {
                    'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'completion-1', 'type': 'function', 'function': {
                            'name': 'complete_task', 'arguments': json.dumps({'summary': 'Synthetic fixture complete'})}}]}}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 10, 'total_tokens': 20}}
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': 200, 'body': body}).encode())
        with tempfile.TemporaryDirectory() as directory, HostModelBridge('b' * 64, completion_wait_seconds=721.5) as bridge:
            bridge.gateway.run = rpc
            agent = CustomHarborAgent(Path(directory), condition='C0', api_base=bridge.base_url,
                trial_token='synthetic-token', max_output_tokens=128, max_model_calls=2,
                trial_timeout_seconds=15, completion_wait_seconds=721.5)
            context = AgentContext()
            await agent.run('Synthetic fixture, no task data', FakeEnvironment(), context)
            self.assertEqual(len(calls), 1)
            self.assertEqual(context.metadata['custom_outcome']['outcome'], 'agent_reported_complete')


if __name__ == '__main__':
    unittest.main()

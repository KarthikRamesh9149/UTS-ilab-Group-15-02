import json
import subprocess
from types import SimpleNamespace
import unittest
from host_model_bridge import ContainerGateway
from budget_ledger import BudgetExceeded
from gateway_core import GatewayError
from container_gateway_rpc import forward


class HostBridgeTests(unittest.TestCase):
    def make(self, status=200, failure=False):
        calls = []
        def run(command, **kwargs):
            calls.append((command, kwargs))
            if failure:
                raise subprocess.TimeoutExpired(command, 120)
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': status, 'body': {'id': 'fixture'}}).encode())
        return ContainerGateway('a'*64, run=run), calls

    def test_fixed_route_no_shell_or_token_in_arguments(self):
        gateway, calls = self.make()
        self.assertEqual(gateway.complete('synthetic-secret', {'messages': []}), {'id': 'fixture'})
        command, options = calls[0]
        self.assertEqual(command, ['docker', 'exec', '-i', 'a'*64, 'python', '/study/stage2/container_gateway_rpc.py'])
        self.assertNotIn('synthetic-secret', ' '.join(command))
        self.assertNotIn('shell', options)
        self.assertEqual(json.loads(options['input'])['token'], 'synthetic-secret')

    def test_timeout_is_not_retried(self):
        gateway, calls = self.make(failure=True)
        with self.assertRaises(GatewayError):
            gateway.complete('token', {})
        self.assertEqual(len(calls), 1)

    def test_budget_error_is_preserved(self):
        gateway, _ = self.make(status=402)
        with self.assertRaises(BudgetExceeded):
            gateway.complete('token', {})

    def test_revocation_and_invalid_id(self):
        gateway, calls = self.make()
        gateway.revoked = True
        with self.assertRaises(GatewayError):
            gateway.complete('token', {})
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            ContainerGateway('--privileged')

    def test_container_rpc_closes_socket_and_keeps_status(self):
        calls = []
        class Connection:
            def __init__(self, path): calls.append(path)
            def request(self, *args): calls.append(args)
            def getresponse(self): return SimpleNamespace(status=402, read=lambda size: b'{"error":{}}')
            def close(self): calls.append('closed')
        self.assertEqual(forward({'token': 'fixture', 'payload': {}}, Connection)['status'], 402)
        self.assertEqual(calls[0], '/socket/private/model.sock')
        self.assertEqual(calls[1][:2], ('POST', '/v1/chat/completions'))
        self.assertEqual(calls[-1], 'closed')

    def test_container_rpc_rejects_header_injection(self):
        with self.assertRaises(ValueError):
            forward({'token': 'bad\r\nHeader:x', 'payload': {}})

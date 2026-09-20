import json
import subprocess
import http.client
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from host_model_bridge import ContainerGateway, HostModelBridge
from budget_ledger import BudgetExceeded
from gateway_core import GatewayError
from container_gateway_rpc import forward
from gateway_policy import MODEL, prepare_request


class HostBridgeTests(unittest.TestCase):
    def make(self, status=200, failure=False):
        calls = []
        def run(command, **kwargs):
            calls.append((command, kwargs))
            if failure:
                raise subprocess.TimeoutExpired(command, 120)
            return SimpleNamespace(returncode=0, stdout=json.dumps({'status': status, 'body': {'id': 'fixture'}}).encode())
        return ContainerGateway('a'*64, completion_wait_seconds=960, run=run), calls

    def test_fixed_route_no_shell_or_token_in_arguments(self):
        gateway, calls = self.make()
        self.assertEqual(gateway.complete('synthetic-secret', {'messages': []}), {'id': 'fixture'})
        command, options = calls[0]
        self.assertEqual(command, ['docker', 'exec', '-i', 'a'*64, 'python',
            '/study/stage2/container_gateway_rpc.py', '--completion-wait-seconds', '960.0'])
        self.assertEqual(options['timeout'], 960.)
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
            ContainerGateway('--privileged', completion_wait_seconds=960)

    def test_container_rpc_closes_socket_and_keeps_status(self):
        calls = []
        class Connection:
            def __init__(self, path, *, completion_wait_seconds): calls.append((path, completion_wait_seconds))
            def request(self, *args): calls.append(args)
            def getresponse(self): return SimpleNamespace(status=402, read=lambda size: b'{"error":{}}')
            def close(self): calls.append('closed')
        self.assertEqual(forward({'token': 'fixture', 'payload': {}}, Connection,
                                 completion_wait_seconds=960)['status'], 402)
        self.assertEqual(calls[0], ('/socket/private/model.sock', 960.))
        self.assertEqual(calls[1][:2], ('POST', '/v1/chat/completions'))
        self.assertEqual(calls[-1], 'closed')

    def test_container_rpc_rejects_header_injection(self):
        with self.assertRaises(ValueError):
            forward({'token': 'bad\r\nHeader:x', 'payload': {}}, completion_wait_seconds=960)

    def test_fake_long_completion_dispatches_once_without_short_transport_cap(self):
        calls = []
        class Connection:
            def __init__(self, path, *, completion_wait_seconds):
                self.wait = completion_wait_seconds
            def request(self, *args): calls.append(args)
            def getresponse(self):
                # Simulated elapsed completion time, without a real paid call
                # or a slow wall-clock test. The old 90/120s caps fail this.
                if self.wait < 121:
                    raise TimeoutError('synthetic completion needs 121 seconds')
                return SimpleNamespace(status=200, read=lambda size: b'{"id":"long-fixture"}')
            def close(self): pass
        def run(command, **kwargs):
            if kwargs['timeout'] < 121:
                raise subprocess.TimeoutExpired(command, kwargs['timeout'])
            supplied = float(command[command.index('--completion-wait-seconds') + 1])
            response = forward(json.loads(kwargs['input']), Connection, completion_wait_seconds=supplied)
            return SimpleNamespace(returncode=0, stdout=json.dumps(response).encode())
        gateway = ContainerGateway('a'*64, completion_wait_seconds=960, run=run)
        self.assertEqual(gateway.complete('fixture', {'completion_wait_seconds': .001}), {'id': 'long-fixture'})
        self.assertEqual(len(calls), 1)

    def test_wait_validation_and_extra_envelope_cannot_override(self):
        for value in (None, True, '960', 0, -1, float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    ContainerGateway('a'*64, completion_wait_seconds=value)
                with self.assertRaises(ValueError):
                    forward({'token': 'fixture', 'payload': {}}, completion_wait_seconds=value)
        with self.assertRaises(ValueError):
            forward({'token': 'fixture', 'payload': {}, 'completion_wait_seconds': 1},
                    completion_wait_seconds=960)
        # The authority-bearing provider request boundary rejects this field;
        # transport forwarding alone never interprets it as configuration.
        with self.assertRaises(ValueError):
            prepare_request({'model': MODEL, 'messages': [{'role': 'user', 'content': 'synthetic'}],
                             'max_tokens': 64, 'completion_wait_seconds': 1})

    def test_shutdown_is_bounded_and_never_claims_stuck_handler_completed(self):
        bridge = HostModelBridge('a'*64, completion_wait_seconds=960)
        entered, release = threading.Event(), threading.Event()
        def complete(token, payload):
            entered.set()
            release.wait(3)
            return {'id': 'fixture'}
        bridge.gateway.complete = complete
        def request():
            client = http.client.HTTPConnection(*bridge.server.server_address, timeout=3)
            try:
                client.request('POST', '/v1/chat/completions', '{}',
                               {'Authorization': 'Bearer fixture'})
                client.getresponse().read()
            finally:
                client.close()
        bridge.__enter__()
        requester = threading.Thread(target=request, daemon=True)
        requester.start()
        try:
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            with patch('host_model_bridge.SHUTDOWN_WAIT_SECONDS', .05):
                with self.assertRaisesRegex(RuntimeError, 'shutdown pending'):
                    bridge.__exit__()
            self.assertLess(time.monotonic() - start, 1)
            self.assertFalse(bridge.closed)
            self.assertTrue(bridge.thread.is_alive())
            self.assertTrue(bridge.gateway.revoked)
        finally:
            release.set()
            requester.join(timeout=3)
            bridge.__exit__()
        self.assertTrue(bridge.closed)
        self.assertFalse(bridge.thread.is_alive())

    def test_unstarted_bridge_closes_without_waiting_for_serve_forever(self):
        bridge = HostModelBridge('a'*64, completion_wait_seconds=960)
        bridge.__exit__()
        self.assertTrue(bridge.closed)

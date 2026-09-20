import http.client
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from container_model_relay import make_relay, UnixConnection
from gateway_core import GatewayError
from gateway_http import make_unix_server


class RelayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='uts-', dir='/tmp')
        self.path = Path(self.temp.name) / 'model.sock'
        self.calls = []
        outer = self
        class Stub:
            def complete(self, token, payload):
                if token != 'fixture':
                    raise GatewayError('secret-canary')
                outer.calls.append(payload)
                return {'id': 'synthetic', 'choices': [{'message': {'content': 'OK'}}]}
        self.gateway = make_unix_server(Stub, self.path)
        self.relay = make_relay(self.path, completion_wait_seconds=960)
        self.threads = []
        for server in (self.gateway, self.relay):
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.threads.append(thread)

    def tearDown(self):
        for server in (self.relay, self.gateway):
            server.shutdown()
            server.server_close()
        for thread in self.threads:
            thread.join(timeout=3)
        self.temp.cleanup()

    def call(self, token='fixture', path='/v1/chat/completions', headers=None, payload=None):
        client = http.client.HTTPConnection(*self.relay.server_address, timeout=3)
        try:
            client.request('POST', path, json.dumps({} if payload is None else payload),
                           headers if headers is not None else {'Authorization': 'Bearer ' + token})
            response = client.getresponse()
            return response.status, response.read()
        finally:
            client.close()

    def test_roundtrip_once_and_private_endpoints(self):
        status, body = self.call()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['id'], 'synthetic')
        self.assertEqual(self.calls, [{}])
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.relay.server_address[0], '127.0.0.1')

    def test_auth_and_route_rejected_without_dispatch(self):
        self.assertEqual(self.call(token='wrong')[0], 403)
        self.assertEqual(self.call(headers={})[0], 401)
        self.assertEqual(self.call(path='/credits')[0], 404)
        self.assertFalse(self.calls)

    def test_failure_sanitised_and_not_retried(self):
        self.relay.socket_path = '/nonexistent/secret-canary.sock'
        status, body = self.call()
        self.assertEqual(status, 502)
        self.assertNotIn(b'secret-canary', body)
        self.assertFalse(self.calls)

    def test_no_socket_replacement_or_public_parent(self):
        with self.assertRaises(ValueError):
            make_unix_server(lambda: None, self.path)
        os.chmod(self.temp.name, 0o755)
        try:
            with self.assertRaises(ValueError):
                make_unix_server(lambda: None, Path(self.temp.name) / 'other.sock')
        finally:
            os.chmod(self.temp.name, 0o700)

    def test_transfer_encoding_refused(self):
        status, _ = self.call(headers={'Authorization': 'Bearer fixture', 'Transfer-Encoding': 'chunked'})
        self.assertEqual(status, 400)
        self.assertFalse(self.calls)

    def test_trusted_wait_reaches_socket_and_payload_cannot_override(self):
        with patch('container_model_relay.UnixConnection', wraps=UnixConnection) as connection:
            self.assertEqual(self.call(payload={'completion_wait_seconds': .001})[0], 200)
            connection.assert_called_once_with(str(self.path), completion_wait_seconds=960.)
        self.assertEqual(self.relay.completion_wait_seconds, 960.)


class RelayWaitValidationTests(unittest.TestCase):
    def test_socket_timeout_and_invalid_waits(self):
        connection = UnixConnection('/fixture', completion_wait_seconds=960)
        self.assertEqual(connection.timeout, 960.)
        connection.close()
        for value in (None, True, '960', 0, -1, float('nan'), float('inf')):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    UnixConnection('/fixture', completion_wait_seconds=value)
                with self.assertRaises(ValueError):
                    make_relay('/fixture', completion_wait_seconds=value)

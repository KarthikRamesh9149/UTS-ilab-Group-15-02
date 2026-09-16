import http.client
import json
import threading
import unittest

from budget_ledger import BudgetExceeded
from gateway_http import make_server


class HTTPTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        outer = self
        class Stub:
            def complete(self, token, payload):
                outer.calls.append((token, payload))
                if payload.get('blocked'):
                    raise BudgetExceeded('sensitive details')
                return {'id':'synthetic', 'choices':[{'message':{'role':'assistant','content':'fixture'}}]}
        self.server = make_server(Stub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=3)

    def call(self, path='/v1/chat/completions', auth=True, payload=None):
        client = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        headers = {'Authorization':'Bearer fixture'} if auth else {}
        try:
            client.request('POST', path, json.dumps(payload or {}), headers)
            response = client.getresponse()
            return response.status, json.loads(response.read())
        finally:
            client.close()

    def test_real_http_roundtrip(self):
        status, body = self.call(payload={'messages':[]})
        self.assertEqual(status, 200)
        self.assertEqual(body['id'], 'synthetic')
        self.assertEqual(self.calls, [('fixture', {'messages':[]})])
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_auth_and_routes(self):
        self.assertEqual(self.call(auth=False)[0], 401)
        self.assertEqual(self.call(path='/credits')[0], 404)
        self.assertFalse(self.calls)

    def test_budget_status_does_not_leak_details(self):
        status, body = self.call(payload={'blocked':True})
        self.assertEqual(status, 402)
        self.assertNotIn('sensitive details', json.dumps(body))

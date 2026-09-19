from decimal import Decimal
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from openrouter_transport import NoRedirect, OpenRouter, TransportError, load_key, error_diagnostic


class Opener:
    def __init__(self, body):
        self.body = body
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        return BytesIO(self.body)


class TransportTests(unittest.TestCase):
    def test_exact_credit_arithmetic(self):
        opener = Opener(b'{"data":{"total_credits":150,"total_usage":124.734823195}}')
        self.assertEqual(OpenRouter('fixture', opener=opener).balance(), Decimal('25.265176805'))
        self.assertEqual(len(opener.requests), 1)
        self.assertEqual(opener.requests[0].full_url, 'https://openrouter.ai/api/v1/credits')

    def test_generation_disabled_before_network(self):
        opener = Opener(b'{}')
        with self.assertRaises(TransportError):
            OpenRouter('fixture', opener=opener).complete({})
        self.assertFalse(opener.requests)

    def test_redirect_is_refused(self):
        with self.assertRaises(TransportError):
            NoRedirect().redirect_request(None, None, 302, '', {}, 'https://other.example')

    def test_exception_does_not_echo_key(self):
        class Failing:
            def open(self, request, timeout):
                raise HTTPError(request.full_url, 401, 'secret-canary', {}, None)
        with self.assertRaises(TransportError) as caught:
            OpenRouter('secret-canary', opener=Failing()).balance()
        self.assertNotIn('secret-canary', str(caught.exception))

    def test_key_file_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('OPENROUTER_API_KEY=fixture\n')
            path.chmod(0o600)
            self.assertEqual(load_key(path), 'fixture')
            path.chmod(0o644)
            with self.assertRaises(TransportError):
                load_key(path)

    def test_error_metadata_retains_id_and_type_but_never_raw_prose(self):
        error = {'id': 'gen-known-id', 'error': {'code': 429, 'message': 'secret-canary',
                 'metadata': {'raw': 'secret-canary', 'error_type': 'rate_limit_exceeded'}}}
        import json
        opener = Opener(json.dumps(error).encode())
        with self.assertRaises(TransportError) as caught:
            OpenRouter('fixture', generation_enabled=True, opener=opener).complete({})
        diagnostic = caught.exception.diagnostic
        self.assertEqual(diagnostic['generation_id'], 'gen-known-id')
        self.assertEqual(diagnostic['error_type'], 'rate_limit_exceeded')
        self.assertEqual(diagnostic['billing_outcome'], 'unknown_reservation_retained')
        self.assertNotIn('secret-canary', json.dumps(diagnostic))
        self.assertEqual(len(opener.requests), 1)

    def test_http_error_preserves_safe_headers_without_retry(self):
        from email.message import Message
        headers = Message()
        headers['X-Generation-Id'] = 'gen-from-header'
        headers['X-Request-Id'] = 'req-from-header'
        class Failing:
            calls = 0
            def open(self, request, timeout):
                self.calls += 1
                raise HTTPError(request.full_url, 502, 'secret-canary', headers,
                                BytesIO(b'{"error":{"metadata":{"error_type":"provider_unavailable"}}}'))
        opener = Failing()
        with self.assertRaises(TransportError) as caught:
            OpenRouter('secret-canary', generation_enabled=True, opener=opener).complete({})
        self.assertEqual(caught.exception.diagnostic['generation_id'], 'gen-from-header')
        self.assertEqual(caught.exception.diagnostic['http_status'], 502)
        self.assertEqual(caught.exception.diagnostic['request_id'], 'req-from-header')
        self.assertEqual(opener.calls, 1)
        self.assertNotIn('secret-canary', str(caught.exception.diagnostic))

    def test_untrusted_error_fields_cannot_become_diagnostics(self):
        result = error_diagnostic({'id': 'gen-key value', 'error': {'code': 'secret-canary',
            'metadata': {'error_type': 'secret-canary', 'raw': 'secret-canary'}}},
            status=True, headers={'X-Generation-Id': 'sk-or-secret-canary'})
        self.assertIsNone(result['http_status'])
        self.assertIsNone(result['error_code'])
        self.assertIsNone(result['error_type'])
        self.assertIsNone(result['generation_id'])
        self.assertNotIn('secret-canary', str(result))
        self.assertIsNone(error_diagnostic({'error': {'metadata': {'error_type': []}}})['error_type'])

    def test_network_failure_stays_ambiguous(self):
        class Failing:
            def open(self, request, timeout): raise TimeoutError('secret-canary')
        with self.assertRaises(TransportError) as caught:
            OpenRouter('fixture', generation_enabled=True, opener=Failing()).complete({})
        self.assertIsNone(caught.exception.diagnostic)
        self.assertNotIn('secret-canary', str(caught.exception))

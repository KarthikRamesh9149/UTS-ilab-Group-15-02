from decimal import Decimal
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from openrouter_transport import NoRedirect, OpenRouter, TransportError, load_key


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

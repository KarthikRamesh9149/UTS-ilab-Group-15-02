from decimal import Decimal
from email.message import Message
from http.client import IncompleteRead
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import HTTPError

from openrouter_transport import NoRedirect, OpenRouter, TransportError, load_key, error_diagnostic


class Opener:
    def __init__(self, body):
        self.body = body
        self.requests = []
        self.timeouts = []

    def open(self, request, timeout):
        self.requests.append(request)
        self.timeouts.append(timeout)
        return BytesIO(self.body)


class ObservedResponse(BytesIO):
    def __init__(self, body=b'{"id":"gen-fixture"}', *, headers=None, status=200,
                 events=None, read_error=None):
        super().__init__(body)
        self.headers = headers if headers is not None else {}
        self.status = status
        self.events = events if events is not None else []
        self.read_error = read_error
        self.read_calls = 0

    def read(self, size=-1):
        self.read_calls += 1
        self.events.append('read')
        if self.read_error is not None:
            raise self.read_error
        return super().read(size)


class ResponseOpener:
    def __init__(self, response, *, http_error=False):
        self.response = response
        self.http_error = http_error
        self.requests = []

    def open(self, request, timeout):
        self.requests.append(request)
        if self.http_error:
            raise HTTPError(request.full_url, self.response.status, 'secret-canary',
                            self.response.headers, self.response)
        return self.response


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

    def test_success_headers_are_observed_before_body_and_response_is_closed(self):
        events, retained = [], []
        response = ObservedResponse(headers={
            'X-Generation-Id': 'gen-fixture', 'X-Request-Id': 'req-fixture',
            'Authorization': 'secret-canary', 'X-Unrelated': 'secret-canary'}, events=events)
        opener = ResponseOpener(response)
        def observe(diagnostic):
            self.assertEqual(response.read_calls, 0)
            self.assertFalse(response.closed)
            events.append('headers')
            retained.append(diagnostic)
        result = OpenRouter('secret-canary', generation_enabled=True, opener=opener).complete(
            {}, on_response_headers=observe)
        self.assertEqual(result['id'], 'gen-fixture')
        self.assertEqual(events, ['headers', 'read'])
        self.assertEqual(retained[0]['generation_id'], 'gen-fixture')
        self.assertEqual(retained[0]['request_id'], 'req-fixture')
        self.assertEqual(retained[0]['http_status'], 200)
        self.assertEqual(retained[0]['billing_outcome'], 'unknown_reservation_retained')
        self.assertNotIn('secret-canary', json.dumps(retained))
        self.assertEqual(len(opener.requests), 1)
        self.assertTrue(response.closed)

    def test_http_error_headers_are_observed_before_error_body(self):
        events, retained = [], []
        response = ObservedResponse(b'{"error":{"message":"secret-canary"}}',
            headers={'X-Generation-Id': 'gen-error', 'X-Request-Id': 'req-error'},
            status=502, events=events)
        opener = ResponseOpener(response, http_error=True)
        def observe(diagnostic):
            self.assertEqual(response.read_calls, 0)
            self.assertFalse(response.closed)
            events.append('headers')
            retained.append(diagnostic)
        with self.assertRaises(TransportError) as caught:
            OpenRouter('secret-canary', generation_enabled=True, opener=opener).complete(
                {}, on_response_headers=observe)
        self.assertEqual(events, ['headers', 'read'])
        self.assertEqual(retained[0]['generation_id'], 'gen-error')
        self.assertEqual(retained[0]['http_status'], 502)
        self.assertEqual(caught.exception.diagnostic, retained[0])
        self.assertNotIn('secret-canary', json.dumps(retained))
        self.assertEqual(len(opener.requests), 1)
        self.assertTrue(response.closed)

    def test_missing_or_invalid_header_ids_stay_unknown(self):
        for headers in ({}, {'X-Generation-Id': 'sk-or-secret-canary',
                             'X-Request-Id': 'secret-canary'},
                        {'X-Generation-Id': 'gen-key value', 'X-Request-Id': 'req-\ncanary'},
                        {'X-Generation-Id': 'gen-' + 'a' * 251, 'X-Request-Id': 'req-'},
                        {'X-Generation-Id': None, 'X-Request-Id': 123}):
            with self.subTest(headers=headers):
                retained = []
                response = ObservedResponse(headers=headers)
                opener = ResponseOpener(response)
                OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                    {}, on_response_headers=retained.append)
                self.assertEqual(len(retained), 1)
                self.assertIsNone(retained[0]['generation_id'])
                self.assertIsNone(retained[0]['request_id'])
                self.assertNotIn('secret-canary', json.dumps(retained))
                self.assertTrue(response.closed)
                self.assertEqual(len(opener.requests), 1)

    def test_header_lookup_is_case_insensitive_for_http_messages_and_mappings(self):
        message = Message()
        message['x-generation-id'] = 'gen-Mixed_123'
        message['X-rEqUeSt-iD'] = 'req-Mixed_123'
        for headers in (message, {'x-generation-id': 'gen-Mixed_123',
                                 'X-rEqUeSt-iD': 'req-Mixed_123'}):
            with self.subTest(headers=type(headers).__name__):
                retained = []
                opener = ResponseOpener(ObservedResponse(headers=headers))
                OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                    {}, on_response_headers=retained.append)
                self.assertEqual(retained[0]['generation_id'], 'gen-Mixed_123')
                self.assertEqual(retained[0]['request_id'], 'req-Mixed_123')
                self.assertEqual(len(opener.requests), 1)

    def test_conflicting_duplicate_header_ids_stop_before_body_without_retry(self):
        for name, first, second, field in (
                ('X-Generation-Id', 'gen-first', 'gen-second', 'generation_id'),
                ('X-Request-Id', 'req-first', 'req-second', 'request_id')):
            for http_error in (False, True):
                with self.subTest(name=name, http_error=http_error):
                    headers = Message()
                    headers[name] = first
                    headers[name.lower()] = second
                    retained = []
                    response = ObservedResponse(headers=headers, status=502 if http_error else 200)
                    opener = ResponseOpener(response, http_error=http_error)
                    with self.assertRaises(TransportError) as caught:
                        OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                            {}, on_response_headers=retained.append)
                    self.assertEqual(len(retained), 1)
                    self.assertIsNone(retained[0][field])
                    self.assertTrue(retained[0]['identifier_conflict'])
                    self.assertTrue(caught.exception.diagnostic['identifier_conflict'])
                    self.assertEqual(response.read_calls, 0)
                    self.assertTrue(response.closed)
                    self.assertEqual(len(opener.requests), 1)

    def test_identical_duplicate_header_ids_are_unambiguous(self):
        headers = Message()
        for _ in range(2):
            headers['X-Generation-Id'] = 'gen-fixture'
            headers['X-Request-Id'] = 'req-fixture'
        retained = []
        opener = ResponseOpener(ObservedResponse(headers=headers))
        OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
            {}, on_response_headers=retained.append)
        self.assertEqual(retained[0]['generation_id'], 'gen-fixture')
        self.assertEqual(retained[0]['request_id'], 'req-fixture')
        self.assertNotIn('identifier_conflict', retained[0])

    def test_read_failures_preserve_observed_ids_close_response_and_never_retry(self):
        for http_error in (False, True):
            for failure_type in (TimeoutError, IncompleteRead, KeyboardInterrupt):
                with self.subTest(http_error=http_error, failure=failure_type.__name__):
                    failure = (IncompleteRead(b'secret-canary', 100)
                               if failure_type is IncompleteRead else failure_type('secret-canary'))
                    events, retained = [], []
                    response = ObservedResponse(headers={'X-Generation-Id': 'gen-retained',
                        'X-Request-Id': 'req-retained'}, status=502 if http_error else 200,
                        events=events, read_error=failure)
                    opener = ResponseOpener(response, http_error=http_error)
                    def observe(diagnostic):
                        self.assertEqual(response.read_calls, 0)
                        events.append('headers')
                        retained.append(diagnostic)
                    expected = KeyboardInterrupt if failure_type is KeyboardInterrupt else TransportError
                    with self.assertRaises(expected) as caught:
                        OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                            {}, on_response_headers=observe)
                    self.assertEqual(events, ['headers', 'read'])
                    self.assertEqual(retained[0]['generation_id'], 'gen-retained')
                    self.assertEqual(retained[0]['request_id'], 'req-retained')
                    self.assertEqual(retained[0]['billing_outcome'], 'unknown_reservation_retained')
                    self.assertNotIn('secret-canary', json.dumps(retained))
                    if expected is TransportError:
                        self.assertEqual(caught.exception.diagnostic, retained[0])
                        self.assertNotIn('secret-canary', str(caught.exception))
                    self.assertTrue(response.closed)
                    self.assertEqual(len(opener.requests), 1)

    def test_invalid_or_oversized_body_retains_observed_header_ids(self):
        from unittest.mock import patch
        for body, maximum in ((b'not-json-secret-canary', 100), (b'0123456789', 4)):
            with self.subTest(maximum=maximum), patch('openrouter_transport.MAX_RESPONSE', maximum):
                retained = []
                response = ObservedResponse(body, headers={'X-Generation-Id': 'gen-retained'})
                opener = ResponseOpener(response)
                with self.assertRaises(TransportError) as caught:
                    OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                        {}, on_response_headers=retained.append)
                self.assertEqual(caught.exception.diagnostic['generation_id'], 'gen-retained')
                self.assertNotIn('secret-canary', str(caught.exception))
                self.assertTrue(response.closed)
                self.assertEqual(len(opener.requests), 1)

    def test_error_header_body_id_conflict_does_not_choose_a_replacement(self):
        for http_error in (False, True):
            with self.subTest(http_error=http_error):
                retained = []
                response = ObservedResponse(b'{"id":"gen-different-body","error":{"code":502}}',
                    headers={'X-Generation-Id': 'gen-first-header'}, status=502)
                opener = ResponseOpener(response, http_error=http_error)
                with self.assertRaises(TransportError) as caught:
                    OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                        {}, on_response_headers=retained.append)
                self.assertEqual(retained[0]['generation_id'], 'gen-first-header')
                self.assertIsNone(caught.exception.diagnostic['generation_id'])
                self.assertTrue(caught.exception.diagnostic['identifier_conflict'])
                self.assertEqual(len(opener.requests), 1)

    def test_http_error_observer_failure_closes_without_reading_or_retrying(self):
        for failure_type in (RuntimeError, OSError, ValueError, KeyboardInterrupt):
            with self.subTest(failure=failure_type.__name__):
                retained = []
                response = ObservedResponse(headers={'X-Generation-Id': 'gen-retained'}, status=502)
                opener = ResponseOpener(response, http_error=True)
                def observe(diagnostic):
                    retained.append(diagnostic)
                    raise failure_type('observer unavailable')
                expected = TransportError if failure_type in (OSError, ValueError) else failure_type
                with self.assertRaises(expected):
                    OpenRouter('fixture', generation_enabled=True, opener=opener).complete(
                        {}, on_response_headers=observe)
                self.assertEqual(retained[0]['generation_id'], 'gen-retained')
                self.assertEqual(response.read_calls, 0)
                self.assertTrue(response.closed)
                self.assertEqual(len(opener.requests), 1)

    def test_configured_wait_applies_only_to_completion(self):
        body = b'{"data":{"total_credits":25,"total_usage":1,"limit_remaining":24}}'
        for method, args in (('complete', ({},)), ('balance', ()), ('metadata', ()),
                             ('key_status', ()), ('generation', ('gen-fixture',))):
            with self.subTest(method=method):
                opener = Opener(body)
                client = OpenRouter('fixture', generation_enabled=True, opener=opener,
                                    completion_wait_seconds=432.5)
                getattr(client, method)(*args)
                self.assertEqual(opener.timeouts, [432.5 if method == 'complete' else 45])
                self.assertEqual(len(opener.requests), 1)

    def test_invalid_completion_wait_is_rejected_before_network(self):
        for wait in (None, True, False, 0, -1, float('nan'), float('inf'),
                     -float('inf'), '90', Decimal('90'), [], 10 ** 1000):
            with self.subTest(wait=wait):
                opener = Opener(b'{}')
                with self.assertRaises(ValueError):
                    OpenRouter('fixture', generation_enabled=True, opener=opener,
                               completion_wait_seconds=wait)
                self.assertFalse(opener.requests)

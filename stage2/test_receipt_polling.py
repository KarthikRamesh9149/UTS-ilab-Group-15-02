import unittest
from openrouter_transport import TransportError
from receipt_polling import read_receipt


class ReceiptPollingTests(unittest.TestCase):
    def test_delayed_read_reuses_same_generation(self):
        calls = []
        delays = []
        def reader(identifier):
            calls.append(identifier)
            if len(calls) < 3:
                raise TransportError('Not ready')
            return {'id': identifier}
        self.assertEqual(read_receipt(reader, 'same', sleep=delays.append), {'id': 'same'})
        self.assertEqual(calls, ['same'] * 3)
        self.assertEqual(delays, [.5, 1])

    def test_attempt_limit_and_sanitised_error(self):
        calls = []
        def reader(identifier):
            calls.append(identifier)
            raise TransportError('secret-canary')
        with self.assertRaises(TransportError) as caught:
            read_receipt(reader, 'same', max_attempts=3, sleep=lambda _: None)
        self.assertEqual(len(calls), 3)
        self.assertNotIn('secret-canary', str(caught.exception))

    def test_deadline_prevents_new_lookup(self):
        now = [0]
        calls = []
        def sleep(delay):
            now[0] += delay
        def reader(identifier):
            calls.append(identifier)
            raise TransportError()
        with self.assertRaises(TransportError):
            read_receipt(reader, 'same', deadline_seconds=.25, clock=lambda: now[0], sleep=sleep)
        self.assertEqual(len(calls), 1)

    def test_programming_errors_are_not_retried(self):
        def reader(identifier):
            raise ValueError('Malformed receipt')
        with self.assertRaises(ValueError):
            read_receipt(reader, 'same')

"""Synthetic exporter checks; no model calls or Langfuse connection."""
import json
from pathlib import Path
import tempfile
import unittest

from gemini_langfuse import BASE_URL, LocalClient, batches, load_events, trial_payload
from local_trace import observation


def fixture():
    identity = dict(trial_id='gemini-01-fixture', task_id='fixture', harness='C0-NC',
                    protocol_sha256='a' * 64)
    events = [observation(**identity, kind='trial', sequence=0, started_ns=1, ended_ns=100),
              observation(**identity, kind='generation', sequence=1, started_ns=2, ended_ns=3,
                          metrics={'input_tokens': 2, 'output_tokens': 1, 'charged_nanodollars': 5}),
              observation(**identity, kind='verifier', sequence=2, started_ns=90, ended_ns=95,
                          reward=1)]
    row = dict(trial_id=identity['trial_id'], task_id='fixture', classification='pass',
               physical_requests=1, known_spending_usd='0.000000005', unresolved_requests=0, reward=1)
    return events, row


class ExportChecks(unittest.TestCase):
    def test_only_laptop_destination(self):
        with self.assertRaises(ValueError):
            LocalClient(dict(LANGFUSE_BASE_URL='https://example.com',
                             LANGFUSE_PUBLIC_KEY='pk-lf-test', LANGFUSE_SECRET_KEY='sk-lf-test'))

    def test_trial_and_task_match(self):
        events, row = fixture()
        row['task_id'] = 'wrong'
        with self.assertRaises(ValueError):
            trial_payload(events, row)

    def test_no_raw_fields(self):
        events, row = fixture()
        events[0]['input'] = 'raw prompt'
        with self.assertRaises(ValueError):
            trial_payload(events, row)

    def test_batches_preserve_stable_ids(self):
        events, row = fixture()
        body = trial_payload(events, row)
        chunks = list(batches(body, size=2))
        ids = [span['spanId'] for chunk in chunks
               for span in chunk['resourceSpans'][0]['scopeSpans'][0]['spans']]
        self.assertEqual(ids, [e['event_id'][:16] for e in events])
        self.assertEqual(len(chunks), 2)
        self.assertNotIn('sk-lf-', json.dumps(body))

    def test_evidence_filename_validation(self):
        events, _ = fixture()
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'wrong.json').write_text(json.dumps(events[0]))
            with self.assertRaises(ValueError):
                load_events(directory)

    def test_receipt_skips_acknowledged_batch(self):
        client = LocalClient(dict(LANGFUSE_BASE_URL=BASE_URL,
                                 LANGFUSE_PUBLIC_KEY='pk-lf-test', LANGFUSE_SECRET_KEY='sk-lf-test'))
        calls = []
        client.request = lambda path, body: calls.append(path) or {}
        body = trial_payload(*fixture())
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(client.send(body, directory), 'transport_acknowledged')
            self.assertEqual(client.send(body, directory), 'previously_acknowledged')
            self.assertEqual(len(calls), 1)
            client.send(body, directory, reexport=True)
            self.assertEqual(len(calls), 2)

    def test_partial_ingestion_keeps_batch_unacknowledged(self):
        client = LocalClient(dict(LANGFUSE_BASE_URL=BASE_URL,
                                 LANGFUSE_PUBLIC_KEY='pk-lf-test', LANGFUSE_SECRET_KEY='sk-lf-test'))
        client.request = lambda path, body: {'partialSuccess': {'rejectedSpans': 1}}
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(RuntimeError):
                client.send(trial_payload(*fixture()), directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_readback_checks_all_ids_and_cursor(self):
        events, _ = fixture()
        client = LocalClient(dict(LANGFUSE_BASE_URL=BASE_URL,
                                 LANGFUSE_PUBLIC_KEY='pk-lf-test', LANGFUSE_SECRET_KEY='sk-lf-test'))
        answers = [{'data': [{'id': e['event_id'][:16]} for e in events[:2]],
                    'meta': {'cursor': 'next'}},
                   {'data': [{'id': events[2]['event_id'][:16]}], 'meta': {}}]
        client.request = lambda path: answers.pop(0)
        self.assertTrue(client.readback(events)['matched'])


if __name__ == '__main__':
    unittest.main()

import copy
import json
from pathlib import Path
import tempfile
import unittest

from gateway_policy import MODEL
from local_trace import observation
from netcup.verify_observability import credentials, read_observations, verify


class ObservabilityReadbackTests(unittest.TestCase):
    def setUp(self):
        shared = dict(trial_id='readback-fixture', task_id='fixture', harness='terminus-2',
                      protocol_sha256='a' * 64)
        self.events = [observation(**shared, kind='trial', sequence=0, started_ns=1000000000, ended_ns=3000000000),
            observation(**shared, kind='generation', sequence=1, started_ns=1100000000, ended_ns=1200000000,
                        metrics={'input_tokens': 10, 'output_tokens': 2, 'charged_nanodollars': 1000000})]
        self.rows = [dict(id=e['event_id'][:16], traceId=e['trace_id'][:32], name=e['kind'],
                         type='SPAN' if e['kind'] == 'trial' else 'GENERATION', sessionId=e['trial_id'],
                         parentObservationId=None if e['kind'] == 'trial' else self.events[0]['event_id'][:16],
                         metadata={key:e[key] for key in ('harness', 'task_id', 'protocol_sha256', 'status')})
                     for e in self.events]
        self.rows[1].update(model=MODEL, usageDetails={'input': 10, 'output': 2, 'total': 12}, totalCost=.001)
        self.auth = {'base_url': 'http://127.0.0.1:3300', 'public_key': 'pk-lf-fixture', 'secret_key': 'sk-lf-fixture'}

    def test_exact_metadata_readback_not_dashboard_or_project_success(self):
        result = verify(self.events, self.rows)
        self.assertEqual(result['status'], 'observations_api_verified_dashboard_pending')
        self.assertEqual(result['metrics']['charged_nanodollars'], 1000000)
        self.assertFalse(result['dashboard_visually_verified'])
        self.assertNotIn('project_success', result)

    def test_missing_duplicate_and_unexpected_rows_rejected(self):
        extra = copy.deepcopy(self.rows[0]); extra['id'] = 'unexpected'
        for rows in (self.rows[:1], self.rows + [self.rows[0]], self.rows + [extra]):
            with self.subTest(rows=len(rows)), self.assertRaises(ValueError): verify(self.events, rows)

    def test_wrong_identity_model_tokens_cost_rejected(self):
        for key, value in [('name', 'wrong'), ('type', 'SPAN'), ('sessionId', 'wrong'),
                           ('parentObservationId', None), ('model', 'wrong'),
                           ('usageDetails', {'input': 11, 'output': 2}), ('totalCost', .0011),
                           ('totalCost', 'NaN')]:
            rows = copy.deepcopy(self.rows); rows[1][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): verify(self.events, rows)

    def test_partial_spool_rejected_before_network(self):
        def fail(query): self.fail('must not fetch an incomplete trial')
        with self.assertRaises(ValueError): read_observations(self.events[1:], self.auth, get=fail)

    def test_verifier_zero_and_measured_runtime_are_checked(self):
        event = observation(trial_id='readback-fixture', task_id='fixture', harness='terminus-2',
            protocol_sha256='a'*64, kind='verifier', sequence=2, started_ns=2000000000,
            ended_ns=2100000000, metrics={'duration_seconds': .1}, reward=0)
        row = dict(id=event['event_id'][:16], traceId=event['trace_id'][:32], name='verifier',
            type='SPAN', sessionId=event['trial_id'], parentObservationId=self.events[0]['event_id'][:16],
            metadata={**self.rows[0]['metadata'], 'attributes.uts.duration_seconds': .1,
                      'attributes.uts.official_verifier_reward': 0})
        result = verify(self.events+[event], self.rows+[row])
        self.assertEqual(result['verifier_rewards'], {'readback-fixture': 0})
        for key,value in [('attributes.uts.official_verifier_reward',1),
                          ('attributes.uts.duration_seconds',.2),('protocol_sha256','wrong')]:
            changed=copy.deepcopy(row);changed['metadata'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):
                verify(self.events+[event], self.rows+[changed])

    def test_pagination_bounded_and_never_requests_raw_io(self):
        calls = []
        def page(query):
            calls.append(query)
            return {'data': [self.rows[len(calls)-1]], 'meta': {'cursor': 'next' if len(calls) == 1 else None}}
        rows = read_observations(self.events, self.auth, get=page)
        verify(self.events, rows)
        self.assertNotIn('io', calls[0]['fields'].split(','))
        self.assertIn('fromStartTime', calls[0]); self.assertIn('toStartTime', calls[0])
        self.assertEqual(calls[1]['cursor'], 'next')

    def test_repeated_cursor_and_malformed_page_rejected(self):
        for result in ({'data': [], 'meta': {'cursor': 'stuck'}}, {'data': []}):
            with self.assertRaises(ValueError):
                read_observations(self.events, self.auth, get=lambda query: result)

    def test_credentials_require_private_file_and_loopback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'credentials.json'
            path.write_text(json.dumps(self.auth)); path.chmod(0o600)
            self.assertEqual(credentials(path), self.auth)
            path.chmod(0o644)
            with self.assertRaises(ValueError): credentials(path)
            path.chmod(0o600)
            bad = dict(self.auth, base_url='https://external.example')
            path.write_text(json.dumps(bad))
            with self.assertRaises(ValueError): credentials(path)
            with self.assertRaises(ValueError): read_observations(self.events, bad, get=lambda _: {})


if __name__ == '__main__':
    unittest.main()

import copy
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from local_study import LocalProtocol, build, fingerprint, quotas, schedule, select
from local_selection import choose, validate_block
from local_trace import TraceSpool, observation, validate
from local_langfuse import payload, export, NoRedirect

ROOT = Path(__file__).resolve().parents[1]


class StudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = build(ROOT)

    def test_dataset_hashes_and_selection(self):
        doc = self.manifest
        self.assertEqual(len(doc['tasks']), 89)
        self.assertEqual(len(doc['selection']['development_ids']), 20)
        self.assertEqual(len(doc['selection']['outside_development_ids']), 69)
        self.assertEqual(set(doc['selection']['coverage_full']['category']),
                         set(doc['selection']['coverage_development']['category']))
        self.assertEqual(select(list(reversed(doc['tasks']))), select(doc['tasks']))

    def test_quotas(self):
        self.assertEqual(quotas({'a': 80, 'b': 9}, 20, cover=True), {'a': 17, 'b': 3})
        self.assertEqual(sum(quotas({str(i): 1 for i in range(25)}, 20, cover=True).values()), 20)
        self.assertEqual(quotas({'a': 1}, 0), {'a': 0})
        with self.assertRaises(ValueError):
            quotas({'a': 1}, 2)

    def test_selection_ignores_outcomes(self):
        rows = copy.deepcopy(self.manifest['tasks'])
        for row in rows:
            row.update(reward=1, reference_solution='unused', hidden_test='unused')
        self.assertEqual(select(rows), select(self.manifest['tasks']))
        with self.assertRaises(ValueError):
            select(rows[:-1] + rows[:1])

    def test_protocol(self):
        protocol = LocalProtocol()
        request = dict(model=protocol.model, temperature=1.0, top_p=.95, top_k=40, max_tokens=8192)
        self.assertTrue(protocol.validate_request(request))
        for key, value in [('model', 'openrouter/model'), ('top_k', True), ('max_tokens', 8193),
                           ('reasoning_effort', 'high'), ('provider', {})]:
            with self.assertRaises(ValueError):
                protocol.validate_request(dict(request, **{key: value}))
        for change in [{'context_tokens': 65536}, {'temperature': True}, {'model': 'other'}]:
            with self.assertRaises(ValueError):
                replace(protocol, **change)
        self.assertEqual(protocol.document()['external_inference_usd'], 0)
        self.assertIsNone(protocol.document()['compute_cost_usd'])

    def test_schedule_counts_and_order(self):
        rows = schedule(self.manifest, finalist='C3')
        self.assertEqual(len(rows), 487)
        self.assertEqual(len({r['trial_id'] for r in rows}), 487)
        self.assertEqual({r['harness'] for r in rows[:89]}, {'terminus-2'})
        self.assertEqual({r['harness'] for r in rows[89:178]}, {'openhands'})
        self.assertEqual(len(schedule(self.manifest)), 278)
        self.assertTrue(all(r['status'] == 'planned_not_launched' for r in rows))
        self.assertEqual({r['task_id'] for r in rows[-89:]}, {r['task_id'] for r in rows[:89]})

    def test_development_selection(self):
        ids = self.manifest['selection']['development_ids']
        digest = fingerprint(LocalProtocol().document())
        def block(harness, tokens):
            return [dict(task_id=t, harness=harness, protocol_sha256=digest,
                         stage='development', repetition=0, infrastructure_valid=True,
                         cleanup_verified=True, reward=0, output_tokens=tokens, agent_seconds=1.0) for t in ids]
        a, b = block('C0', 50), block('C1', 60)
        result = choose({'C0': a, 'C1': b}, ids, protocol_sha256=digest, retained_features={'C0': 0, 'C1': 1})
        self.assertEqual(result['selected'], 'C0')
        b[0]['reward'] = 1
        self.assertEqual(choose({'C0': a, 'C1': b}, ids, protocol_sha256=digest,
                                retained_features={'C0': 0, 'C1': 1})['selected'], 'C1')
        for key, value in [('infrastructure_valid', False), ('output_tokens', None),
                           ('stage', 'confirmation'), ('reward', True)]:
            broken = copy.deepcopy(a)
            broken[0][key] = value
            with self.assertRaises(ValueError):
                validate_block(broken, ids, harness='C0', protocol_sha256=digest)


class TraceTests(unittest.TestCase):
    def event(self, **extra):
        data = dict(trial_id='baseline-openhands-r0-test', task_id='test', harness='openhands',
                    protocol_sha256='a' * 64, kind='trial', sequence=0, started_ns=10, ended_ns=20)
        data.update(extra)
        return observation(**data)

    def test_spool_durable_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            spool = TraceSpool(tmp)
            event = self.event()
            spool.record(event)
            spool.record(event)
            self.assertEqual(spool.events(), [event])
            with self.assertRaises(ValueError):
                spool.record(self.event(status='error'))
            self.assertEqual(len(list(Path(tmp).glob('*.json'))), 1)

    def test_metadata_allowlist(self):
        for key in ('prompt', 'api_key', 'command', 'input', 'output'):
            with self.assertRaises(ValueError):
                validate(dict(self.event(), **{key: 'private text'}))
        with self.assertRaises(ValueError):
            self.event(reward=1)
        with self.assertRaises(ValueError):
            self.event(metrics={'duration_seconds': float('nan')})
        with self.assertRaises(ValueError):
            self.event(metrics={'input_tokens': True})
        with self.assertRaises(ValueError):
            self.event(ended_ns=9)

    def test_otel_payload(self):
        root = self.event()
        generation = self.event(sequence=1, kind='generation', started_ns=11, ended_ns=19,
                                metrics={'input_tokens': 5, 'output_tokens': 3})
        spans = payload([root, generation])['resourceSpans'][0]['scopeSpans'][0]['spans']
        self.assertEqual(spans[1]['parentSpanId'], spans[0]['spanId'])
        self.assertEqual(len(spans[0]['traceId']), 32)
        self.assertIn('gen_ai.usage.output_tokens', json.dumps(spans))
        with self.assertRaises(ValueError):
            payload([generation])
        with self.assertRaises(ValueError):
            payload([root, root])

    def test_export_rejects_wrong_origin_and_missing_credentials(self):
        for base, pub, sec in [('https://openrouter.ai', 'pk-lf-test', 'sk-lf-test'),
                               ('https://cloud.langfuse.com', '', '')]:
            with self.assertRaises(ValueError):
                export('/not-used', base_url=base, public_key=pub, secret_key=sec)
        with self.assertRaises(RuntimeError):
            NoRedirect().redirect_request(None, None, 302, None, None, 'https://other')

    def test_transport_ack_and_replay(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self): return b'{}'
        with tempfile.TemporaryDirectory() as tmp:
            TraceSpool(tmp).record(self.event())
            with patch('local_langfuse.build_opener') as opener:
                opener.return_value.open.return_value = Response()
                kwargs = dict(base_url='https://cloud.langfuse.com', public_key='pk-lf-test', secret_key='sk-lf-test')
                self.assertEqual(export(tmp, **kwargs)['status'], 'transport_acknowledged_not_dashboard_verified')
                self.assertEqual(export(tmp, **kwargs)['status'], 'previously_acknowledged')
                self.assertEqual(opener.return_value.open.call_count, 1)

    def test_failed_export_keeps_spool(self):
        with tempfile.TemporaryDirectory() as tmp:
            TraceSpool(tmp).record(self.event())
            with patch('local_langfuse.build_opener') as opener:
                opener.return_value.open.side_effect = OSError('offline')
                with self.assertRaises(OSError):
                    export(tmp, base_url='https://cloud.langfuse.com', public_key='pk-lf-test', secret_key='sk-lf-test')
            self.assertEqual(len(TraceSpool(tmp).events()), 1)
            self.assertFalse(list(Path(tmp).glob('.exported-*')))


if __name__ == '__main__':
    unittest.main()

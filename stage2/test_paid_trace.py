from pathlib import Path
import json
import tempfile
import unittest

from gateway_policy import MODEL, CANONICAL_MODEL
from local_langfuse import payload
from paid_trace import PaidTrialTrace
from scored_gateway import durable_json


class PaidTraceTests(unittest.TestCase):
    def fixture(self, root, cost='.001'):
        evidence = root / 'evidence'
        evidence.mkdir()
        durable_json(evidence / '000001.response.json', {'id': 'fixture', 'model': MODEL,
            'choices': [{'message': {'content': 'secret-canary-task-text'}}],
            'usage': {'cost': cost, 'prompt_tokens': 10, 'completion_tokens': 2}})
        durable_json(evidence / '000001.receipt.json', {'id': 'fixture', 'model': CANONICAL_MODEL,
            'provider_name': 'DeepInfra', 'total_cost': cost})
        durable_json(evidence / '000001.timing.json', {'started_ns': 15, 'ended_ns': 20, 'seconds': .2, 'status': 'ok'})
        trace = PaidTrialTrace(root / 'traces', trial_id='fixture', task_id='fixture',
            harness='terminus-2', protocol_sha256='a'*64)
        trace(kind='verifier', started_ns=22, ended_ns=25, seconds=.1, reward=0)
        trace(kind='trial', started_ns=10, ended_ns=30, seconds=1)
        billing = {'billing_verified': True, 'requests': 1, 'prompt_tokens': 10, 'completion_tokens': 2, 'charged_usd': '.001'}
        return trace, evidence, billing

    def test_phase_generation_cost_and_model_export_without_raw_content(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, evidence, billing = self.fixture(Path(temporary))
            result = trace.finish(evidence, billing)
            self.assertEqual(result['events'], 3)
            document = payload(trace.spool.events(), track='netcup-openrouter')
            serialized = json.dumps(document)
            self.assertIn(MODEL, serialized)
            self.assertIn('charged_nanodollars', serialized)
            self.assertNotIn('secret-canary', serialized)
            self.assertNotIn('Qwen', serialized)
            root = [e for e in trace.spool.events() if e['kind'] == 'trial'][0]
            self.assertEqual(root['metrics']['charged_nanodollars'], 1_000_000)

    def test_unreconciled_billing_cannot_be_exported(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, evidence, billing = self.fixture(Path(temporary))
            billing['billing_verified'] = False
            with self.assertRaises(ValueError):
                trace.finish(evidence, billing)

    def test_charge_mismatch_cannot_finish_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            trace, evidence, billing = self.fixture(Path(temporary), cost='.002')
            with self.assertRaises(ValueError):
                trace.finish(evidence, billing)
            self.assertFalse(any(e['kind'] == 'trial' for e in trace.spool.events()))

    def test_unknown_track_rejected(self):
        with self.assertRaises(ValueError):
            payload([], track='unregistered')

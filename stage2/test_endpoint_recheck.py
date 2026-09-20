import fcntl
from pathlib import Path
import tempfile
import unittest

from budget_ledger import Ledger, dollars
from endpoint_recheck import ReservedClient, run, scored_state
from model_protocol import ModelSettings, freeze_protocol
from scored_gateway import durable_json, private_directory
from study_budget import SCORED_CEILING, STAGE_CAPS, TRIAL_CAP
from test_scored_gateway import Client


class Fixture(Client):
    def balance(self): return self.allowance
    def complete(self, request):
        result = super().complete(request)
        result.update(provider='DeepInfra', choices=[{'message': {'content': 'UTS_OK'}}])
        result['usage'].update(is_byok=False, prompt_tokens=14, completion_tokens=4)
        return result


class EndpointRecheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = private_directory(self.root / '.runtime/stage2')
        setup = Ledger(self.runtime/'setup_budget.sqlite', '1', '1', {'setup':'1'})
        setup.reserve('prior', 'prior', '.01', '12', 'setup'); setup.settle('prior', '.001'); setup.close()
        (self.runtime/'setup_budget.sqlite').chmod(0o600)
        scored = Ledger(self.runtime/'scored_budget.sqlite', SCORED_CEILING, TRIAL_CAP, STAGE_CAPS, allow_estimated_trials=True)
        scored.reserve('unknown', 'old-trial', '.106496', '12', 'development', trial_estimate='.001')
        scored.close()
        path = private_directory(self.runtime/'scored-trials/old-trial')
        durable_json(path/'result.json', {'status':'billing_unresolved', 'reward':0})
        freeze_protocol(self.runtime, ModelSettings(8192, 1., 'high'))
        self.client = Fixture()
        self.before = scored_state(self.runtime)

    def test_one_setup_call_retains_old_scored_evidence_and_cost(self):
        result = run(self.root, 'fixture', execute=True, client=self.client)
        self.assertEqual(result['status'], 'reply_and_billing_verified')
        self.assertEqual(result['upstream_generation_calls'], 1)
        self.assertEqual(result['billing']['aggregate_setup_charged_usd'], '0.002')
        self.assertEqual(scored_state(self.runtime), self.before)
        self.assertFalse(result['benchmark_resumption_authorized'])
        with self.assertRaises(ValueError): run(self.root, 'fixture', execute=True, client=self.client)
        self.assertEqual(self.client.calls, 1)

    def test_failure_retains_both_reservations_and_does_not_retry(self):
        self.client.fail = True
        result = run(self.root, 'failure', execute=True, client=self.client)
        self.assertEqual(result['status'], 'diagnostic_failed_no_replay')
        self.assertEqual(result['upstream_generation_calls'], 1)
        self.assertEqual(scored_state(self.runtime), self.before)
        ledger = Ledger(self.runtime/'setup_budget.sqlite', '1', '1', {'setup':'1'})
        try:
            self.assertEqual(ledger.db.execute("SELECT COUNT(*) FROM requests WHERE state='pending'").fetchone()[0], 1)
        finally:
            ledger.close()

    def test_existing_scored_liability_reduces_available_credit(self):
        self.client.allowance = '2.15'
        result = run(self.root, 'credit', execute=True, client=self.client)
        self.assertEqual(result['status'], 'diagnostic_failed_no_replay')
        self.assertEqual(result['upstream_generation_calls'], 0)
        self.assertEqual(scored_state(self.runtime), self.before)

    def test_explicit_execution_and_idle_host_required(self):
        with self.assertRaises(ValueError): run(self.root, 'fixture', client=self.client)
        with (self.runtime/'scored.lock').open('a+') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): run(self.root, 'fixture', execute=True, client=self.client)
        self.assertEqual(self.client.calls, 0)

    def test_guard_permits_only_one_generation(self):
        guarded = ReservedClient(self.client, self.before[0])
        guarded.complete({})
        with self.assertRaises(ValueError): guarded.complete({})
        self.assertEqual(self.client.calls, 1)

    def test_empty_choices_still_reconciles_billing(self):
        complete = self.client.complete
        def empty_response(request):
            result = complete(request)
            result['choices'] = []
            return result
        self.client.complete = empty_response
        result = run(self.root, 'empty', execute=True, client=self.client)
        self.assertEqual(result['status'], 'response_received_fixture_not_matched')
        self.assertEqual(result['billing']['aggregate_setup_charged_usd'], '0.002')
        self.assertEqual(result['upstream_generation_calls'], 1)
        self.assertEqual(scored_state(self.runtime), self.before)


if __name__ == '__main__': unittest.main()

"""Synthetic registration/recovery tests; no network, credentials or paid calls."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from portable_custom_gateway import CustomRetrySession
from portable_custom_policy import (EXPERIMENT, POLICY, POLICY_FILE, QUALIFICATION, SETTINGS,
    INPUT_SHA256, BLOCKS, CANDIDATE_VERSION, PYTHON_SHA256, fingerprint,
    require_policy, require_block, require_trial, cells, block_path)
from credit_only_gateway import PassiveSession, CreditOnlyError
from credit_only_accounting import summarise
from retry_gateway import RetrySession
from retry_runtime import activate
from scored_gateway import durable_json, private_directory
from test_credit_only_gateway import TOKEN, Client
from test_retry_gateway import Clock, Event, Flaky, REQUEST


def fixture(root, condition='C0', parent=None):
    """Test records only; this is deliberately not a native qualification."""
    runtime = private_directory(Path(root) / '.runtime/stage2')
    if not (runtime / POLICY_FILE).exists():
        durable_json(runtime / POLICY_FILE, POLICY)
    tasks = json.loads((Path(__file__).parent / 'input_manifest.json').read_text())['development_ids']
    proof = dict(experiment=EXPERIMENT, status='passed', sources_sha256='a' * 64,
        candidate_version=CANDIDATE_VERSION, python_runtime={'sha256': PYTHON_SHA256},
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint())
    if not (runtime / QUALIFICATION).exists():
        durable_json(runtime / QUALIFICATION, proof)
    block = dict(experiment=EXPERIMENT, stage='development', condition=condition, parent=parent,
        candidate_version=CANDIDATE_VERSION, python_runtime_sha256=PYTHON_SHA256,
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, development_ids=tasks,
        primary_comparator='terminus-2', secondary_comparator='openhands',
        cells=cells(tasks, condition, parent), sources_sha256='a' * 64,
        qualification_sha256=fingerprint(proof))
    path = block_path(runtime, condition)
    private_directory(path.parent)
    durable_json(path, block)
    return runtime, block, proof


class CustomPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime, self.block, self.proof = fixture(self.root)
        self.trial = self.block['cells'][0]['trial_id']

    def test_explicit_custom_authority_is_not_a_baseline_file(self):
        self.assertEqual(require_policy(self.runtime), POLICY)
        self.assertEqual(require_trial(self.runtime, self.trial, 'development'), self.block)
        self.assertEqual(POLICY['reserve_usd'], '0')
        self.assertTrue(all(POLICY[n] is None for n in ('per_task_cap_usd', 'project_cap_usd',
            'stage_cap_usd', 'model_call_cap', 'physical_request_count_cap', 'provider_max_price')))
        self.assertFalse(POLICY['automatic_top_up'])
        self.assertFalse(POLICY['automatic_credit_limit_increase'])
        self.assertFalse((self.runtime / 'credit-only-policy.json').exists())

    def test_every_variant_has_exactly_twenty_unique_original_tasks(self):
        tasks = self.block['development_ids']
        for condition, parent in (('C0', None), ('C1', None), ('C2', 'C0'), ('C2', 'C1')):
            rows = cells(tasks, condition, parent)
            self.assertEqual(len({r['trial_id'] for r in rows}), 20)
            self.assertEqual([r['task_id'] for r in rows], tasks)
        for changed in (tasks[:-1], tasks[::-1], tasks[:-1] + ['held-out'], tasks + [tasks[0]]):
            with self.assertRaises(ValueError): cells(changed, 'C0')

    def test_unknown_condition_or_c2_parent_rejected(self):
        for condition, parent in (('C3', None), ('C2', None), ('C0', 'C1'), ('C2', 'openhands')):
            with self.assertRaises(ValueError): cells(self.block['development_ids'], condition, parent)

    def test_financial_or_provider_drift_rejected(self):
        path = self.runtime / POLICY_FILE
        for changes in ({'reserve_usd': '1'}, {'model_call_cap': 100}, {'parallel_trials': True},
                {'automatic_credit_limit_increase': True}, {'model': {'model': 'other'}}):
            path.write_text(json.dumps(dict(POLICY, **changes)))
            with self.assertRaises(ValueError): require_policy(self.runtime)

    def test_private_records_and_symlinks_rejected(self):
        path = self.runtime / POLICY_FILE
        path.chmod(0o644)
        with self.assertRaises(ValueError): require_policy(self.runtime)
        path.chmod(0o600)
        target = self.root / 'saved-policy.json'
        path.rename(target)
        path.symlink_to(target)
        with self.assertRaises(OSError): require_policy(self.runtime)

    def test_registration_drift_rejected(self):
        path = block_path(self.runtime, 'C0')
        for key, value in (('stage', 'final'), ('condition', 'C1'), ('input_manifest_sha256', 'b' * 64),
                ('primary_comparator', 'openhands'), ('cells', self.block['cells'][:-1]),
                ('sources_sha256', 'invalid'), ('qualification_sha256', 'b' * 64)):
            path.write_text(json.dumps(dict(self.block, **{key: value})))
            with self.subTest(key=key), self.assertRaises(ValueError):
                require_trial(self.runtime, self.trial, 'development')

    def test_qualification_changed_or_failed_cannot_dispatch(self):
        path = self.runtime / QUALIFICATION
        for changed in (dict(self.proof, status='failed'), dict(self.proof, sources_sha256='b' * 64)):
            path.write_text(json.dumps(changed))
            with self.assertRaises(ValueError): require_trial(self.runtime, self.trial, 'development')

    def test_final_arbitrary_id_or_held_out_attempt_denied(self):
        for trial, stage in ((self.trial, 'final'), ('../secret', 'development'),
                ('customdev2-c0-01-unregistered', 'development'), ('other', 'development')):
            with self.assertRaises(ValueError): require_trial(self.runtime, trial, stage)

    def test_historical_gateway_remains_final_only(self):
        for cls in (PassiveSession, RetrySession):
            with self.assertRaises(ValueError):
                cls(self.root, 'legacy', 'development', TOKEN, Client(), settings=SETTINGS, clock=Clock()) \
                    if cls is RetrySession else cls(self.root, 'legacy', 'development', TOKEN, Client(), settings=SETTINGS)
        self.assertFalse((self.runtime / 'scored-attempts').exists())

    def test_predecessor_cells_and_qualification_cannot_be_relabelled(self):
        from corrected_custom_policy import require_trial as legacy_trial
        with self.assertRaises((ValueError, OSError)):
            legacy_trial(self.runtime, self.trial, 'development')
        with self.assertRaises(ValueError):
            require_trial(self.runtime, self.trial.replace('customdev2-', 'customdev1-'), 'development')
        for changes in ({'candidate_version': 'stage2-candidate-0.2.0'},
                        {'python_runtime_sha256': 'b' * 64}):
            block_path(self.runtime, 'C0').write_text(json.dumps(self.block | changes))
            with self.assertRaises(ValueError): require_trial(self.runtime, self.trial, 'development')


class CustomGatewayTests(unittest.TestCase):
    setUp = CustomPolicyTests.setUp
    def session(self, failures=(), index=0, timeout=10000):
        trial = self.block['cells'][index]['trial_id']
        clock = Clock()
        activate(self.runtime, trial, timeout, SETTINGS, clock)
        session = CustomRetrySession(self.root, trial, 'development', TOKEN,
            Flaky(clock, failures), settings=SETTINGS, clock=clock)
        session.cancelled = Event(clock)
        return session

    def test_more_than_100_requests_without_money_reservations(self):
        with patch('budget_ledger.Ledger.reserve', side_effect=AssertionError('No financial gate')), self.session() as s:
            s.client.response['usage']['cost'] = Decimal('100.123456789')
            for _ in range(105): s.complete(TOKEN, REQUEST)
            evidence = summarise(self.runtime, s.trial_id)
            self.assertEqual(evidence['requests'], 105)
            self.assertEqual(evidence['charged_usd'], '10512.962962845')
        self.assertFalse(list(self.runtime.glob('*.sqlite')))

    def test_unknown_cost_and_many_transient_retries_do_not_block(self):
        with self.session([(429, ['0'])] * 105) as s:
            s.client.response.pop('usage')
            s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 106)
            evidence = summarise(self.runtime, s.trial_id)
            self.assertEqual(evidence['unknown_cost_requests'], 106)
            self.assertIsNone(evidence['charged_usd'])
            self.assertIsNone(evidence['provider_stop'])

    def test_auth_credit_identity_are_real_stops_not_spending_caps(self):
        for index, code in enumerate((401, 402, 403)):
            with self.session([(code, ['1'])], index=index) as s:
                with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
                self.assertEqual(len(s.client.calls), 1)
        with self.session(index=3) as s:
            s.client.response['model'] = 'other-model'
            with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 1)

    def test_deadline_and_revocation_still_apply(self):
        with self.session(timeout=1) as s:
            s.clock.now += 2
            with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
            self.assertFalse(s.client.calls)
        with self.session(index=1) as s:
            s.cancelled.set()
            with self.assertRaises(CreditOnlyError): s.complete(TOKEN, REQUEST)
            self.assertFalse(s.client.calls)

    def test_registration_rechecked_before_every_physical_call(self):
        with self.session() as s:
            s.complete(TOKEN, REQUEST)
            block_path(self.runtime, 'C0').write_text(json.dumps(dict(self.block, qualifier_note='changed')))
            with self.assertRaises(ValueError): s.complete(TOKEN, REQUEST)
            self.assertEqual(len(s.client.calls), 1)

    def test_bad_token_or_second_attempt_never_replays(self):
        with self.session() as s:
            with self.assertRaises(CreditOnlyError): s.complete('wrong', REQUEST)
            self.assertFalse(s.client.calls)
        with self.assertRaises(FileExistsError):
            CustomRetrySession(self.root, self.trial, 'development', TOKEN, Client(), settings=SETTINGS, clock=Clock())


if __name__ == '__main__': unittest.main()

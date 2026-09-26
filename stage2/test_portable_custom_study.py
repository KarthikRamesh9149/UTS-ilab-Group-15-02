"""Registration/selection/dispatch correctness, all fixtures and no live calls."""
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

from portable_custom_agent import agent_factory
from portable_custom_policy import (EXPERIMENT, SETTINGS, POLICY, QUALIFICATION, fingerprint,
    require_trial, INPUT_SHA256, CANDIDATE_VERSION, PYTHON_SHA256, block_path)
from portable_custom_study import (identity, qualified, register, admit_trial, audited,
    summary, selected_parent, TEST_MODULES, PROBE_CASES, PROBE_CHECKS, probe_checks)
from run_portable_custom import dispatch
from scored_trial import run_trial
from scored_gateway import private_directory, durable_json
from test_portable_custom_policy import fixture
from test_retry_gateway import Clock


class CustomStudyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime, self.block, self.base_proof = fixture(self.root)
        self.scope = dict(input_manifest_sha256=INPUT_SHA256,
            development_ids=self.block['development_ids'], primary_comparator='terminus-2', secondary_comparator='openhands')
        self.image = 'sha256:' + 'a' * 64
        self.proof = dict(self.base_proof, matched_scope=self.scope, gateway_image=self.image,
            guard_image=self.image, setup_timeout_seconds=900)

    def records(self, condition='C0', parent=None, *, missing=None, failures=0, unknown=False):
        if condition != 'C0':
            _, block, _ = fixture(self.root, condition, parent)
        else:
            block = self.block
        for i, cell in enumerate(block['cells']):
            folder = private_directory(self.runtime / 'scored-trials' / cell['trial_id'])
            reward = None if i == missing else int(i >= failures)
            result = dict(cell, stage='development', model_protocol_sha256=SETTINGS.fingerprint(),
                accounting_mode='provider-credit-only', custom_registration_sha256=fingerprint(block),
                model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
                status='verified', phase_seconds={'agent': 10.},
                verifier_result={'rewards': {'reward': reward}},
                agent_context={'metadata': {'custom_condition': condition, 'custom_parent': parent,
                    'custom_version': CANDIDATE_VERSION}})
            durable_json(folder / 'result.json', result)
            if unknown:
                calls = private_directory(self.runtime / 'scored-attempts' / cell['trial_id'])
                durable_json(calls / '000001.request.json', {})
        return block

    def test_source_identity_binds_current_agent_gateway_and_tests(self):
        root = Path(__file__).resolve().parents[1]
        with patch('portable_custom_study.runtime_bundle') as bundle:
            bundle.return_value.validate.return_value = {'sha256': PYTHON_SHA256}
            current = identity(root)
        for name in ('portable_custom_agent.py', 'portable_custom_policy.py', 'credit_only_gateway.py',
                'scored_trial.py', 'test_portable_custom_study.py'):
            self.assertIn(name, current['sources'])
        self.assertEqual(current['matched_scope']['conditions']['terminus-2']['passed'], 14)
        self.assertEqual(current['matched_scope']['conditions']['openhands']['passed'], 10)

    def test_unqualified_fixture_is_not_native_admission(self):
        with patch('portable_custom_study.identity', return_value=self.base_proof), \
             patch('host_environment.snapshot', return_value={}):
            with self.assertRaises(ValueError): qualified(self.root)

    def test_native_proof_requires_every_variant_and_current_dependencies(self):
        current = dict(self.base_proof, dependencies={'version': 'pinned'})
        proof = dict(current, live_api_calls=0, host_environment={},
            gateway_image=self.image, guard_image=self.image, image_sources_match=True, setup_timeout_seconds=900,
            offline=dict(modules=list(TEST_MODULES), tests=100, passed=True, skipped=0, errors=0, failures=0),
            synthetic=[dict(condition=c, parent=p, mode=m, status='passed', live_api_calls=0,
                checks={k: True for k in probe_checks(m)}) for c, p, m in PROBE_CASES])
        path = self.runtime / QUALIFICATION
        with patch('portable_custom_study.identity', return_value=current), \
             patch('host_environment.snapshot', return_value={}), patch('scored_trial.docker', return_value=self.image):
            path.write_text(json.dumps(proof))
            self.assertEqual(qualified(self.root), proof)
            for changes in ({'dependencies': {}}, {'synthetic': proof['synthetic'][:-1]},
                    {'live_api_calls': 1}, {'image_sources_match': False},
                    {'setup_timeout_seconds': 9000},
                    {'offline': dict(proof['offline'], skipped=1)}):
                path.write_text(json.dumps(dict(proof, **changes)))
                with self.assertRaises(ValueError): qualified(self.root)

    def test_register_is_exact_and_idempotent_and_requires_c0_before_c1(self):
        with tempfile.TemporaryDirectory() as directory:
            fresh = Path(directory)
            state = private_directory(fresh / '.runtime/stage2')
            from portable_custom_policy import POLICY_FILE
            durable_json(state / POLICY_FILE, POLICY)
            durable_json(state / QUALIFICATION, self.proof)
            with patch('portable_custom_study.qualified', return_value=self.proof):
                block = register(fresh, 'C0')
                self.assertEqual(register(fresh, 'C0'), block)
                self.assertEqual(len(block['cells']), 20)
                self.assertEqual(require_trial(state, block['cells'][6]['trial_id'], 'development'), block)
                with self.assertRaises(ValueError): register(fresh, 'C1')
                changed = dict(self.proof, sources_sha256='b' * 64)
                with patch('portable_custom_study.qualified', return_value=changed):
                    with self.assertRaises(ValueError): register(fresh, 'C0')

    def test_actual_factory_binds_condition_parent_and_version(self):
        for condition, parent, _ in PROBE_CASES:
            factory = agent_factory(self.root, condition, parent=parent)
            self.assertEqual(factory.harness, condition)
            self.assertEqual(factory.custom_parent, parent)
            self.assertEqual(factory.custom_version, 'stage2-candidate-0.3.0')
            self.assertEqual(factory.python_runtime_sha256, PYTHON_SHA256)

    def test_admission_requires_matching_task_factory_and_images(self):
        cell = self.block['cells'][0]
        factory = agent_factory(self.root, 'C0')
        args = dict(trial_id=cell['trial_id'], task_id=cell['task_id'], stage='development',
            factory=factory, settings=SETTINGS, gateway_image=self.image, guard_image=self.image)
        with patch('portable_custom_study.qualified', return_value=self.base_proof | dict(gateway_image=self.image, guard_image=self.image)):
            # Qualification hash includes image metadata, unlike the deliberately
            # unqualified gateway fixture; mismatch is rejected.
            with self.assertRaises(ValueError): admit_trial(self.root, **args)
        proof = self.base_proof | dict(gateway_image=self.image, guard_image=self.image)
        (self.runtime / QUALIFICATION).write_text(json.dumps(proof))
        block = dict(self.block, qualification_sha256=fingerprint(proof))
        block_path(self.runtime, 'C0').write_text(json.dumps(block))
        with patch('portable_custom_study.qualified', return_value=proof):
            self.assertEqual(admit_trial(self.root, **args), fingerprint(block))
            for changes in ({'task_id': 'held-out'}, {'stage': 'final'},
                    {'factory': agent_factory(self.root, 'C1')}, {'gateway_image': 'other'}):
                with self.assertRaises(ValueError): admit_trial(self.root, **(args | changes))

    def test_missing_verifier_and_cost_remain_unknown_not_zero(self):
        self.records(missing=3, failures=5, unknown=True)
        value = summary(self.root, 'C0')
        self.assertEqual((value['passes'], value['failures'], value['no_verifier_result']), (15, 4, 1))
        self.assertEqual(value['attempted'], 20)
        self.assertIsNone(value['charged_usd'])
        self.assertEqual(value['known_charged_usd'], '0')
        self.assertEqual(value['unknown_cost_requests'], 20)

    def test_parent_selection_uses_all_twenty_not_just_successes(self):
        self.records(failures=7, unknown=True)
        self.records('C1', failures=5, unknown=True)
        selection = selected_parent(self.root)
        self.assertEqual(selection['parent'], 'C1')
        self.assertFalse(selection['cost_tiebreak_used'])
        self.assertEqual(len(selection['results_sha256']), 40)

    def test_unknown_cost_tie_prefers_simpler_parent_without_efficiency_claim(self):
        self.records(failures=5, unknown=True)
        self.records('C1', failures=5)
        selection = selected_parent(self.root)
        self.assertEqual(selection['parent'], 'C0')
        self.assertFalse(selection['cost_tiebreak_used'])
        self.assertFalse(selection['summaries']['C0']['efficiency_win_claimed'])

    def test_interrupted_attempt_and_unregistered_task_not_replayed(self):
        private_directory(self.runtime / 'scored-trials' / self.block['cells'][0]['trial_id'])
        done, partial = audited(self.root)
        self.assertFalse(done)
        self.assertEqual(len(partial), 1)
        with patch('portable_custom_study.qualified', return_value=self.proof):
            with self.assertRaises(ValueError): register(self.root, 'C0')
        private_directory(self.runtime / 'scored-trials/foreign-attempt')
        with self.assertRaises(ValueError): audited(self.root)

    def test_unclean_or_wrong_protocol_result_rejected(self):
        self.records()
        path = self.runtime / 'scored-trials' / self.block['cells'][0]['trial_id'] / 'result.json'
        original = json.loads(path.read_text())
        for changed in ({'model_revoked': False}, {'containers_removed': False},
                {'custom_registration_sha256': 'b' * 64}, {'stage': 'final'}):
            path.write_text(json.dumps(original | changed))
            with self.assertRaises(ValueError): audited(self.root)


class CustomDispatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_scored_runner_requires_new_admission_before_any_host_action(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch('portable_custom_study.admit_trial', side_effect=ValueError('no native qualification')) as admission, \
                 patch('scored_trial.check_host') as host:
                with self.assertRaisesRegex(ValueError, 'no native qualification'):
                    await run_trial(root=root, trial_id='candidate', task_id='fixture', stage='development',
                        agent_factory=agent_factory(root, 'C0'), gateway_image='image', guard_image='guard',
                        model_settings=SETTINGS, setup_timeout_seconds=900,
                        accounting_mode='provider-credit-only', custom_study=EXPERIMENT)
                admission.assert_called_once()
                host.assert_not_called()

    async def test_dispatch_skips_retained_zero_and_runs_only_missing_cell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, block, proof = fixture(root)
            # Bounded dispatcher fixture; the real admission tests above
            # separately require exactly twenty registered tasks.
            block['cells'] = block['cells'][:2]
            complete = {block['cells'][0]['trial_id']: dict(reward=0)}
            proof |= dict(gateway_image='image', guard_image='guard', setup_timeout_seconds=900)
            block['qualification_sha256'] = fingerprint(proof)
            async def execute(**kwargs):
                value = dict(model_revoked=True, containers_removed=True, networks_removed=True,
                    volumes_removed=True, status='verified')
                complete[kwargs['trial_id']] = value
                self.assertEqual(kwargs['custom_study'], EXPERIMENT)
                self.assertEqual(kwargs['stage'], 'development')
                return value
            with patch('run_portable_custom.audited', side_effect=lambda root: (complete.copy(), [])), \
                 patch('run_portable_custom.pending_stops', return_value=[]), \
                 patch('run_portable_custom.qualified', return_value=proof), \
                 patch('run_portable_custom.Clock', Clock), \
                 patch('run_portable_custom.summary', return_value={'attempted': 2}), \
                 patch('run_portable_custom.run_trial', side_effect=execute) as runner, patch('builtins.print'):
                await dispatch(root, block)
                runner.assert_awaited_once()
                self.assertEqual(runner.call_args.kwargs['trial_id'], block['cells'][1]['trial_id'])

    async def test_dispatch_does_not_launch_on_partial_or_provider_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, block, _ = fixture(root)
            for partial, stops in ((['started'], []), ([], ['credit_exhausted'])):
                with patch('run_portable_custom.audited', return_value=({}, partial)), \
                     patch('run_portable_custom.pending_stops', return_value=stops), \
                     patch('run_portable_custom.run_trial') as runner:
                    with self.assertRaises(ValueError): await dispatch(root, block)
                    runner.assert_not_called()


if __name__ == '__main__': unittest.main()

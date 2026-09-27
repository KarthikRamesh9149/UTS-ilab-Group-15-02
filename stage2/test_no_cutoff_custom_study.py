"""Locked dispatch/admission tests with synthetic results, not paid evidence."""
import asyncio
from contextlib import ExitStack, contextmanager
from copy import deepcopy
import fcntl
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import no_cutoff_custom_policy as policy
import no_cutoff_custom_study as study
import run_no_cutoff_custom as runner
from no_cutoff_custom_agent import agent_factory
from custom_dispatch_stop import BoundaryStop
from local_trace import observation
from scored_trial import run_trial
from scored_gateway import private_directory, durable_json
from test_no_cutoff_custom_policy import Fixture
from test_retry_gateway import Clock


class StudyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, folder.name); self.root = self.f.root
        self.auth = {'synthetic': True}

    def test_source_bound_qualification_rechecks_original_and_current_host(self):
        with patch.object(study.original, 'recheck') as old, patch.object(study.runtime_identity, 'verify_current') as current:
            self.assertEqual(study.qualified(self.root), self.f.proof)
            old.assert_called_once_with(self.root, self.f.document, self.auth)
            current.assert_called_once()
        self.f.proof['original_authentication_sha256'] = '1' * 64; self.f.write()
        with self.assertRaises(ValueError): study.qualified(self.root)

    def test_native_proof_never_skips_live_original_or_runtime_rechecks(self):
        for name in ('original', 'runtime'):
            with patch.object(study.original, 'recheck', side_effect=ValueError('original changed') if name == 'original' else None), \
                    patch.object(study.runtime_identity, 'verify_current', side_effect=ValueError('runtime changed') if name == 'runtime' else None):
                with self.subTest(check=name), self.assertRaises(ValueError): study.qualified(self.root)

    def test_immutable_registration_requires_matching_fresh_authentication(self):
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.original, 'recheck'):
            self.assertEqual(study.register(self.root, self.auth), self.f.block)
            self.assertEqual(study.register(self.root, self.auth), self.f.block)
            with self.assertRaises(ValueError): study.register(self.root, {'synthetic': False})
            policy.block_path(self.f.rt).write_text(json.dumps(self.f.block | {'parent': 'C3'}))
            with self.assertRaises(ValueError): study.register(self.root, self.auth)

    def test_admission_requires_transient_permit_and_exact_factory(self):
        cell = self.f.block['cells'][0]
        args = dict(trial_id=cell['trial_id'], task_id=cell['task_id'], stage='development',
            factory=agent_factory(self.root, 'C0'), settings=policy.SETTINGS,
            gateway_image=self.f.proof['gateway_image'], guard_image=self.f.proof['guard_image'])
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.original, 'recheck'):
            with self.assertRaises(ValueError): study.admit_trial(self.root, **args)
            with study.dispatch_permit(self.root, self.f.block, self.auth):
                self.assertEqual(study.admit_trial(self.root, **args), policy.fingerprint(self.f.block))
                for change in ({'stage': 'final'}, {'factory': agent_factory(self.root, 'C1')},
                        {'task_id': 'outside-fixed20'}, {'gateway_image': 'mutable:tag'}):
                    with self.subTest(change=change), self.assertRaises(ValueError): study.admit_trial(self.root, **(args | change))
            with self.assertRaises(ValueError): study.admit_trial(self.root, **args)

    def test_attempt_directory_without_result_is_retained_not_replayed(self):
        cell = self.f.block['cells'][0]
        private_directory(self.f.rt / 'scored-trials' / cell['trial_id'])
        complete, partial = study.audited(self.root)
        self.assertFalse(complete); self.assertEqual(partial, [cell['trial_id']])
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.original, 'recheck'):
            with self.assertRaises(ValueError): study.register(self.root, self.auth)

    def result(self, cell, reward):
        folder = private_directory(self.f.rt / 'scored-trials' / cell['trial_id'])
        result = dict(cell, stage='development', custom_study=policy.EXPERIMENT, status='verified',
            model_revoked=True, containers_removed=True, networks_removed=True, volumes_removed=True,
            custom_registration_sha256=policy.fingerprint(self.f.block), accounting_mode='provider-credit-only',
            model_protocol_sha256=policy.SETTINGS.fingerprint(), phase_seconds={'agent': 25.},
            verifier_result={'rewards': {'reward': reward}})
        durable_json(folder / 'result.json', result)
        return folder, result

    def test_zero_and_missing_rewards_are_not_parent_score_or_free_execution(self):
        self.result(self.f.block['cells'][0], 0)
        self.result(self.f.block['cells'][1], None)
        bill = dict(requests=1, unknown_cost_requests=1, known_charged_usd='0.1', charged_usd=None)
        with patch.object(study, 'billing_summary', return_value=bill):
            value = study.summary(self.root)
        self.assertEqual((value['attempted'], value['passes'], value['failures'], value['no_verifier_result']), (2, 0, 1, 1))
        self.assertEqual(value['known_charged_usd'], '0.2'); self.assertIsNone(value['charged_usd'])
        self.assertIsNone(value['agent_seconds']); self.assertFalse(value['original_score_inherited'])

    def test_result_identity_revocation_and_cleanup_tampering_block(self):
        folder, result = self.result(self.f.block['cells'][0], 0)
        for changes in ({'model_revoked': False}, {'custom_study': 'old-c0'}, {'containers_removed': False},
                {'custom_registration_sha256': '1' * 64}, {'harness': 'C0'},
                {'agent_context': {'metadata': {'custom_version': 'stage2-candidate-0.3.0'}}}):
            (folder / 'result.json').write_text(json.dumps(result | changes))
            with self.subTest(changes=changes), self.assertRaises(ValueError): study.audited(self.root)

    def test_running_container_image_checked_again_after_start(self):
        name = self.f.tasks[0]
        (self.f.rt / policy.RUNTIME_FILE).write_text(json.dumps({'task_inventory': {name: {'image_id': 'sha256:fixed'}}}))
        study.require_task_image(self.root, name, 'sha256:fixed')
        with self.assertRaises(ValueError): study.require_task_image(self.root, name, 'sha256:changed')

    def test_trace_accepts_only_explicit_revision_not_arbitrary_variants(self):
        args = dict(trial_id=self.f.block['cells'][0]['trial_id'], task_id=self.f.tasks[0],
            protocol_sha256=policy.SETTINGS.fingerprint(), kind='verifier', sequence=0,
            started_ns=1, ended_ns=2, reward=0)
        self.assertEqual(observation(**args, harness='C0-NC')['reward'], 0)
        for name in ('C1-NC', 'C2-NC', 'C3-NC'):
            with self.assertRaises(ValueError): observation(**args, harness=name)

    def test_every_ancestor_including_completed_c3_r2_is_locked(self):
        calls = []
        def record(stack, runtime, name): calls.append((runtime, name))
        with ExitStack() as stack, patch('run_deadline_custom.hold', side_effect=record), patch.object(runner, 'hold', side_effect=record):
            runner.lock_all(stack, self.root)
        for root in ('/opt/uts-capstone-custom-development-20260926', '/opt/uts-capstone-custom-portable-20260926',
                     '/opt/uts-capstone-custom-deadline-20260927', '/opt/uts-capstone-custom-deadline-20260927-r2'):
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                self.assertIn((Path(root) / '.runtime/stage2', name), calls)
        self.assertEqual(calls.count((self.f.rt, 'matrix.lock')), 1)


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, folder.name); self.root = self.f.root

    async def test_scored_entry_routes_to_new_admission_before_host_work(self):
        cell = self.f.block['cells'][0]
        with patch.object(study, 'admit_trial', side_effect=ValueError('not qualified')) as admit, \
                patch('scored_trial.check_host') as host:
            with self.assertRaises(ValueError):
                await run_trial(root=self.root, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='development',
                    agent_factory=agent_factory(self.root, 'C0'), gateway_image='bad', guard_image='bad',
                    setup_timeout_seconds=900, model_settings=policy.SETTINGS,
                    accounting_mode='provider-credit-only', custom_study=policy.EXPERIMENT)
            admit.assert_called_once(); host.assert_not_called()

    async def test_persistent_stop_is_checked_before_authentication_or_dispatch(self):
        durable_json(self.f.rt / 'operator-stop-request.json', {'automatic_resume': False})
        with patch.object(runner.original, 'authenticate') as auth, patch.object(runner, 'audited') as audit:
            with self.assertRaises(ValueError): await runner.run(self.root)
            await runner.dispatch(self.root, self.f.block)
            auth.assert_not_called(); audit.assert_not_called()

    async def test_all_complete_never_replayed_and_partial_never_restarted(self):
        for completed, partial in (({r['trial_id']: {} for r in self.f.block['cells']}, []), ({}, ['started'])):
            with patch.object(runner, 'audited', return_value=(completed, partial)), \
                    patch.object(runner, 'pending_stops', return_value=[]), patch.object(runner, 'run_trial', new_callable=AsyncMock) as run:
                if partial:
                    with self.assertRaises(ValueError): await runner.dispatch(self.root, self.f.block)
                else: await runner.dispatch(self.root, self.f.block)
                run.assert_not_awaited()

    async def test_original_authentication_precedes_locks_then_recheck_and_dispatch(self):
        events = []
        def step(name, result=None):
            def call(*args): events.append(name); return result
            return call
        @contextmanager
        def permit(*args): events.append('permit'); yield
        with patch.object(runner.original, 'authenticate', side_effect=step('authenticate', {'fresh': True})), \
                patch.object(runner, 'lock_all', side_effect=step('locks')), \
                patch.object(runner.original, 'recheck', side_effect=step('recheck')), \
                patch.object(runner, 'docker', return_value=''), \
                patch.object(runner, 'register', side_effect=step('register', self.f.block)), \
                patch.object(runner, 'dispatch_permit', permit), \
                patch.object(runner, 'dispatch', new_callable=AsyncMock) as dispatch:
            await runner.run(self.root)
            self.assertEqual(events, ['authenticate', 'locks', 'recheck', 'register', 'permit'])
            dispatch.assert_awaited_once()

    async def test_real_held_lock_prevents_registration_and_dispatch(self):
        from run_credit_only import hold
        with (self.f.rt / 'matrix.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(runner.original, 'authenticate', return_value={'fresh': True}), \
                    patch.object(runner, 'lock_all', side_effect=lambda stack, root: hold(stack, self.f.rt, 'matrix.lock')), \
                    patch.object(runner, 'register') as register, patch.object(runner, 'run_trial', new_callable=AsyncMock) as trial:
                with self.assertRaises(BlockingIOError): await runner.run(self.root)
                register.assert_not_called(); trial.assert_not_awaited()

    async def test_owned_stopped_container_blocks_new_launch(self):
        with patch.object(runner.original, 'authenticate', return_value={'fresh': True}), \
                patch.object(runner.original, 'recheck'), patch.object(runner, 'lock_all'), \
                patch.object(runner, 'docker', return_value='owned-container'), patch.object(runner, 'register') as register:
            with self.assertRaises(ValueError): await runner.run(self.root)
            register.assert_not_called()

    async def test_unknown_cost_and_failure_do_not_retry_final_cell_and_signal_persists(self):
        block = self.f.block; last = block['cells'][-1]
        before = {c['trial_id']: {} for c in block['cells'][:-1]}
        after = dict(before, **{last['trial_id']: {}})
        stop = BoundaryStop(self.f.rt)
        async def execute(**kwargs):
            self.assertEqual(kwargs['trial_id'], last['trial_id'])
            self.assertEqual(kwargs['stage'], 'development')
            self.assertEqual(kwargs['custom_study'], policy.EXPERIMENT)
            self.assertEqual(kwargs['agent_factory'].harness, 'C0-NC')
            stop.signalled = True
            return dict(status='verified', containers_removed=True, networks_removed=True,
                volumes_removed=True, model_revoked=True, verifier_result={'rewards': {'reward': 0}})
        with patch.object(runner, 'audited', side_effect=[(before, []), (after, [])]), \
                patch.object(runner, 'Clock', Clock), \
                patch.object(runner, 'pending_stops', return_value=[]), patch.object(runner, 'qualified', return_value=self.f.proof), \
                patch.object(runner, 'run_trial', side_effect=execute) as trial, \
                patch.object(runner, 'summary', return_value={'attempted': 20, 'charged_usd': None, 'passes': 0, 'rows': []}):
            await runner.dispatch(self.root, block, stop=stop)
            trial.assert_awaited_once()
        self.assertTrue(stop.marker.is_file())
        self.assertFalse(json.loads(stop.marker.read_text())['automatic_resume'])

    async def test_provider_stop_prevents_next_call_without_treating_unknown_cost_as_stop(self):
        with patch.object(runner, 'audited', return_value=({}, [])), \
                patch.object(runner, 'pending_stops', return_value=['real-provider-stop']), \
                patch.object(runner, 'run_trial', new_callable=AsyncMock) as trial:
            with self.assertRaises(ValueError): await runner.dispatch(self.root, self.f.block)
            trial.assert_not_awaited()


class ScoredIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, *, wrong_image=False):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        f = Fixture(self, folder.name); cell = f.block['cells'][0]
        (f.root / 'stage2').mkdir()
        (f.root / 'stage2/input_manifest.json').write_text(json.dumps({'development_ids': f.tasks}))
        events = []
        expected_image = 'sha256:' + '9' * 64
        (f.rt / policy.RUNTIME_FILE).write_text(json.dumps({'task_inventory': {
            cell['task_id']: {'image_id': expected_image}}}))
        task = NS(paths=NS(environment_dir=f.root), has_steps=False, instruction='Synthetic fixture only',
            config=NS(environment=NS(network_mode=NS(value='public'), build_timeout_sec=10),
                agent=NS(network_mode=None, timeout_sec=180),
                verifier=NS(network_mode=None, environment=None)))
        class Environment:
            def __init__(self, **kwargs): pass
            async def start(self, **kwargs): events.append('start')
            async def stop(self, **kwargs): events.append('cleanup')
            async def stop_service(self, name): events.append('revoke')
        class Bridge:
            base_url = 'http://127.0.0.1:1234/v1'
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        def service(project, name):
            return dict(Id='a' * 64, State={'Running': False}, Image=(
                'sha256:' + '0' * 64 if wrong_image else expected_image) if name == 'main' else f.proof['gateway_image'])
        async def phases(**kwargs):
            await kwargs['revoke_model']()
            events.append('verify')
            observer = kwargs['phase_observer']
            self.assertIsNotNone(observer)
            observer(kind='verifier', started_ns=1, ended_ns=2, seconds=0.000000001, status='ok', reward=0)
            observer(kind='trial', started_ns=0, ended_ns=3, seconds=0.000000003, status='ok')
            return dict(status='verified', model_revoked=True, phase_seconds={'agent': 0.1},
                verifier_result={'rewards': {'reward': 0}})
        with ExitStack() as stack:
            stack.enter_context(patch.object(study, 'qualified', return_value=f.proof))
            stack.enter_context(patch.object(study.original, 'recheck'))
            stack.enter_context(study.dispatch_permit(f.root, f.block, {'synthetic': True}))
            stack.enter_context(patch('harbor.models.task.task.Task', return_value=task))
            stack.enter_context(patch('pinned_docker.PinnedImageDockerEnvironment', Environment))
            for name, value in dict(check_host=lambda: {}, frozen_dataset=lambda root: root,
                    audit_task=lambda *args: None, compose_runtime=lambda **kwargs: {}, service=service,
                    HostModelBridge=Bridge, execute_phases=phases, docker=lambda *args: '').items():
                stack.enter_context(patch('scored_trial.' + name, value))
            args = dict(root=f.root, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='development',
                agent_factory=agent_factory(f.root, 'C0'), gateway_image=f.proof['gateway_image'],
                guard_image=f.proof['guard_image'], setup_timeout_seconds=900, model_settings=policy.SETTINGS,
                accounting_mode='provider-credit-only', custom_study=policy.EXPERIMENT)
            if wrong_image:
                with self.assertRaises(ValueError): await run_trial(**args)
            else:
                result = await run_trial(**args)
                with self.assertRaises(FileExistsError): await run_trial(**args)
            result = json.loads((f.rt / 'scored-trials' / cell['trial_id'] / 'result.json').read_text())
        return result, events

    async def test_actual_admission_and_trace_hooks_connect_to_scored_lifecycle(self):
        result, events = await self.run_case()
        self.assertEqual(result['harness'], 'C0-NC')
        self.assertEqual(result['trace']['status'], 'metadata_spool_not_cloud_export')
        self.assertEqual(result['trace']['events'], 2)
        self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
        self.assertLess(events.index('revoke'), events.index('verify'))
        self.assertTrue(all(result[key] for key in ('containers_removed', 'networks_removed', 'volumes_removed')))

    async def test_changed_container_image_stops_before_agent_and_retains_cleanup(self):
        result, events = await self.run_case(wrong_image=True)
        self.assertEqual(result['status'], 'infrastructure_failed')
        self.assertNotIn('verify', events)
        self.assertIn('cleanup', events)
        self.assertNotIn('model_revoked', result)  # Never invent missing phase evidence.


if __name__ == '__main__':
    unittest.main()

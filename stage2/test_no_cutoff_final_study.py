"""Final dispatch and scored hooks with mocked hosts, not native qualification."""
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

import no_cutoff_final_policy as policy
import no_cutoff_final_study as study
import run_no_cutoff_final as runner
from no_cutoff_custom_agent import agent_factory
from custom_dispatch_stop import BoundaryStop
from local_trace import observation
from scored_trial import run_trial
from scored_gateway import private_directory, durable_json
from test_no_cutoff_final_policy import Fixture as PolicyFixture
from test_retry_gateway import Clock


class Fixture(PolicyFixture):
    def __init__(self, owner, root):
        super().__init__(owner, root)
        self.auth = {'synthetic_final_authentication_not_native': True}
        self.proof['finalist_authentication_sha256'] = policy.fingerprint(self.auth)
        self.block = policy.registration(self.document, self.manifest, self.proof)
        self.write()
        durable_json(self.runtime / policy.AUTHENTICATION_FILE, self.auth)
        durable_json(self.runtime / policy.RUNTIME_FILE, {'synthetic_current_final_host': True})


def retained(f, cell, reward=0):
    folder = private_directory(f.runtime / 'scored-trials' / cell['trial_id'])
    value = dict(cell, custom_study=policy.EXPERIMENT, status='verified', model_revoked=True,
        containers_removed=True, networks_removed=True, volumes_removed=True,
        custom_registration_sha256=policy.fingerprint(f.block), gateway_image_id=f.proof['gateway_image'],
        accounting_mode='provider-credit-only', model_protocol_sha256=policy.SETTINGS.fingerprint(),
        phase_seconds={'agent': 25.}, verifier_result={'rewards': {'reward': reward}})
    durable_json(folder / 'result.json', value)
    return folder, value


class StudyTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, Path(folder.name).resolve()); self.root = self.f.root
        self.auth = self.f.auth

    def test_qualification_rechecks_all_measured_evidence_and_current_host(self):
        with patch.object(study.evidence, 'recheck') as measured, \
                patch.object(study.evidence, 'authenticate') as fresh, \
                patch.object(study.runtime_identity, 'verify_current') as current:
            self.assertEqual(study.qualified(self.root), self.f.proof)
            measured.assert_called_once_with(self.root, self.f.document, self.auth)
            current.assert_called_once_with(self.root, self.f.document, self.f.proof,
                {'synthetic_current_final_host': True})
            fresh.assert_not_called()  # No recursive collector while ancestor locks are held.
        self.f.proof['finalist_authentication_sha256'] = '1' * 64; self.f.write()
        with self.assertRaises(ValueError): study.qualified(self.root)

    def test_saved_proof_cannot_skip_measured_evidence_or_native_runtime(self):
        for name in ('evidence', 'runtime'):
            with patch.object(study.evidence, 'recheck', side_effect=ValueError('changed') if name == 'evidence' else None), \
                    patch.object(study.runtime_identity, 'verify_current', side_effect=ValueError('changed') if name == 'runtime' else None):
                with self.subTest(check=name), self.assertRaises(ValueError): study.qualified(self.root)

    def test_operator_stop_precedes_qualification(self):
        durable_json(self.f.runtime / 'operator-stop-request.json', {'automatic_resume': False})
        with patch.object(study.evidence, 'recheck') as check, self.assertRaises(ValueError):
            study.qualified(self.root)
        check.assert_not_called()

    def test_immutable_registration_requires_the_fresh_matching_record(self):
        path = self.f.runtime / policy.REGISTRATION_FILE
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.evidence, 'recheck'):
            original = path.read_bytes()
            self.assertEqual(study.register(self.root, self.auth), self.f.block)
            self.assertEqual(path.read_bytes(), original)
            with self.assertRaises(ValueError): study.register(self.root, {'synthetic': False})
            path.write_text(json.dumps(self.f.block | {'condition': 'C0'}))
            with self.assertRaises(ValueError): study.register(self.root, self.auth)

    def test_new_registration_preserves_89_cells_and_private_permissions(self):
        path = self.f.runtime / policy.REGISTRATION_FILE
        path.unlink()  # Only the synthetic fixture's registry is removed.
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.evidence, 'recheck'):
            block = study.register(self.root, self.auth)
        self.assertEqual(block, self.f.block); self.assertEqual(len(block['cells']), 89)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_unregistered_or_partial_attempt_blocks_registration_without_replay(self):
        cell = self.f.block['cells'][0]
        private_directory(self.f.runtime / 'scored-trials' / cell['trial_id'])
        complete, partial = study.audited(self.root)
        self.assertFalse(complete); self.assertEqual(partial, [cell['trial_id']])
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.evidence, 'recheck'):
            with self.assertRaises(ValueError): study.register(self.root, self.auth)
        private_directory(self.f.runtime / 'scored-trials' / 'customdev4-c0-nc-unregistered')
        with self.assertRaises(ValueError): study.audited(self.root)

    def test_transient_permit_does_not_come_from_saved_registration(self):
        cell = self.f.block['cells'][0]
        args = dict(trial_id=cell['trial_id'], task_id=cell['task_id'], stage='final',
            factory=agent_factory(self.root, 'C0'), settings=policy.SETTINGS,
            gateway_image=self.f.proof['gateway_image'], guard_image=self.f.proof['guard_image'],
            setup_timeout_seconds=900)
        with patch.object(study, 'qualified', return_value=self.f.proof), patch.object(study.evidence, 'recheck'):
            with self.assertRaises(ValueError): study.admit_trial(self.root, **args)
            with study.dispatch_permit(self.root, self.f.block, self.auth):
                self.assertEqual(study.admit_trial(self.root, **args), policy.fingerprint(self.f.block))
                for change in ({'stage': 'development'}, {'factory': agent_factory(self.root, 'C1')},
                        {'task_id': 'outside-final89'}, {'gateway_image': 'mutable:tag'},
                        {'guard_image': 'mutable:tag'}, {'setup_timeout_seconds': 100},
                        {'trial_id': 'synthetic-nc-final-tools'}):
                    with self.subTest(change=change), self.assertRaises(ValueError):
                        study.admit_trial(self.root, **(args | change))
            with self.assertRaises(ValueError): study.admit_trial(self.root, **args)

    def test_permit_is_reset_on_exception_and_rejects_changed_or_old_record(self):
        with patch.object(study.evidence, 'recheck'):
            with self.assertRaises(RuntimeError):
                with study.dispatch_permit(self.root, self.f.block, self.auth):
                    raise RuntimeError('synthetic')
            self.assertIsNone(study._DISPATCH.get())
            for block, auth in ((self.f.block, {}), (dict(self.f.block, intended=20), self.auth)):
                with self.assertRaises(ValueError), study.dispatch_permit(self.root, block, auth): pass

    def test_zeros_missing_outcomes_and_unknown_costs_are_retained(self):
        retained(self.f, self.f.block['cells'][0], 0)
        retained(self.f, self.f.block['cells'][1], None)
        bill = dict(requests=1, unknown_cost_requests=1, known_charged_usd='0.1', charged_usd=None)
        with patch.object(study, 'billing_summary', return_value=bill): value = study.summary(self.root)
        self.assertEqual((value['intended'], value['attempted'], value['passes'], value['failures'],
            value['no_verifier_result']), (89, 2, 0, 1, 1))
        self.assertEqual(value['known_charged_usd'], '0.2'); self.assertIsNone(value['charged_usd'])
        self.assertIsNone(value['agent_seconds']); self.assertFalse(value['original_score_inherited'])
        self.assertEqual(value['confirmation60_status'], 'deferred_not_run')
        self.assertEqual(value['diagnostic20_status'], 'deferred_not_run')

    def test_all_failures_remain_complete_not_a_new_selection_or_score_floor(self):
        for cell in self.f.block['cells']: retained(self.f, cell, 0)
        bill = dict(requests=1, unknown_cost_requests=1, known_charged_usd='0', charged_usd=None)
        with patch.object(study, 'billing_summary', return_value=bill): value = study.summary(self.root)
        self.assertEqual((value['attempted'], value['passes'], value['failures']), (89, 0, 89))
        self.assertEqual(len(value['rows']), 89); self.assertEqual(value['agent_seconds'], 2225.)
        self.assertIsNone(value['charged_usd']); self.assertFalse(value['full_benchmark_win_claimed'])

    def test_result_identity_revocation_and_cleanup_changes_block(self):
        folder, result = retained(self.f, self.f.block['cells'][0])
        for changes in ({'stage': 'development'}, {'model_revoked': False}, {'custom_study': 'old-c0'},
                {'containers_removed': False}, {'custom_registration_sha256': '1' * 64},
                {'gateway_image_id': 'sha256:changed'}, {'harness': 'C0'},
                {'agent_context': {'metadata': {'custom_version': 'stage2-candidate-0.3.0'}}}):
            (folder / 'result.json').write_text(json.dumps(result | changes))
            with self.subTest(changes=changes), self.assertRaises(ValueError): study.audited(self.root)

    def test_invalid_reward_and_runtime_are_not_coerced_to_valid_observations(self):
        folder, result = retained(self.f, self.f.block['cells'][0])
        for changes in ({'verifier_result': {'rewards': {'reward': True}}},
                {'verifier_result': {'rewards': {'reward': 0.5}}}, {'phase_seconds': {'agent': -1}}):
            (folder / 'result.json').write_text(json.dumps(result | changes))
            with self.assertRaises(ValueError): study.summary(self.root)

    def test_running_container_image_checked_again_after_start(self):
        name = self.f.block['cells'][-1]['task_id']
        (self.f.runtime / policy.RUNTIME_FILE).write_text(json.dumps({'task_inventory': {name: {'image_id': 'sha256:fixed'}}}))
        study.require_task_image(self.root, name, 'sha256:fixed')
        with self.assertRaises(ValueError): study.require_task_image(self.root, name, 'sha256:changed')
        with self.assertRaises(ValueError): study.require_task_image(self.root, 'unregistered', 'sha256:fixed')

    def test_existing_trace_contract_accepts_final_identity_without_code_change(self):
        cell = self.f.block['cells'][0]
        args = dict(trial_id=cell['trial_id'], task_id=cell['task_id'], protocol_sha256=policy.SETTINGS.fingerprint(),
            kind='verifier', sequence=0, started_ns=1, ended_ns=2, reward=0)
        self.assertEqual(observation(**args, harness='C0-NC')['reward'], 0)
        for name in ('C1-NC', 'C2-NC', 'C3-NC'):
            with self.assertRaises(ValueError): observation(**args, harness=name)

    def test_every_ancestor_including_revision_is_locked_once(self):
        calls = []
        def record(stack, runtime, name): calls.append((runtime, name))
        with ExitStack() as stack, patch('run_deadline_custom.hold', side_effect=record), \
                patch('run_no_cutoff_custom.hold', side_effect=record), patch.object(runner, 'hold', side_effect=record):
            runner.lock_all(stack, self.root)
        for root in ('/opt/uts-capstone-custom-development-20260926', '/opt/uts-capstone-custom-portable-20260926',
                     '/opt/uts-capstone-custom-deadline-20260927', '/opt/uts-capstone-custom-deadline-20260927-r2',
                     '/opt/uts-capstone-custom-no-cutoff-20260928'):
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                self.assertEqual(calls.count((Path(root) / '.runtime/stage2', name)), 1)
        self.assertEqual(calls.count((self.f.runtime, 'matrix.lock')), 1)
        self.assertNotIn((self.f.runtime, 'scored.lock'), calls)  # run_trial owns this.
        self.assertNotIn((self.f.runtime, 'gateway.lock'), calls)  # Gateway session owns this.
        self.assertEqual(len(calls), len(set(calls)))

    def test_final_cannot_lock_as_an_original_or_revision_root(self):
        for root in (study.evidence.CURRENT, *study.evidence.original.ROOTS.values()):
            with ExitStack() as stack, self.subTest(root=root), self.assertRaises(ValueError):
                runner.lock_all(stack, root)


class DispatchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        self.f = Fixture(self, Path(folder.name).resolve()); self.root = self.f.root
        self.patch = patch.object(runner, 'DEPLOYMENT', self.root); self.patch.start(); self.addCleanup(self.patch.stop)

    async def test_scored_entry_routes_to_final_admission_before_host_work(self):
        cell = self.f.block['cells'][0]
        with patch.object(study, 'admit_trial', side_effect=ValueError('not qualified')) as admit, \
                patch('scored_trial.check_host') as host:
            with self.assertRaises(ValueError):
                await run_trial(root=self.root, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='final',
                    agent_factory=agent_factory(self.root, 'C0'), gateway_image='bad', guard_image='bad',
                    setup_timeout_seconds=900, model_settings=policy.SETTINGS,
                    accounting_mode='provider-credit-only', custom_study=policy.EXPERIMENT)
            admit.assert_called_once(); host.assert_not_called()
            self.assertEqual(admit.call_args.kwargs['setup_timeout_seconds'], 900)

    async def test_wrong_final_deployment_is_refused_before_authentication(self):
        with patch.object(runner.evidence, 'authenticate') as auth, self.assertRaises(ValueError):
            await runner.run(self.root / 'other')
        auth.assert_not_called()

    async def test_persistent_stop_precedes_authentication_or_dispatch(self):
        durable_json(self.f.runtime / 'operator-stop-request.json', {'automatic_resume': False})
        with patch.object(runner.evidence, 'authenticate') as auth, patch.object(runner, 'audited') as audit:
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

    async def test_fresh_native_authentication_precedes_locks_and_dispatch(self):
        events = []
        def step(name, result=None):
            def call(*args): events.append(name); return result
            return call
        @contextmanager
        def permit(*args): events.append('permit'); yield
        with patch.object(runner.evidence, 'authenticate', side_effect=step('authenticate', self.f.auth)) as auth, \
                patch.object(runner, 'lock_all', side_effect=step('locks')), \
                patch.object(runner.evidence, 'recheck', side_effect=step('recheck')), \
                patch.object(runner, 'docker', return_value=''), \
                patch.object(runner, 'register', side_effect=step('register', self.f.block)), \
                patch.object(runner, 'dispatch_permit', permit), \
                patch.object(runner, 'dispatch', new_callable=AsyncMock) as dispatch:
            await runner.run(self.root)
            self.assertEqual(events, ['authenticate', 'locks', 'recheck', 'register', 'permit'])
            auth.assert_called_once_with(self.root, self.f.document); dispatch.assert_awaited_once()

    async def test_failed_fresh_native_audit_does_not_take_locks_or_use_saved_record(self):
        with patch.object(runner.evidence, 'authenticate', side_effect=ValueError('active or changed')) as auth, \
                patch.object(runner, 'lock_all') as locks, patch.object(runner, 'register') as register:
            with self.assertRaises(ValueError): await runner.run(self.root)
            auth.assert_called_once(); locks.assert_not_called(); register.assert_not_called()

    async def test_real_held_ancestor_lock_prevents_registration_and_dispatch(self):
        from run_credit_only import hold
        ancestor = private_directory(self.root / 'synthetic-ancestor')
        with (ancestor / 'matrix.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch.object(runner.evidence, 'authenticate', return_value=self.f.auth), \
                    patch.object(runner, 'lock_all', side_effect=lambda stack, root: hold(stack, ancestor, 'matrix.lock')), \
                    patch.object(runner, 'register') as register, patch.object(runner, 'run_trial', new_callable=AsyncMock) as trial:
                with self.assertRaises(BlockingIOError): await runner.run(self.root)
                register.assert_not_called(); trial.assert_not_awaited()

    async def test_under_lock_drift_and_owned_stopped_container_prevent_launch(self):
        for drift in (True, False):
            with patch.object(runner.evidence, 'authenticate', return_value=self.f.auth), \
                    patch.object(runner.evidence, 'recheck', side_effect=ValueError('changed') if drift else None), \
                    patch.object(runner, 'lock_all'), patch.object(runner, 'docker', return_value='owned-container'), \
                    patch.object(runner, 'register') as register:
                with self.assertRaises(ValueError): await runner.run(self.root)
                register.assert_not_called()

    async def test_unknown_cost_and_failure_do_not_retry_last_cell_and_signal_persists(self):
        block = self.f.block; last = block['cells'][-1]
        before = {c['trial_id']: {} for c in block['cells'][:-1]}; after = dict(before, **{last['trial_id']: {}})
        stop = BoundaryStop(self.f.runtime)
        async def execute(**kwargs):
            self.assertEqual(kwargs['trial_id'], last['trial_id']); self.assertEqual(kwargs['stage'], 'final')
            self.assertEqual(kwargs['custom_study'], policy.EXPERIMENT)
            self.assertEqual(kwargs['agent_factory'].custom_version, policy.CANDIDATE_VERSION)
            self.assertEqual(kwargs['agent_factory'].custom_parent, 'C0')
            self.assertEqual(kwargs['accounting_mode'], 'provider-credit-only')
            stop.signalled = True
            return dict(status='verified', containers_removed=True, networks_removed=True,
                volumes_removed=True, model_revoked=True, verifier_result={'rewards': {'reward': 0}})
        with patch.object(runner, 'audited', side_effect=[(before, []), (after, [])]), \
                patch.object(runner, 'Clock', Clock), patch.object(runner, 'pending_stops', return_value=[]), \
                patch.object(runner, 'qualified', return_value=self.f.proof), patch.object(runner, 'run_trial', side_effect=execute) as trial, \
                patch.object(runner, 'summary', return_value={'attempted': 89, 'charged_usd': None, 'passes': 0, 'rows': []}):
            await runner.dispatch(self.root, block, stop=stop); trial.assert_awaited_once()
        self.assertTrue(stop.marker.is_file()); self.assertFalse(json.loads(stop.marker.read_text())['automatic_resume'])

    async def test_provider_stop_prevents_next_call(self):
        with patch.object(runner, 'audited', return_value=({}, [])), \
                patch.object(runner, 'pending_stops', return_value=['real-provider-stop']), \
                patch.object(runner, 'run_trial', new_callable=AsyncMock) as trial:
            with self.assertRaises(ValueError): await runner.dispatch(self.root, self.f.block)
            trial.assert_not_awaited()

    async def test_all_89_are_sequential_rechecked_and_retained_without_score_or_cost_gate(self):
        complete, seen = {}, []
        busy = False
        async def execute(**kwargs):
            nonlocal busy
            self.assertFalse(busy); busy = True
            await asyncio.sleep(0)
            name = kwargs['trial_id']; seen.append(name)
            cell = next(c for c in self.f.block['cells'] if c['trial_id'] == name)
            result = retained(self.f, cell, None if len(seen) == 1 else 0)[1]
            complete[name] = result; busy = False
            return result
        with patch.object(runner, 'audited', side_effect=lambda root: (dict(complete), [])), \
                patch.object(runner, 'Clock', Clock), patch.object(runner, 'pending_stops', return_value=[]), \
                patch.object(runner, 'qualified', return_value=self.f.proof) as qualify, \
                patch.object(runner, 'run_trial', side_effect=execute) as trial, \
                patch.object(runner, 'summary', side_effect=lambda root: {'attempted': len(complete), 'charged_usd': None, 'rows': []}), \
                patch('builtins.print'):
            await runner.dispatch(self.root, self.f.block)
        self.assertEqual(seen, [c['trial_id'] for c in self.f.block['cells']])
        self.assertEqual(trial.await_count, 89); self.assertEqual(qualify.call_count, 89)

    async def test_dispatch_rethrows_unretained_exception_and_stops_on_cleanup_failure(self):
        for failure in (ValueError('unretained'), {'status': 'cleanup_failed'}):
            with patch.object(runner, 'audited', return_value=({}, [])), \
                    patch.object(runner, 'Clock', Clock), patch.object(runner, 'pending_stops', return_value=[]), \
                    patch.object(runner, 'qualified', return_value=self.f.proof), \
                    patch.object(runner, 'run_trial', side_effect=failure if isinstance(failure, Exception) else None,
                        return_value=failure) as trial:
                with self.assertRaises(ValueError): await runner.dispatch(self.root, self.f.block)
                trial.assert_awaited_once()

    async def test_qualification_drift_blocks_before_any_task(self):
        with patch.object(runner, 'audited', return_value=({}, [])), \
                patch.object(runner, 'pending_stops', return_value=[]), \
                patch.object(runner, 'qualified', return_value=dict(self.f.proof, status='changed')), \
                patch.object(runner, 'run_trial', new_callable=AsyncMock) as trial:
            with self.assertRaises(ValueError): await runner.dispatch(self.root, self.f.block)
            trial.assert_not_awaited()


class ScoredIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def run_case(self, *, wrong_image=False):
        folder = tempfile.TemporaryDirectory(); self.addCleanup(folder.cleanup)
        f = Fixture(self, Path(folder.name).resolve()); cell = f.block['cells'][-1]
        (f.root / 'stage2/input_manifest.json').write_text(json.dumps(f.manifest))
        events = []; expected_image = 'sha256:' + '9' * 64
        (f.runtime / policy.RUNTIME_FILE).write_text(json.dumps({'task_inventory': {cell['task_id']: {'image_id': expected_image}}}))
        task = NS(paths=NS(environment_dir=f.root), has_steps=False, instruction='Synthetic fixture only',
            config=NS(environment=NS(network_mode=NS(value='public'), build_timeout_sec=10),
                agent=NS(network_mode=None, timeout_sec=7200), verifier=NS(network_mode=None, environment=None)))
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
            self.assertEqual(kwargs['agent'].timeout, 7200)  # No independent one-hour allowance.
            self.assertEqual(kwargs['setup_timeout_seconds'], 900)
            await kwargs['revoke_model'](); events.append('verify')
            observer = kwargs['phase_observer']; self.assertIsNotNone(observer)
            observer(kind='verifier', started_ns=1, ended_ns=2, seconds=0.000000001, status='ok', reward=0)
            observer(kind='trial', started_ns=0, ended_ns=3, seconds=0.000000003, status='ok')
            return dict(status='verified', model_revoked=True, phase_seconds={'agent': 0.1},
                verifier_result={'rewards': {'reward': 0}})
        with ExitStack() as stack:
            stack.enter_context(patch.object(study, 'qualified', return_value=f.proof))
            stack.enter_context(patch.object(study.evidence, 'recheck'))
            stack.enter_context(study.dispatch_permit(f.root, f.block, f.auth))
            stack.enter_context(patch('harbor.models.task.task.Task', return_value=task))
            stack.enter_context(patch('pinned_docker.PinnedImageDockerEnvironment', Environment))
            for name, value in dict(check_host=lambda: {}, frozen_dataset=lambda root: root,
                    audit_task=lambda *args: None, compose_runtime=lambda **kwargs: {}, service=service,
                    HostModelBridge=Bridge, execute_phases=phases, docker=lambda *args: '').items():
                stack.enter_context(patch('scored_trial.' + name, value))
            args = dict(root=f.root, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='final',
                agent_factory=agent_factory(f.root, 'C0'), gateway_image=f.proof['gateway_image'],
                guard_image=f.proof['guard_image'], setup_timeout_seconds=900, model_settings=policy.SETTINGS,
                accounting_mode='provider-credit-only', custom_study=policy.EXPERIMENT)
            if wrong_image:
                with self.assertRaises(ValueError): await run_trial(**args)
            else:
                await run_trial(**args)
                with self.assertRaises(FileExistsError): await run_trial(**args)
            result = json.loads((f.runtime / 'scored-trials' / cell['trial_id'] / 'result.json').read_text())
        return result, events

    async def test_actual_final_admission_and_trace_hooks_reach_mocked_lifecycle(self):
        result, events = await self.run_case()
        self.assertEqual(result['harness'], 'C0-NC'); self.assertEqual(result['stage'], 'final')
        self.assertEqual(result['custom_study'], policy.EXPERIMENT)
        self.assertEqual(result['trace']['status'], 'metadata_spool_not_cloud_export')
        self.assertEqual(result['trace']['events'], 2); self.assertEqual(result['verifier_result']['rewards']['reward'], 0)
        self.assertLess(events.index('revoke'), events.index('verify'))
        self.assertTrue(all(result[key] for key in ('containers_removed', 'networks_removed', 'volumes_removed')))

    async def test_changed_final_image_stops_before_agent_and_retains_cleanup(self):
        result, events = await self.run_case(wrong_image=True)
        self.assertEqual(result['status'], 'infrastructure_failed'); self.assertNotIn('verify', events)
        self.assertIn('cleanup', events); self.assertNotIn('model_revoked', result)


if __name__ == '__main__':
    unittest.main()

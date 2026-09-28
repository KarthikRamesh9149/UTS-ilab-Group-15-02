"""Local synthetic qualification/readers, real locks and admission. No paid calls."""
import asyncio
from contextlib import ExitStack
import json
import os
import pickle
from pathlib import Path
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_policy as policy
import matched_repeat_session as session
import matched_repeat_study as study
import test_matched_repeat_session as fixtures
from scored_trial import run_trial


class StudyFixture(unittest.TestCase):
    def setUp(self):
        self.q = fixtures.SessionTests('runTest')
        self.q.setUp(); self.addCleanup(self.q.doCleanups)
        self.root = self.q.root; self.rt = self.root / '.runtime/stage2'
        self.q.host['task_inventory'] = {cell['task_id']: dict(agent_timeout_seconds=180.,
            image_id='sha256:' + '9' * 64) for cell in self.q.f.block['cells']}
        self.q.proof_files()
        (self.rt / policy.REGISTRATION_FILE).unlink()  # Only a temporary fabricated fixture.
        self.cells = policy.cells(self.q.f.manifest, 'terminus-2')

    def args(self, factory, index=0, **changes):
        cell = self.cells[index]
        return dict(root=self.root, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='final',
            factory=factory, settings=policy.SETTINGS, gateway_image=self.q.f.proof['gateway_image'],
            guard_image=self.q.f.proof['guard_image'], setup_timeout_seconds=900, **changes)

    def result(self, block, index=0, reward=0, **changes):
        cell = self.cells[index]
        folder = self.rt / 'scored-trials'; folder.mkdir(mode=0o700, exist_ok=True)
        folder /= cell['trial_id']; folder.mkdir(mode=0o700, exist_ok=True)
        value = dict(trial_id=cell['trial_id'], task_id=cell['task_id'], harness='terminus-2',
            stage='final', matched_repeat_experiment=policy.EXPERIMENT,
            matched_repeat_registration_sha256=policy.fingerprint(block),
            model_protocol_sha256=policy.MODEL_SHA256, accounting_mode='provider-credit-only',
            gateway_image_id=self.q.f.proof['gateway_image'], guard_image_id=self.q.f.proof['guard_image'],
            project='synthetic-owned-fixture', started_utc='2026-09-28T00:00:00Z', status='starting')
        self.q.private('scored-trials/' + cell['trial_id'] + '/started.json', value)
        value.update(status='verified', model_revoked=True, containers_removed=True,
            networks_removed=True, volumes_removed=True,
            task_image_id=self.q.host['task_inventory'][cell['task_id']]['image_id'],
            verifier_result=None if reward is None else {'rewards': {'reward': reward}},
            billing=dict(known_charged_usd='0', charged_usd=None, requests=105, unknown_cost_requests=105))
        value.update(changes)
        self.q.private('scored-trials/' + cell['trial_id'] + '/result.json', value)
        return folder / 'result.json'

    def partial(self, index=0, folder='scored-trials'):
        base = self.rt / folder; base.mkdir(mode=0o700, exist_ok=True)
        target = base / self.cells[index]['trial_id']; target.mkdir(mode=0o700, exist_ok=True)
        return target


class RegistrationTests(StudyFixture):
    def test_registration_requires_actual_live_session_not_descriptions(self):
        for value in (None, {}, session._Session(), {'paid_launch_ready': True}):
            with self.subTest(value=value), self.assertRaises(ValueError): study.register(value)
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())
        with self.q.open() as active:
            with self.assertRaises(ValueError): study.register(session.describe(active))

    def test_exclusive_registration_rechecks_real_producers_and_never_overwrites(self):
        with self.q.open() as active:
            block = study.register(active)
            path = self.rt / policy.REGISTRATION_FILE; first = path.read_bytes()
            self.assertEqual(study.register(active), block)
            self.assertEqual(first, path.read_bytes())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(block['cells'], self.cells)
            self.assertEqual(block['original_scores'], {'terminus-2': 52, 'openhands': 44})
            self.assertFalse(block['automatic_task_replay'])
            self.assertNotIn('passes', block)
        self.q.auth.assert_called_once(); self.q.old_auth.assert_called_once()
        self.q.process.assert_not_called()

    def test_changed_producer_prevents_registration_even_with_passed_flags(self):
        with self.q.open() as active:
            path = self.root / next(iter(self.q.f.proof['evidence_files']))
            path.write_bytes(b'Changed native producer fixture')
            with self.assertRaises(ValueError): study.register(active)
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())

    def test_registration_is_immutable_and_private(self):
        with self.q.open() as active:
            block = study.register(active)
            self.q.private(policy.REGISTRATION_FILE, dict(block, parallel_trials=2))
            with self.assertRaisesRegex(ValueError, 'immutable'): study.register(active)
            self.q.private(policy.REGISTRATION_FILE, block)
            (self.rt / policy.REGISTRATION_FILE).chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'private'): study.register(active)

    def test_any_unregistered_or_partial_started_key_refuses_registration(self):
        for folder in ('scored-trials', 'scored-attempts'):
            path = self.partial(folder=folder)
            with self.subTest(folder=folder), self.q.open() as active:
                with self.assertRaisesRegex(ValueError, 'Started'): study.register(active)
            path.rmdir()

    def test_a_result_does_not_allow_recreating_missing_registration(self):
        with self.q.open() as active:
            block = study.register(active)
            self.result(block)
            (self.rt / policy.REGISTRATION_FILE).unlink()
            with self.assertRaisesRegex(ValueError, 'Started'): study.register(active)

    def test_saved_session_and_openhands_remain_closed(self):
        with self.q.open() as active: study.register(active)
        with self.assertRaises(ValueError): study.register(active)
        with self.assertRaisesRegex(ValueError, 'OpenHands'):
            with self.q.open('openhands'): self.fail('Second predecessor reader is still required')

    def test_historical_transition_and_persistent_stop_refused(self):
        for name in ('accounting-runtime-transition-v1.json', 'operator-stop-request.json', 'provider-stop.json'):
            with self.subTest(name=name), self.q.open() as active:
                path = self.rt / name; path.symlink_to(self.rt / 'absent')
                with self.assertRaises(ValueError): study.register(active)
                path.unlink()


class AdmissionTests(StudyFixture):
    def test_permit_without_registration_is_not_admission(self):
        with self.q.open() as active:
            with self.assertRaises(FileNotFoundError):
                with study.dispatch_permit(active): self.fail('Registration is mandatory')

    def test_next_key_requires_scope_and_issued_original_factory(self):
        from recovery_agents import agent_factory
        caller_factory = agent_factory('terminus-2', self.root)
        with self.assertRaises(ValueError): study.admit_trial(**self.args(caller_factory))
        with self.q.open() as active:
            block = study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                self.assertIs(factory, study.agent_factory(permit))
                self.assertEqual(study.admit_trial(**self.args(factory)), policy.fingerprint(block))
                study.require_task_image(self.root, self.cells[0]['task_id'], 'sha256:' + '9' * 64)
                self.assertEqual(factory.harness, 'terminus-2')
                self.assertEqual(factory.model_protocol_sha256, policy.MODEL_SHA256)
            with self.assertRaises(ValueError): study.admit_trial(**self.args(factory))

    def test_admission_cannot_reuse_a_key_without_a_retained_completion(self):
        with self.q.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                study.admit_trial(**self.args(factory))
                with self.assertRaises(ValueError): study.admit_trial(**self.args(factory))
                with self.assertRaises(ValueError): study.agent_factory(permit)

    def test_wrong_task_order_factory_settings_images_setup_or_root_fail_closed(self):
        changes = [dict(task_id='wrong'), dict(stage='development'), dict(root=self.root / 'other'),
            dict(trial_id=self.cells[1]['trial_id'], task_id=self.cells[1]['task_id']),
            dict(factory=lambda **kw: None), dict(settings=policy.SETTINGS.__class__(100, 1., 'high')),
            dict(gateway_image='sha256:' + 'a' * 64), dict(guard_image='sha256:' + 'a' * 64),
            dict(setup_timeout_seconds=60), dict(setup_timeout_seconds=True)]
        with self.q.open() as active:
            study.register(active)
            for change in changes:
                with self.subTest(change=change), study.dispatch_permit(active) as permit:
                    factory = study.agent_factory(permit); args = self.args(factory); args.update(change)
                    with self.assertRaises(ValueError): study.admit_trial(**args)
                    with self.assertRaises(ValueError): study.agent_factory(permit)

    def test_factory_attribute_code_and_nested_closure_mutation_are_detected(self):
        with self.q.open() as active:
            study.register(active)
            for target in ('attribute', 'code', 'closure'):
                with self.subTest(target=target), study.dispatch_permit(active) as permit:
                    factory = study.agent_factory(permit)
                    if target == 'attribute': factory.harness = 'C0-NC'
                    elif target == 'code':
                        # Same free-variable count, different code, never executed.
                        factory.__code__ = factory.__code__.replace(co_name='changed')
                    else:
                        cell = dict(zip(factory.__code__.co_freevars, factory.__closure__))['native']
                        cell.cell_contents.__code__ = cell.cell_contents.__code__.replace(co_name='changed')
                    with self.assertRaises(ValueError): study.admit_trial(**self.args(factory))

    def test_real_original_constructor_preserves_million_turn_guard_and_deadline_wrapper(self):
        from native_agents import NoRetryTerminus
        with self.q.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                study.admit_trial(**self.args(factory))
                path = self.partial()
                kwargs = dict(paths=NS(trial_dir=path, agent_dir=path / 'agent'),
                    host_api_base='http://127.0.0.1:1/v1', container_api_base='http://127.0.0.1:1/v1',
                    trial_token='synthetic-not-a-provider-key', agent_timeout_seconds=180.,
                    completion_wait_seconds=240.)
                agent = factory(**kwargs)
                self.assertIs(type(agent), NoRetryTerminus)
                self.assertEqual(agent._max_episodes, 1000000)
                self.assertEqual(Path(agent.run.__code__.co_filename).name, 'retry_runtime.py')
                with self.assertRaises(ValueError): factory(**kwargs)
        self.q.process.assert_not_called()

    def test_factory_cannot_be_used_before_admission_or_after_scope_exit(self):
        with self.q.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                with self.assertRaises(ValueError): factory()
            with study.dispatch_permit(active) as permit: factory = study.agent_factory(permit)
            with self.assertRaises(ValueError): factory()

    def test_next_key_preserves_failed_missing_and_unknown_cost_outcomes(self):
        with self.q.open() as active:
            block = study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                for i, reward in enumerate((0.0, None, 1.0)):
                    study.admit_trial(**self.args(factory, i))
                    self.result(block, i, reward)
                study.admit_trial(**self.args(factory, 3))
                retained, partial, _ = study._attempts(self.root, block)
                self.assertFalse(partial); self.assertEqual(len(retained), 3)
                self.assertIsNone(retained[self.cells[1]['trial_id']]['verifier_result'])
                self.assertTrue(all(r['billing']['charged_usd'] is None for r in retained.values()))
                self.assertTrue(all(r['billing']['requests'] > 100 for r in retained.values()))

    def test_changed_previous_result_bytes_invalidate_scope_even_if_outcome_is_same(self):
        with self.q.open() as active:
            block = study.register(active); first = self.result(block)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                first.write_bytes(first.read_bytes() + b'\n')
                with self.assertRaisesRegex(ValueError, 'retained'): study.admit_trial(**self.args(factory, 1))

    def test_retained_result_identity_revocation_cleanup_and_reward_are_checked(self):
        with self.q.open() as active:
            block = study.register(active)
            for changes in (dict(model_revoked=False), dict(containers_removed=False),
                    dict(matched_repeat_registration_sha256='0' * 64), dict(harness='C0-NC'),
                    dict(gateway_image_id='sha256:' + 'a' * 64), dict(guard_image_id='sha256:' + 'a' * 64),
                    dict(task_image_id='sha256:' + 'a' * 64),
                    dict(custom_study='custom'), dict(verifier_result={'rewards': {'reward': True}})):
                self.result(block, **changes)
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    with study.dispatch_permit(active): self.fail('Changed result is not admission')

    def test_partial_gap_foreign_and_symlinked_attempts_are_refused(self):
        with self.q.open() as active:
            block = study.register(active)
            for index in (0, 1):
                path = self.partial(index)
                with self.subTest(index=index), self.assertRaises(ValueError):
                    with study.dispatch_permit(active): self.fail('Partial or gap')
                path.rmdir()
            base = self.rt / 'scored-trials'
            foreign = base / 'not-registered'; foreign.mkdir(mode=0o700)
            with self.assertRaises(ValueError): study._attempts(self.root, block)
            foreign.rmdir(); foreign.symlink_to(base, target_is_directory=True)
            with self.assertRaises(ValueError): study._attempts(self.root, block)

    def test_missing_start_or_public_result_cannot_authorise_next_attempt(self):
        with self.q.open() as active:
            block = study.register(active); result = self.result(block)
            started = result.parent / 'started.json'; raw = started.read_bytes(); started.unlink()
            with self.assertRaises(FileNotFoundError): study._attempts(self.root, block)
            started.write_bytes(raw); started.chmod(0o600); result.chmod(0o644)
            with self.assertRaisesRegex(ValueError, 'private'): study._attempts(self.root, block)

    def test_actual_per_attempt_provider_stop_prevents_further_dispatch(self):
        with self.q.open() as active:
            block = study.register(active); self.result(block)
            target = self.partial(folder='scored-attempts') / 'provider-stop.json'
            target.symlink_to(self.rt / 'missing')
            with self.assertRaisesRegex(ValueError, 'provider stop'):
                with study.dispatch_permit(active): self.fail('Persistent actual provider stop')

    def test_all_eighty_nine_results_mean_no_remaining_key(self):
        with self.q.open() as active:
            block = study.register(active)
            for i in range(89): self.result(block, i, i % 2)
            with study.dispatch_permit(active) as permit:
                with self.assertRaisesRegex(ValueError, 'No fresh'):
                    study.admit_trial(**self.args(study.agent_factory(permit)))

    def test_source_producer_or_registration_mutation_after_open_refuses_admission(self):
        for target in ('source', 'producer', 'registration'):
            with self.subTest(target=target), self.q.open() as active:
                study.register(active)
                with study.dispatch_permit(active) as permit:
                    factory = study.agent_factory(permit)
                    path = (self.root / 'stage2/matched_repeat_study.py' if target == 'source' else
                        self.root / next(iter(self.q.f.proof['evidence_files'])) if target == 'producer' else
                        self.rt / policy.REGISTRATION_FILE)
                    raw = path.read_bytes(); path.write_bytes(raw + b'\n')
                    with self.assertRaises(ValueError): study.admit_trial(**self.args(factory))
                    path.write_bytes(raw)
                    with self.assertRaises(ValueError): study.agent_factory(permit)

    def test_post_start_image_mismatch_permanently_invalidates_scope(self):
        with self.q.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                study.admit_trial(**self.args(study.agent_factory(permit)))
                with self.assertRaisesRegex(ValueError, 'image'):
                    study.require_task_image(self.root, self.cells[0]['task_id'], 'sha256:' + 'a' * 64)
                with self.assertRaises(ValueError): study.agent_factory(permit)

    def test_source_change_during_retained_result_check_is_refused_before_admission(self):
        with self.q.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                factory = study.agent_factory(permit)
                original = study._attempts
                def changed(root, block):
                    value = original(root, block)
                    (root / 'stage2/matched_repeat_study.py').write_bytes(b'Changed after result read')
                    return value
                with patch.object(study, '_attempts', changed), self.assertRaises(ValueError):
                    study.admit_trial(**self.args(factory))
                with self.assertRaises(ValueError): study.agent_factory(permit)

    def test_nested_saved_constructed_cross_process_and_thread_permits_refused(self):
        with self.q.open() as active:
            study.register(active)
            with study.dispatch_permit(active) as permit:
                with self.assertRaises(ValueError):
                    with study.dispatch_permit(active): self.fail('Nested')
                with self.assertRaises(TypeError): pickle.dumps(permit)
                with self.assertRaises(ValueError): study.agent_factory(study._Permit())
                with patch.object(session.os, 'getpid', return_value=os.getpid() + 1):
                    with self.assertRaises(ValueError): study.agent_factory(permit)
                errors = []
                def other():
                    try: study.agent_factory(permit)
                    except ValueError as exc: errors.append(str(exc))
                thread = threading.Thread(target=other); thread.start(); thread.join()
                self.assertEqual(len(errors), 1)
            with self.assertRaises(ValueError): study.agent_factory(permit)

    def test_child_async_task_cannot_inherit_dispatch_authority(self):
        async def parent():
            with self.q.open() as active:
                study.register(active)
                with study.dispatch_permit(active) as permit:
                    async def child():
                        with self.assertRaisesRegex(ValueError, 'async tasks'): study.agent_factory(permit)
                    await asyncio.create_task(child())
                    study.agent_factory(permit)
        asyncio.run(parent())


class ScoredIntegrationTests(StudyFixture):
    def test_rejected_scope_never_reaches_host_container_or_trial_creation(self):
        async def run():
            args = self.args(lambda **kw: None)
            args['agent_factory'] = args.pop('factory'); args['model_settings'] = args.pop('settings')
            with patch('scored_trial.check_host') as host:
                with self.assertRaises(ValueError):
                    await run_trial(**args, accounting_mode='provider-credit-only', matched_repeat=policy.EXPERIMENT)
                host.assert_not_called()
            self.assertFalse((self.rt / 'scored-trials').exists())
        asyncio.run(run())

    def test_explicit_repeat_cannot_mix_custom_reserved_or_setup_billing(self):
        async def run():
            base = self.args(lambda **kw: None)
            base['agent_factory'] = base.pop('factory'); base['model_settings'] = base.pop('settings')
            for changes in (dict(custom_study='custom'), dict(accounting_mode='reserved'),
                    dict(billing_runtime=self.rt), dict(billing_kind='setup'), dict(matched_repeat='unknown')):
                args = dict(base, accounting_mode='provider-credit-only', matched_repeat=policy.EXPERIMENT)
                args.update(changes)
                with self.subTest(changes=changes), patch('scored_trial.check_host') as host:
                    with self.assertRaises(ValueError): await run_trial(**args)
                    host.assert_not_called()
        asyncio.run(run())

    def wire(self, bad_image=False):
        async def run():
            task_id = self.cells[0]['task_id']; image = self.q.host['task_inventory'][task_id]['image_id']
            task = NS(paths=NS(environment_dir=self.root), has_steps=False, instruction='synthetic fixture',
                config=NS(environment=NS(network_mode=NS(value='public'), build_timeout_sec=1),
                    agent=NS(network_mode=None, timeout_sec=180.),
                    verifier=NS(network_mode=None, environment=None)))
            events = []
            class Env:
                def __init__(self, **kw): events.append('constructed')
                async def start(self, **kw): events.append('start')
                async def stop(self, **kw): events.append('cleanup')
                async def stop_service(self, name): events.append('revoke')
            class Bridge:
                base_url = 'http://127.0.0.1:1/v1'
                def __init__(self, *args, **kw): pass
                def __enter__(self): return self
                def __exit__(self, *args): pass
            def service(project, name):
                return dict(Id='synthetic', Image=(('sha256:' + 'a' * 64 if bad_image else image)
                    if name == 'main' else self.q.f.proof['gateway_image']), State={'Running': False})
            async def phases(**kwargs):
                self.assertEqual(kwargs['setup_timeout_seconds'], 900)
                self.assertEqual(kwargs['agent']._max_episodes, 1000000)
                await kwargs['revoke_model'](); events.append('verify')
                return dict(status='verified', model_revoked=True, verifier_result={'rewards': {'reward': 0.0}})
            with ExitStack() as patches:
                for name, value in dict(check_host=lambda: {}, frozen_dataset=lambda root: root,
                        audit_task=lambda *args: None, HostModelBridge=Bridge, service=service,
                        execute_phases=phases, compose_runtime=lambda **kw: {}, docker=lambda *args: '').items():
                    patches.enter_context(patch('scored_trial.' + name, value))
                patches.enter_context(patch('pinned_docker.PinnedImageDockerEnvironment', Env))
                patches.enter_context(patch('harbor.models.task.task.Task', return_value=task))
                legacy = patches.enter_context(patch('receipt_runtime_transition.gateway_for_trial',
                    side_effect=AssertionError('No old receipt transition in a repeat')))
                with self.q.open() as active:
                    block = study.register(active)
                    with study.dispatch_permit(active) as permit:
                        args = self.args(study.agent_factory(permit))
                        args['agent_factory'] = args.pop('factory'); args['model_settings'] = args.pop('settings')
                        if bad_image:
                            with self.assertRaises(ValueError):
                                await run_trial(**args, accounting_mode='provider-credit-only', matched_repeat=policy.EXPERIMENT)
                        else:
                            result = await run_trial(**args, accounting_mode='provider-credit-only', matched_repeat=policy.EXPERIMENT)
                            self.assertEqual(result['matched_repeat_registration_sha256'], policy.fingerprint(block))
                            self.assertEqual(result['matched_repeat_experiment'], policy.EXPERIMENT)
                            self.assertEqual(result['guard_image_id'], self.q.f.proof['guard_image'])
                            self.assertEqual(result['verifier_result']['rewards']['reward'], 0.0)
                            self.assertNotIn('custom_study', result)
                            self.assertLess(events.index('revoke'), events.index('verify'))
                            study.admit_trial(**self.args(args['agent_factory'], 1))
                    legacy.assert_not_called()
            path = self.rt / 'scored-trials' / self.cells[0]['trial_id'] / 'result.json'
            saved = json.loads(path.read_bytes())
            self.assertTrue(all(saved[k + '_removed'] for k in ('containers', 'networks', 'volumes')))
            if bad_image:
                self.assertEqual(saved['status'], 'infrastructure_failed'); self.assertNotIn('verify', events)
            self.q.process.assert_not_called()
        asyncio.run(run())

    def test_scored_hook_wires_original_factory_passive_trace_revocation_and_retained_zero(self):
        self.wire()

    def test_post_start_image_failure_retains_cleanup_without_replay(self):
        self.wire(bad_image=True)

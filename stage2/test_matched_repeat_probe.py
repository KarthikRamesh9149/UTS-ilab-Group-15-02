"""Actual local scopes/lifecycle/files; mocked Docker and native agent actions.

These tests never create real native proof or contact a provider. Synthetic
prerequisites exist only in temporary directories, with native readers mocked.
"""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import pickle
import shutil
import signal
import threading
import time
import unittest
from unittest.mock import patch

import matched_repeat_probe as probe
import matched_repeat_fixture as fixture
import matched_repeat_policy as policy
import matched_repeat_session as session
import scored_trial
import trial_execution
from scored_gateway import durable_json
from test_matched_repeat_fixture import payload, feedback
from test_matched_repeat_policy import predecessors
import test_matched_repeat_session as session_fixtures

STAGE = Path(__file__).resolve().parent


class Clock:
    boot_id = 'local-synthetic-boot'
    def monotonic(self): return time.monotonic()
    def wall(self): return time.time()


class ProbeTests(unittest.TestCase):
    def setUp(self):
        self.q = q = session_fixtures.SessionTests('runTest'); q.setUp(); self.addCleanup(q.doCleanups)
        self.enterContext(patch.dict(os.environ, {name: '' for name in (
            'DOCKER_HOST', 'DOCKER_CONTEXT', 'DOCKER_TLS_VERIFY', 'DOCKER_CERT_PATH', 'DOCKER_CONFIG',
            'COMPOSE_FILE', 'OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPINFRA_API_TOKEN')}))
        self.root = q.root; self.rt = q.f.runtime
        # Discard only this temporary test fixture's earlier synthetic proof.
        # Real rehearsals never manufacture or erase production qualification.
        for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE):
            (self.rt / name).unlink()
        for case in q.f.proof['synthetic']:
            shutil.rmtree(self.root / case['runtime_path'])
            (self.rt / ('matched-repeat-rehearsal-' + case['mode'] + '.json')).unlink()
        for name in probe.SOURCE_FILES:
            q.actual[name] = q.write('stage2/' + name, (STAGE / name).read_bytes())
            q.f.final['sources'][name] = q.actual[name]
            if name in q.f.original['sources']:
                q.f.original['sources'][name] = q.actual[name]
        q.f.final['sources_sha256'] = policy.fingerprint(q.f.final['sources'])
        for key, value in (('ORIGINAL_QUALIFICATION_SHA256', policy.fingerprint(q.f.original)),
                ('CUSTOM_FINAL_QUALIFICATION_SHA256', policy.fingerprint(q.f.final)),
                ('CUSTOM_FINAL_SOURCES_SHA256', q.f.final['sources_sha256'])):
            self.enterContext(patch.object(policy, key, value))
        for name, value, anchor in ((policy.BASELINE_FILE, q.f.original, 'ORIGINAL_FILE_SHA256'),
                (policy.FINAL_FILE, q.f.final, 'FINAL_FILE_SHA256')):
            self.enterContext(patch.object(session.baseline, anchor, q.private(name, value)))
        q.f.predecessor = predecessors(q.f.manifest, 'terminus-2')
        q.pred['predecessors'] = deepcopy(q.f.predecessor)
        for record in (q.pred, q.old, q.library, q.host):
            record['original_qualification_sha256'] = policy.fingerprint(q.f.original)
            record['custom_final_qualification_sha256'] = policy.fingerprint(q.f.final)
            record['sources_sha256' if record is q.host else 'current_sources_sha256'] = policy.fingerprint(q.actual)
        q.host.update(sources=deepcopy(q.actual), source_transition=policy.source_transition(q.f.original, q.f.final, q.actual),
            task_inventory={probe.RESOURCE_TASK: dict(image_id='sha256:' + '4' * 64, cpus=1, memory_mb=256,
                storage_mb=1024, gpus=0, build_timeout_seconds=120., agent_timeout_seconds=180., verifier_timeout_seconds=30.)})
        (self.root / '.cache/stage2-tokenizer').mkdir(parents=True)
        self.events = []; self.environments = []; self.arguments = []; self.captured = []
        self.before_start = None; self.before_stop = None; self.after_phases = None
        self.observation_change = None
        self.enterContext(patch.object(fixture, 'require_network_isolation'))
        self.enterContext(patch('retry_runtime.Clock', Clock))
        for name in ('verify_qualification',):
            self.enterContext(patch.object(session, name, side_effect=AssertionError('No fabricated native qualification')))
        for name in ('register', 'admit_trial', 'dispatch_permit'):
            self.enterContext(patch('matched_repeat_study.' + name, side_effect=AssertionError('No paid admission bypass')))
        self.enterContext(patch('openrouter_transport.OpenRouter', side_effect=AssertionError('No external provider')))
        self.enterContext(patch('receipt_runtime_transition.gateway_for_trial', side_effect=AssertionError('No legacy gateway transition')))
        self.enterContext(patch.object(scored_trial, 'check_host', return_value=q.host['host_environment']))
        self.enterContext(patch.object(scored_trial, 'frozen_dataset', side_effect=AssertionError('No benchmark task content')))
        self.enterContext(patch.object(scored_trial, 'docker', return_value=''))
        test = self

        class Environment:
            def __init__(self, **kwargs):
                self.kwargs = kwargs; test.environments.append(self)
                self.paths = kwargs['trial_paths']; self.root = self.paths.trial_dir.parents[3]
                self.rt = self.root / '.runtime/stage2'; self.gateway = None
                self.compose = json.loads(kwargs['extra_docker_compose'][0].read_bytes())
                self.project = kwargs['environment_name']; self.running = True
            async def start(self, **kwargs):
                test.events.append('start')
                if test.before_start: test.before_start(self)
            async def stop(self, **kwargs):
                test.events.append('cleanup'); self.running = False
                if test.before_stop: await test.before_stop()
            async def stop_service(self, name):
                test.events.append('revocation'); self.running = False
                if self.gateway is not None: self.gateway.close()
            async def empty_dirs(self, *args, **kwargs): test.events.append('verifier-outputs')
            @contextmanager
            def with_default_user(self, user): yield
        self.enterContext(patch('pinned_docker.PinnedImageDockerEnvironment', Environment))

        class Bridge:
            base_url = 'http://127.0.0.1:1234/v1'
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): test.events.append('bridge'); return self
            def __exit__(self, *args): test.events.append('bridge-close')
        self.enterContext(patch.object(scored_trial, 'HostModelBridge', Bridge))
        self.enterContext(patch.object(scored_trial, 'service', side_effect=self.service))

        async def setup(agent, environment): test.events.append('native-setup')
        async def run(agent, instruction, environment, context):
            test.events.append('native-run')
            value = json.loads((environment.rt / fixture.FIXTURE_FILE).read_bytes())
            clock = Clock(); token = (environment.paths.trial_dir / 'token').read_text()
            provider = fixture.SyntheticProvider(fixture.SYNTHETIC_KEY, harness=value['harness'], mode=value['mode'],
                clock=clock, generation_enabled=True, completion_wait_seconds=240.)
            gateway = fixture.FixtureSession(environment.root, value['trial_id'], 'final', token,
                provider, settings=policy.SETTINGS, clock=clock)
            environment.gateway = gateway
            request = payload(value['harness']); response = gateway.complete(token, request)
            request = feedback(value['harness'], request, response); response = gateway.complete(token, request)
            if value['harness'] == 'terminus-2':
                gateway.complete(token, feedback(value['harness'], request, response, confirmation=True))
        self.enterContext(patch('native_agents.NoRetryTerminus.setup', setup))
        self.enterContext(patch('native_agents.NoRetryTerminus.run', run))

        class Verifier:
            def __init__(self, *args): pass
            async def verify(self):
                test.events.append('verify')
                from types import SimpleNamespace
                return SimpleNamespace(model_dump=lambda **kwargs: {'rewards': {'reward': 1.0}})
        async def phases(**kwargs):
            async def prepare(environment): return {'synthetic_local_setup': True}
            kwargs['prepare_environment'] = prepare
            kwargs['verifier_factory'] = Verifier
            answer = await trial_execution.execute_phases(**kwargs)
            if test.after_phases: test.after_phases()
            return answer
        self.enterContext(patch.object(scored_trial, 'execute_phases', phases))
        original_run_trial = self.original_run_trial = scored_trial.run_trial
        async def capture(**kwargs):
            self.arguments.append(kwargs); self.captured.append(kwargs['matched_repeat_fixture'])
            self.assertIs(session._task(), session._live(probe._live(kwargs['matched_repeat_fixture'])['session'])['task'])
            return await original_run_trial(**kwargs)
        self.enterContext(patch.object(scored_trial, 'run_trial', capture))

    def service(self, project, name):
        env = self.environments[-1]; self.assertEqual(project, env.project)
        expected = env.compose['services'][name]
        main = name == 'main'
        result = dict(Id='owned-' + name, Image=env.kwargs['task_env_config'].docker_image if main else expected['image'],
            State=dict(Running=env.running if name != 'socket-init' else False, ExitCode=0), Config=dict(Entrypoint=expected.get('entrypoint'),
                Cmd=expected.get('command'), Env=['LANG=C.UTF-8']),
            HostConfig=dict(Privileged=False, PortBindings={}, CapAdd=expected.get('cap_add', []),
                CapDrop=expected.get('cap_drop', []), SecurityOpt=expected['security_opt'],
                NetworkMode='container:owned-task-network-guard' if name in ('main', 'model-relay') else
                    expected.get('network_mode', 'project-uts-task-egress'),
                ReadonlyRootfs=not main, NanoCpus=10**9 if main else int(expected['cpus'] * 1e9),
                Memory=256 * 1024**2 if main else int(expected['mem_limit'].removesuffix('m')) * 1024**2),
            NetworkSettings=dict(Networks={'none': {}} if name == 'model-gateway' else {}), Mounts=[])
        if main:
            for field in ('agent', 'verifier'):
                result['Mounts'].append(dict(Type='bind', Source=str(getattr(env.paths, field + '_dir')),
                    Destination='/logs/' + field, RW=True))
        else:
            for mount in expected.get('volumes', []):
                result['Mounts'].append(dict(Type=mount['type'], Destination=mount['target'],
                    Source=mount['source'], Name=project + '_model-socket', RW=not mount.get('read_only', False)))
        if self.observation_change: self.observation_change(name, result)
        return result

    async def execute(self, mode='tools', after=None):
        with self.q.open() as active:
            value = await probe.probe(active, mode)
            if after: await after(active, value)
            return value

    def failure(self, *, mode='tools', expression=''):
        with self.assertRaisesRegex((ValueError, RuntimeError, OSError), expression):
            asyncio.run(self.execute(mode))
        failures = list(self.rt.glob('matched-repeat-rehearsal-*-failure.json'))
        if failures:
            value = json.loads(failures[0].read_bytes())
            self.assertNotIn('error', value); self.assertFalse(value['automatic_resume'])

    def test_tools_uses_real_scoped_scored_lifecycle_and_original_constructor(self):
        value = asyncio.run(self.execute())
        self.assertEqual(value['status'], 'passed'); self.assertEqual(set(value['checks']), policy.probe_checks('tools'))
        self.assertTrue(all(value['checks'].values()))
        self.assertFalse(value['paid_launch_ready']); self.assertFalse(value['repeat_execution_qualified'])
        self.assertEqual(value['live_api_calls'], 0)
        self.assertLess(self.events.index('native-setup'), self.events.index('native-run'))
        self.assertLess(self.events.index('revocation'), self.events.index('verify'))
        result = json.loads((self.root / value['runtime_path'] / '.runtime/stage2/scored-trials' /
            self.arguments[0]['trial_id'] / 'result.json').read_bytes())
        self.assertEqual(result['billing']['requests'], 4); self.assertEqual(result['billing']['unknown_cost_requests'], 4)
        self.assertIsNone(result['billing']['charged_usd']); self.assertNotIn('matched_repeat_registration_sha256', result)
        self.assertEqual(result['matched_repeat_fixture'], fixture.FIXTURE_KIND)
        self.assertFalse(probe._PERMITS)

    def test_actual_setup_cancellation_never_calls_agent_or_verifier(self):
        value = asyncio.run(self.execute('cancel_setup'))
        self.assertTrue(value['checks']['cancelled_setup_evidence'])
        self.assertIn('native-setup', self.events); self.assertNotIn('native-run', self.events)
        self.assertNotIn('verify', self.events); self.assertIn('revocation', self.events)

    def test_real_cooperative_signal_finishes_current_fixture_and_restores_handler(self):
        before = signal.getsignal(signal.SIGUSR1)
        value = asyncio.run(self.execute('boundary_stop'))
        self.assertTrue(value['checks']['cooperative_stop_persisted']); self.assertTrue(value['checks']['no_next_dispatch'])
        self.assertIn('verify', self.events); self.assertIs(signal.getsignal(signal.SIGUSR1), before)
        self.assertFalse((self.rt / 'operator-stop-request.json').exists())

    def test_no_production_proof_is_created_or_required(self):
        value = asyncio.run(self.execute())
        rt = self.root / value['runtime_path'] / '.runtime/stage2'
        self.assertTrue(all(not (rt / name).exists() for name in fixture.PRODUCTION_FILES))
        self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())

    def test_saved_or_empty_session_cannot_create_rehearsal(self):
        for value in ({}, session._Session(), object()):
            with self.assertRaises(ValueError): asyncio.run(probe.probe(value, 'tools'))
        self.assertFalse(list(self.rt.glob('matched-repeat-rehearsal-*')))

    def test_different_async_task_cannot_consume_live_session(self):
        async def run():
            with self.q.invalidated() as active:
                with self.assertRaisesRegex(ValueError, 'cross processes'):
                    await asyncio.create_task(probe.probe(active, 'tools'))
        asyncio.run(run()); self.assertFalse(self.environments)

    def test_existing_qualification_registration_or_attempt_refuses_before_images(self):
        for name in (policy.QUALIFICATION_FILE, policy.REGISTRATION_FILE, 'matched-repeat-dispatch.json'):
            path = self.rt / name; durable_json(path, {})
            self.failure(expression='qualified, dispatched')
            path.unlink()
        path = self.rt / 'scored-trials/started'; path.mkdir(parents=True)
        self.failure(expression='No paid attempts')
        self.assertFalse(self.environments)

    def test_prior_intent_or_abandoned_runtime_blocks_fresh_session_replay(self):
        path = self.rt / 'matched-repeat-rehearsal-tools.json'; durable_json(path, {})
        self.failure(expression='automatic replay'); path.unlink()
        (self.rt / 'native-matched-repeat-terminus-2-tools-interrupted').mkdir()
        self.failure(expression='automatic replay'); self.assertFalse(self.environments)

    def test_success_cannot_replay_with_same_or_fresh_session(self):
        async def after(active, value):
            with self.assertRaisesRegex(ValueError, 'automatic replay'): await probe.probe(active, 'tools')
        asyncio.run(self.execute(after=after)); self.failure(expression='automatic replay')
        self.assertEqual(len(self.environments), 1)

    def test_real_credential_or_redirected_daemon_refused(self):
        for name in ('OPENROUTER_API_KEY', 'DOCKER_HOST', 'DOCKER_CONTEXT', 'COMPOSE_FILE'):
            with patch.dict(os.environ, {name: 'not-for-this-fixture'}):
                self.failure(expression='Credential-free')
        self.assertFalse(self.environments)

    def test_actual_network_and_image_audit_precedes_constructor(self):
        self.observation_change = lambda name, value: value['HostConfig'].update(NetworkMode='bridge') if name == 'model-gateway' else None
        self.failure(expression='network isolation')
        self.assertNotIn('bridge', self.events); self.assertIn('cleanup', self.events)

    def test_task_image_drift_cleans_without_agent(self):
        self.observation_change = lambda name, value: value.update(Image='sha256:' + '9' * 64) if name == 'main' else None
        self.failure(expression='task image changed'); self.assertNotIn('native-setup', self.events)

    def test_wrong_gateway_entrypoint_refused(self):
        self.observation_change = lambda name, value: value['Config'].update(Entrypoint=['python', 'paid.py']) if name == 'model-gateway' else None
        self.failure(expression='fixed synthetic gateway')

    def test_unexpected_credential_mount_refused(self):
        self.observation_change = lambda name, value: value['Mounts'][3].update(Source='/real/.env') if name == 'model-gateway' else None
        self.failure(expression='another host path')

    def test_socket_volume_identity_and_readonly_access_are_audited(self):
        self.observation_change = lambda name, value: value['Mounts'][0].update(Name='another-volume') if name == 'model-relay' else None
        self.failure(expression='volume identity')

    def test_extra_network_attachment_refused_even_with_none_mode(self):
        self.observation_change = lambda name, value: value['NetworkSettings']['Networks'].update(egress={}) if name == 'model-gateway' else None
        self.failure(expression='external network')

    def test_privileged_guard_is_refused(self):
        self.observation_change = lambda name, value: value['HostConfig'].update(Privileged=True) if name == 'task-network-guard' else None
        self.failure(expression='privileges')

    def test_changed_fixture_bytes_fail_before_agent_and_do_not_revive(self):
        self.before_start = lambda env: (env.rt / fixture.FIXTURE_FILE).write_bytes(b'{}')
        self.failure(expression='input changed'); self.assertNotIn('native-setup', self.events)
        self.failure(expression='retained rehearsal failure'); self.assertEqual(len(self.environments), 1)

    def test_changed_source_bytes_after_start_refused_and_retained(self):
        self.before_start = lambda env: (self.root / 'stage2/matched_repeat_probe.py').write_text('changed')
        self.failure(expression='input changed'); self.assertNotIn('native-setup', self.events)

    def test_public_fake_credential_refused(self):
        self.before_start = lambda env: (env.root / '.env').chmod(0o644)
        self.failure(expression='private'); self.assertNotIn('native-setup', self.events)

    def test_task_object_mutation_is_not_an_admission_escape(self):
        self.before_start = lambda env: setattr(env.kwargs['task_env_config'], 'cpus', 2)
        self.failure(expression='Official task resources|configuration changed')

    def test_external_cancellation_is_retained_not_reported_as_fixture_success(self):
        self.before_start = lambda env: asyncio.current_task().cancel()
        with self.assertRaises(asyncio.CancelledError): asyncio.run(self.execute('cancel_setup'))
        value = json.loads((self.rt / 'matched-repeat-rehearsal-cancel_setup-failure.json').read_bytes())
        self.assertEqual(value['error_type'], 'CancelledError'); self.assertIn('cleanup', self.events)

    def test_image_reverification_is_mandatory_before_and_after_execution(self):
        original = self.q.image_binding.side_effect
        def binding(active):
            value = original(active)
            if len(self.q.image_binding.call_args_list) >= 3: value['image_build_sha256'] = 'f' * 64
            return value
        self.q.image_binding.side_effect = binding
        self.failure(expression='Image evidence changed'); self.assertIn('verify', self.events)

    def test_result_return_value_cannot_replace_actual_durable_result(self):
        async def no_execution(**kwargs): return {'status': 'verified'}
        with patch.object(scored_trial, 'run_trial', no_execution):
            self.failure()
        self.assertFalse(self.environments)

    def test_closed_fixture_handle_is_not_reusable_or_serializable(self):
        asyncio.run(self.execute()); permit = self.captured[0]
        with self.assertRaises(ValueError): probe._live(permit)
        with self.assertRaises(TypeError): pickle.dumps(permit)

    def test_mixed_paid_route_and_saved_fixture_flag_refused(self):
        args = dict(root=self.root, trial_id='synthetic', task_id='lifecycle', stage='final',
            agent_factory=lambda **kwargs: None, gateway_image='sha256:' + '1' * 64,
            guard_image='sha256:' + '2' * 64, setup_timeout_seconds=900, model_settings=policy.SETTINGS,
            accounting_mode='provider-credit-only', matched_repeat_fixture={})
        with self.assertRaises(ValueError): asyncio.run(self.original_run_trial(**args, matched_repeat=policy.EXPERIMENT))

    def test_live_handle_refuses_thread_pid_and_serialized_metadata(self):
        self.refuse_owner_transfer('thread')

    def test_process_failure_latches_before_any_native_scored_execution(self):
        self.refuse_owner_transfer('process')

    def refuse_owner_transfer(self, kind):
        original = scored_trial.run_trial
        async def check(**kwargs):
            permit = kwargs['matched_repeat_fixture']; errors = []
            def other_thread():
                try: probe._live(permit)
                except ValueError as exc: errors.append(type(exc).__name__)
            if kind == 'thread':
                thread = threading.Thread(target=other_thread); thread.start(); thread.join()
                self.assertEqual(errors, ['ValueError'])
            else:
                with patch.object(session.os, 'getpid', return_value=os.getpid() + 1):
                    with self.assertRaisesRegex(ValueError, 'cross processes'): probe._live(permit)
            with self.assertRaises(TypeError): pickle.dumps(permit)
            with self.assertRaisesRegex(ValueError, 'active locked'): probe._live(permit)
            return await original(**kwargs)
        with patch.object(scored_trial, 'run_trial', check), self.assertRaisesRegex(ValueError, 'active locked'):
            asyncio.run(self.execute())
        self.assertFalse(self.environments)

    def test_scored_lifecycle_cannot_move_to_a_child_task(self):
        async def moved(**kwargs): return await asyncio.create_task(self.original_run_trial(**kwargs))
        with patch.object(scored_trial, 'run_trial', moved): self.failure(expression='cross processes')
        self.assertFalse(self.environments)

    def test_nested_rehearsal_does_not_transfer_or_reuse_the_session(self):
        original = scored_trial.run_trial
        async def nested(**kwargs):
            active = probe._live(kwargs['matched_repeat_fixture'])['session']
            with self.assertRaisesRegex(ValueError, 'nested'): await probe.probe(active, 'cancel_setup')
            return await original(**kwargs)
        with patch.object(scored_trial, 'run_trial', nested): asyncio.run(self.execute())

    def test_admission_refuses_factory_identity_mutation(self):
        self.before_start = lambda env: setattr(self.arguments[-1]['agent_factory'], 'harness', 'openhands')
        self.failure(expression='unchanged native construction'); self.assertNotIn('native-setup', self.events)

    def test_compose_cannot_mount_another_credential_or_choose_images(self):
        original = probe.compose
        def substitute(permit, **kwargs):
            kwargs['credential_file'] = self.root / '.env'
            return original(permit, **kwargs)
        with patch.object(probe, 'compose', substitute): self.failure(expression='private runtime')
        self.assertFalse(self.environments)

    def test_owned_resources_block_before_any_rehearsal_intent(self):
        with patch.object(scored_trial, 'docker', return_value='retained-owned-container'):
            self.failure(expression='Retained owned resources')
        self.assertFalse(self.environments); self.assertFalse(list(self.rt.glob('matched-repeat-rehearsal-*')))

    def test_owned_resources_are_checked_again_at_terminal_boundary(self):
        original = scored_trial.docker
        def docker(*args):
            return 'leftover' if 'name=uts-scored-' in args and self.environments else original(*args)
        with patch.object(scored_trial, 'docker', docker): self.failure(expression='Retained owned resources')
        self.assertIn('verify', self.events)

    def test_all_three_modes_can_run_in_one_live_session_without_reopening_locks(self):
        async def run():
            with self.q.open() as active:
                result = [await probe.probe(active, mode) for mode in policy.PROBE_MODES]
                self.assertTrue(all(value['status'] == 'passed' for value in result))
                self.assertEqual(self.q.auth.call_count, 1); self.assertEqual(self.q.old_auth.call_count, 1)
                self.assertEqual(self.q.lock.call_count, 1)
                return result
        values = asyncio.run(run())
        self.assertEqual(len(self.environments), 3)
        self.assertEqual([v['mode'] for v in values], list(policy.PROBE_MODES))

    def test_prior_completed_producer_bytes_are_rechecked_before_next_mode(self):
        async def run():
            with self.q.open() as active:
                value = await probe.probe(active, 'tools')
                name = next(n for n in value['producer_files'] if n.endswith('/result.json'))
                (self.root / name).write_text('{}')
                with self.assertRaisesRegex(ValueError, 'input changed'): await probe.probe(active, 'cancel_setup')
        asyncio.run(run()); self.assertEqual(len(self.environments), 1)

    def test_overlapping_file_bindings_must_agree(self):
        with patch.object(probe, '_prior', return_value={
                '.runtime/stage2/matched-repeat-image-build.json': '0' * 64}):
            self.failure(expression='file bindings disagree')
        self.assertFalse(self.environments)
        self.assertTrue((self.rt / 'matched-repeat-rehearsal-tools-failure.json').exists())

    def test_prior_incomplete_other_mode_blocks_new_operation(self):
        durable_json(self.rt / 'matched-repeat-rehearsal-tools.json', dict(mode='tools', harness='terminus-2',
            runtime_path='.runtime/stage2/native-matched-repeat-terminus-2-tools-retained'))
        (self.rt / 'native-matched-repeat-terminus-2-tools-retained').mkdir()
        self.failure(mode='cancel_setup'); self.assertFalse(self.environments)

    def test_retained_failure_blocks_every_other_mode_in_fresh_session(self):
        durable_json(self.rt / 'matched-repeat-rehearsal-tools-failure.json', dict(error_type='CancelledError', automatic_resume=False))
        self.failure(mode='cancel_setup', expression='retained rehearsal failure'); self.assertFalse(self.environments)

    def test_additional_external_cancel_is_not_swallowed_as_synthetic_cancel(self):
        called = False
        async def cancel_again():
            nonlocal called
            if not called:
                called = True; asyncio.current_task().cancel('external-test-cancel')
                await asyncio.sleep(0)
        self.before_stop = cancel_again
        with self.assertRaises(asyncio.CancelledError): asyncio.run(self.execute('cancel_setup'))
        self.assertTrue((self.rt / 'matched-repeat-rehearsal-cancel_setup-failure.json').exists())
        self.assertFalse(list(self.rt.glob('native-matched-repeat-*/evidence.json')))

    def test_missing_actual_trace_is_not_replaced_by_result_flags(self):
        original = probe._evidence
        def missing(state, cancelled):
            path = next((state['runtime'] / 'scored-trials' / state['record']['trial_id'] / 'traces').glob('*.json'))
            path.unlink()  # This test's private temporary trace only.
            return original(state, cancelled)
        with patch.object(probe, '_evidence', missing): self.failure(expression='lifecycle failed')

    def test_synthetic_zero_is_retained_as_failed_qualification_not_replayed(self):
        original = probe._evidence
        def zero(state, cancelled):
            path = state['runtime'] / 'scored-trials' / state['record']['trial_id'] / 'result.json'
            value = json.loads(path.read_bytes()); value['verifier_result']['rewards']['reward'] = 0
            path.write_text(json.dumps(value))
            return original(state, cancelled)
        with patch.object(probe, '_evidence', zero): self.failure(expression='lifecycle failed')
        result = json.loads(next(self.rt.glob('native-matched-repeat-*/.runtime/stage2/scored-trials/*/result.json')).read_bytes())
        self.assertEqual(result['verifier_result']['rewards']['reward'], 0)

    def test_native_factory_or_protocol_argument_substitution_is_refused(self):
        original = scored_trial.run_trial
        async def substitute(**kwargs):
            kwargs['agent_factory'] = lambda **options: object()
            return await original(**kwargs)
        with patch.object(scored_trial, 'run_trial', substitute): self.failure(expression='fixed synthetic identity')
        self.assertFalse(self.environments)


if __name__ == '__main__':
    unittest.main()

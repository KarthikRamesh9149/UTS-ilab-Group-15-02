"""Real local probe/scored/lifecycle/constructor; native Docker actions mocked."""
from contextlib import contextmanager
import json
from pathlib import Path
import signal
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_recovery_files as files
import no_cutoff_recovery_fixture as fixture
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_probe as probe
import no_cutoff_recovery_qualification as reader
import no_cutoff_recovery_session as session
import scored_trial
import trial_execution
from custom_python_runtime import PythonBundle
from test_no_cutoff_recovery_qualification import FakeContainer, request, feedback
from test_no_cutoff_recovery_runtime import save
import test_qualify_no_cutoff_recovery as base

REAL_PROBE = probe.probe


class Clock:
    boot_id = 'local-synthetic-recovery-boot'
    def monotonic(self): return time.monotonic()
    def wall(self): return time.time()


class ProbeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.base = base.QualifierTests('runTest')
        self.base._callCleanup = lambda function, *args, **kwargs: function(*args, **kwargs)
        self.addCleanup(self.base.doCleanups); self.base.setUp()
        self.q = self.base.q; self.root = self.q.root; self.rt = self.base.rt
        self.base.official.update(cpus=1, memory_mb=256, storage_mb=1024, gpus=0, build_timeout_seconds=120)
        files.save(self.rt / policy.RUNTIME_FILE, self.q.host)
        save(self.root, '.runtime/stage2/python-runtime.tar.gz', self.base.bundle)
        (self.root / '.cache/stage2-tokenizer').mkdir(parents=True, mode=0o700)
        self.events = []; self.environments = []; self.observation_change = None
        self.arguments = []; self.after_phases = None
        self.enterContext(patch('retry_runtime.Clock', Clock))
        self.enterContext(patch('custom_python_runtime.PythonBundle.validate', return_value={'local_mock': True}))
        bundle = lambda root: PythonBundle(Path(root) / '.runtime/stage2/python-runtime.tar.gz', policy.PYTHON_SHA256)
        self.enterContext(patch('portable_custom_agent.runtime_bundle', side_effect=bundle))
        self.enterContext(patch('no_cutoff_custom_agent.runtime_bundle', side_effect=bundle))
        self.enterContext(patch('openrouter_transport.OpenRouter', side_effect=AssertionError('No real provider')))
        self.enterContext(patch.object(scored_trial, 'check_host', return_value={'execution_mode':'native_linux_x86_64'}))
        self.enterContext(patch.object(scored_trial, 'frozen_dataset', side_effect=AssertionError('No benchmark payload')))
        self.enterContext(patch.object(scored_trial, 'docker', return_value=''))
        test = self

        class Environment:
            def __init__(self, **kwargs):
                self.kwargs = kwargs; test.environments.append(self)
                self.paths = kwargs['trial_paths']; self.root = self.paths.trial_dir.parents[3]
                self.rt = self.root / '.runtime/stage2'; self.gateway = None
                self.compose = json.loads(kwargs['extra_docker_compose'][0].read_bytes())
                self.project = kwargs['environment_name']; self.running = True
                self.record = json.loads((self.rt / fixture.FIXTURE_FILE).read_bytes())
                self.container = FakeContainer(self.record['mode'])
            async def start(self, **kwargs):
                test.events.append('start')
                clock = Clock(); token = (self.paths.trial_dir / 'token').read_text()
                provider = fixture.SyntheticProvider(fixture.SYNTHETIC_KEY, mode=self.record['mode'],
                    clock=clock, generation_enabled=True, completion_wait_seconds=240)
                self.gateway = fixture.FixtureSession(self.root, self.record['trial_id'], 'final', token,
                    provider, settings=policy.SETTINGS, clock=clock)
            async def stop(self, **kwargs): test.events.append('cleanup'); self.running = False
            async def stop_service(self, name):
                test.events.append('revocation'); self.running = False
                if self.gateway is not None: self.gateway.close()
            async def empty_dirs(self, *args, **kwargs): test.events.append('verifier-outputs')
            async def exec(self, *args, **kwargs): return await self.container.exec(*args, **kwargs)
            @contextmanager
            def with_default_user(self, user): yield
        self.enterContext(patch('pinned_docker.PinnedImageDockerEnvironment', Environment))

        class Bridge:
            base_url = 'http://127.0.0.1:1234/v1'
            def __init__(self, *args, **kwargs): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        self.enterContext(patch.object(scored_trial, 'HostModelBridge', Bridge))
        self.enterContext(patch.object(scored_trial, 'service', side_effect=self.service))
        async def setup(agent, environment): test.events.append('native-setup')
        async def run(agent, instruction, environment, context):
            test.events.append('native-run')
            token = (environment.paths.trial_dir / 'token').read_text()
            first = environment.gateway.complete(token, request())
            environment.gateway.complete(token, feedback(request(), first))
        self.enterContext(patch('no_cutoff_custom_agent.NoCutoffCustomHarborAgent.setup', setup))
        self.enterContext(patch('no_cutoff_custom_agent.NoCutoffCustomHarborAgent.run', run))
        class Verifier:
            def __init__(self, *args): pass
            async def verify(self):
                test.events.append('verify')
                return SimpleNamespace(model_dump=lambda **kwargs: {'rewards': {'reward': 1.0}})
        async def phases(**kwargs):
            kwargs['verifier_factory'] = Verifier
            result = await trial_execution.execute_phases(**kwargs)
            if self.after_phases: self.after_phases()
            return result
        self.enterContext(patch.object(scored_trial, 'execute_phases', phases))
        original = scored_trial.run_trial
        async def capture(**kwargs):
            self.arguments.append(kwargs)
            return await original(**kwargs)
        self.enterContext(patch.object(scored_trial, 'run_trial', capture))

    def service(self, project, name):
        env = self.environments[-1]; self.assertEqual(project, env.project)
        expected = env.compose['services'][name]; main = name == 'main'
        result = dict(Id='owned-' + name, Image=env.kwargs['task_env_config'].docker_image if main else expected['image'],
            State=dict(Running=env.running if name != 'socket-init' else False, ExitCode=0),
            Config=dict(Entrypoint=expected.get('entrypoint'), Cmd=expected.get('command'), Env=['LANG=C.UTF-8']),
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

    async def test_all_six_actual_local_probe_scored_original_constructor_and_producer_reads(self):
        before = signal.getsignal(signal.SIGUSR1)
        with self.base.open() as active:
            images.build(active)
            for mode in policy.PROBE_MODES:
                self.events.clear()
                case = await REAL_PROBE(active, mode)
                proof = dict(images.qualification_binding(active), sources=self.q.bound,
                    sources_sha256=policy.fingerprint(self.q.bound))
                bound = reader.case_files(self.root, case, proof)
                self.assertIn(case['runtime_path'] + '/producer.json', bound)
                self.assertEqual(self.environments[-1].container.original_calls, 1)
                if mode in fixture.NO_MODEL:
                    self.assertNotIn('native-setup', self.events)
                    self.assertNotIn('native-run', self.events); self.assertNotIn('verify', self.events)
                else:
                    self.assertIn('native-run', self.events); self.assertIn('verify', self.events)
                self.assertIn('revocation', self.events); self.assertIn('cleanup', self.events)
                self.assertFalse(probe._PERMITS)
            with self.assertRaises(ValueError): await REAL_PROBE(active, 'tools')
        self.assertIs(signal.getsignal(signal.SIGUSR1), before)
        self.assertFalse((self.rt / policy.QUALIFICATION_FILE).exists())
        self.assertFalse((self.rt / policy.REGISTRATION_FILE).exists())

    async def test_external_gateway_network_refuses_before_agent_and_retains_failure(self):
        def change(name, value):
            if name == 'model-gateway': value['NetworkSettings']['Networks']['external'] = {}
        self.observation_change = change
        with self.assertRaises(ValueError), self.base.open() as active:
            images.build(active); await REAL_PROBE(active, 'tools')
        self.assertNotIn('native-setup', self.events); self.assertNotIn('native-run', self.events)
        self.assertTrue((self.rt / 'no-cutoff-recovery-rehearsal-tools-failure.json').is_file())
        self.assertIn('cleanup', self.events)

    async def test_result_change_after_lifecycle_cannot_create_passed_evidence(self):
        def change():
            path = self.environments[-1].rt / fixture.FIXTURE_FILE
            path.write_bytes(path.read_bytes() + b' ')
        self.after_phases = change
        with self.assertRaises(ValueError), self.base.open() as active:
            images.build(active); await REAL_PROBE(active, 'tools')
        self.assertFalse(list(self.rt.glob('native-no-cutoff-recovery-tools-*/evidence.json')))
        self.assertTrue((self.rt / 'no-cutoff-recovery-rehearsal-tools-failure.json').is_file())

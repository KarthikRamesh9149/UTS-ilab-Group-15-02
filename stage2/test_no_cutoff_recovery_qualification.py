"""Local synthetic producers and real strict readers, never native qualification."""
import ast
import asyncio
from copy import deepcopy
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import time
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import no_cutoff_recovery_files as files
import no_cutoff_recovery_fixture as fixture
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_probe as probe
import no_cutoff_recovery_qualification as reader
import no_cutoff_recovery_result as retained
import qualify_no_cutoff_recovery as qualifier
import test_no_cutoff_recovery_execution as local
from test_no_cutoff_recovery_setup import Environment
from test_no_cutoff_recovery_runtime import save
from test_retry_gateway import Clock, Event, REQUEST
from test_credit_only_gateway import TOKEN
from credit_only_accounting import PassiveTrialTrace, summarise
from credit_only_gateway import CreditOnlyError
from model_protocol import freeze_protocol
from retry_runtime import activate
from custom_dispatch_stop import BoundaryStop
from trial_execution import execute_phases

STAGE = Path(__file__).resolve().parent


def request():
    value = deepcopy(REQUEST)
    value['tools'] = [dict(type='function', function=dict(name=n, parameters={'type':'object','properties':{}}))
        for n in ('execute','complete_task')]
    return value


def feedback(value, response):
    result = deepcopy(value)
    result['messages'].extend([response['choices'][0]['message'],
        dict(role='tool', tool_call_id=fixture.TOKEN, content=fixture.MARKER)])
    return result


class FixtureTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.rt = self.root / '.runtime/stage2'; self.rt.mkdir(parents=True, mode=0o700)
        self.network = self.enterContext(patch.object(fixture, 'network_isolation'))
        self.clock = Clock()

    def gateway(self, mode='tools'):
        from scored_gateway import durable_json
        record = fixture.document(mode); durable_json(self.rt / fixture.FIXTURE_FILE, record)
        freeze_protocol(self.rt, policy.SETTINGS)
        activate(self.rt, record['trial_id'], 900, policy.SETTINGS, self.clock)
        provider = fixture.SyntheticProvider(fixture.SYNTHETIC_KEY, mode=mode, clock=self.clock,
            generation_enabled=True, completion_wait_seconds=960)
        value = fixture.FixtureSession(self.root, record['trial_id'], 'final', TOKEN, provider,
            settings=policy.SETTINGS, clock=self.clock)
        value.cancelled = Event(self.clock); self.addCleanup(value.close)
        return value

    def test_two_actual_fake_dialogue_rounds_three_physical_records_and_unknown_costs(self):
        gateway = self.gateway()
        first = gateway.complete(TOKEN, request())
        second = gateway.complete(TOKEN, feedback(request(), first))
        self.assertEqual(first['choices'][0]['message']['tool_calls'][0]['function']['name'], 'execute')
        self.assertEqual(second['choices'][0]['message']['tool_calls'][0]['function']['name'], 'complete_task')
        summary = summarise(self.rt, gateway.trial_id)
        self.assertEqual(summary['requests'], 3); self.assertEqual(summary['unknown_cost_requests'], 3)
        self.assertIsNone(summary['charged_usd'])
        self.assertEqual(len(list(gateway.evidence.glob('*.retry.json'))), 1)
        with self.assertRaises((CreditOnlyError, ValueError)): gateway.complete(TOKEN, feedback(request(), first))

    def test_no_model_modes_refuse_and_latch(self):
        for mode in fixture.NO_MODEL:
            provider = fixture.SyntheticProvider(fixture.SYNTHETIC_KEY, mode=mode, clock=self.clock,
                generation_enabled=True, completion_wait_seconds=960)
            with self.assertRaises(ValueError): provider.complete(request(), on_response_headers=lambda _: None)
            self.assertTrue(provider.failed); self.assertEqual(provider.calls, 0)

    def test_missing_actual_feedback_refuses(self):
        gateway = self.gateway(); first = gateway.complete(TOKEN, request())
        bad = feedback(request(), first); bad['messages'][-1]['content'] = fixture.COMMAND
        with self.assertRaises((CreditOnlyError, ValueError)): gateway.complete(TOKEN, bad)
        self.assertTrue(gateway.client.failed)

    def test_changed_fixture_is_terminal_and_restoration_cannot_resume(self):
        gateway = self.gateway(); path = self.rt / fixture.FIXTURE_FILE; raw = path.read_bytes()
        path.write_bytes(raw + b' ')
        with self.assertRaises((CreditOnlyError, ValueError)): gateway.complete(TOKEN, request())
        path.write_bytes(raw)
        with self.assertRaises((CreditOnlyError, ValueError)): gateway.complete(TOKEN, request())
        self.assertEqual(gateway.client.calls, 0)

    def test_private_inputs_no_paid_metadata_and_synthetic_credentials_only(self):
        gateway = self.gateway()
        path = self.rt / fixture.FIXTURE_FILE; path.chmod(0o644)
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, gateway.trial_id, 'final')
        path.chmod(0o600)
        (self.rt / policy.QUALIFICATION_FILE).symlink_to('absent')
        with self.assertRaises(ValueError): fixture.read_fixture(self.rt, gateway.trial_id, 'final')
        with self.assertRaises(ValueError):
            fixture.SyntheticProvider('not-the-synthetic-key', mode='tools', clock=self.clock,
                generation_enabled=True, completion_wait_seconds=960)

    def test_same_byte_fixture_replacement_latches_gateway_stopped(self):
        gateway = self.gateway()
        path = self.rt / fixture.FIXTURE_FILE; raw = path.read_bytes()
        path.rename(path.with_suffix('.retained'))
        save(self.root, '.runtime/stage2/' + fixture.FIXTURE_FILE, raw)
        with self.assertRaises(ValueError): gateway.require_session_policy()
        self.assertTrue(gateway.stopped)


class FakeContainer(Environment):
    """Only tests: native container commands are mocked, original callback real."""
    def __init__(self, mode):
        super().__init__(); self.mode = mode; self.original_calls = 0
        self.started = False
    async def exec(self, command, *, timeout_sec, env=None):
        from task_preparation import COMMAND
        if command == COMMAND:
            self.original_calls += 1
            if self.mode == 'cancel_setup':
                self.started = True
                await asyncio.Event().wait()
            return NS(return_code=42 if self.mode == 'prepare_nonzero' else 0,
                stdout='UTS_PACKAGE_METADATA_NOT_APPLICABLE\n' if self.mode == 'prepare_not_applicable' else 'synthetic text',
                stderr='synthetic error' if self.mode == 'prepare_nonzero' else '')
        if command.startswith('test -f ' + probe.CONTROL):
            return NS(return_code=0 if self.started else 1, stdout='', stderr='')
        return NS(return_code=0, stdout='', stderr='')


class QualificationCases(local.LocalFiles, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.protect(Path(temp.name).resolve())
        self.rt = self.root / '.runtime/stage2'; self.rt.mkdir(parents=True, mode=0o700)
        (self.root / '.runtime').chmod(0o700)
        self.enterContext(patch.object(fixture, 'network_isolation'))
        self.sources = retained.setup._bindings()
        self.proof = dict(sources=self.sources, sources_sha256=policy.fingerprint(self.sources),
            image_build_sha256='1'*64, gateway_image='sha256:'+'8'*64, guard_image='sha256:'+'7'*64)
        self.official = dict(image_id='sha256:'+'9'*64, agent_timeout_seconds=180, verifier_timeout_seconds=30)
        files.save(self.rt / policy.RUNTIME_FILE, dict(task_inventory={probe.RESOURCE_TASK:self.official}))
        save(self.root, 'stage2/fixtures/lifecycle/instruction.md', b'Harmless local fixture\n')
        self.bundle = b'synthetic-test-bundle-not-an-interpreter'
        self.enterContext(patch.object(policy, 'PYTHON_SHA256', hashlib.sha256(self.bundle).hexdigest()))

    async def produce(self, mode):
        relative = '.runtime/stage2/native-no-cutoff-recovery-' + mode + '-local'
        root = self.root / relative; root.mkdir(mode=0o700)
        rt = root / '.runtime/stage2'; rt.mkdir(parents=True, mode=0o700); rt.parent.chmod(0o700)
        (root / 'stage2').mkdir(mode=0o700)
        record = fixture.document(mode); trial_id = record['trial_id']
        files.save(root / 'stage2/input_manifest.json', dict(all_task_ids=['lifecycle'],development_ids=['lifecycle']))
        files.save(rt / fixture.FIXTURE_FILE, record)
        save(root, '.runtime/stage2/synthetic-provider.txt', ('OPENROUTER_API_KEY='+fixture.SYNTHETIC_KEY+'\n').encode())
        save(root, '.runtime/stage2/python-runtime.tar.gz', self.bundle)
        freeze_protocol(rt, policy.SETTINGS)
        files.save(root / 'admission.json', dict(kind='actual_native_recovery_fixture_admission',
            resource_task_id=probe.RESOURCE_TASK, official=self.official, task_id='lifecycle',trial_id=trial_id,
            setup_timeout_seconds=900,instruction_sha256=files.libraries.read(self.root,'stage2/fixtures/lifecycle/instruction.md'),
            sources_sha256=self.proof['sources_sha256'],paid_launch_ready=False))
        files.save(self.rt / ('no-cutoff-recovery-rehearsal-'+mode+'.json'),
            dict(kind='one_shot_native_recovery_rehearsal',mode=mode,experiment=policy.EXPERIMENT,
                runtime_path=relative,sources_sha256=self.proof['sources_sha256'],
                image_build_sha256=self.proof['image_build_sha256'],automatic_resume=False,paid_launch_ready=False,
                pid=os.getpid(),started_utc='2026-09-29T22:00:00Z'))
        trial = rt / 'scored-trials' / trial_id; trial.mkdir(parents=True,mode=0o700); trial.parent.chmod(0o700)
        start = dict(trial_id=trial_id,task_id='lifecycle',stage='final',harness=policy.CONDITION,
            recovery_experiment=policy.EXPERIMENT,recovery_fixture=fixture.FIXTURE_KIND,
            recovery_fixture_sha256=policy.fingerprint(record),model_protocol_sha256=policy.MODEL_SHA256,
            gateway_image_id=self.proof['gateway_image'],guard_image_id=self.proof['guard_image'],
            accounting_mode='provider-credit-only',project='synthetic-owned',started_utc='2026-09-29T22:00:00Z')
        files.save(trial / 'started.json',start); files.save(trial / 'compose.json',{})
        clock = Clock(); clock.wall = time.time
        provider = fixture.SyntheticProvider(fixture.SYNTHETIC_KEY,mode=mode,clock=clock,
            generation_enabled=True,completion_wait_seconds=240)
        gateway = fixture.FixtureSession(root,trial_id,'final',TOKEN,provider,settings=policy.SETTINGS,clock=clock)
        gateway.cancelled = Event(clock)
        environment = FakeContainer(mode); observed = {}
        preparation = probe._Preparation(mode,observed)
        trace = PassiveTrialTrace(trial / 'traces',trial_id=trial_id,task_id='lifecycle',
            harness=policy.CONDITION,protocol_sha256=policy.MODEL_SHA256)
        class Agent:
            async def setup(self, env): pass
            async def run(self, *args):
                activate(rt,trial_id,180,policy.SETTINGS,clock)
                if mode == 'boundary_stop':
                    files.save(rt / 'operator-stop-request.json',dict(automatic_resume=False,source='local-synthetic-test'))
                    os.kill(os.getpid(), signal.SIGUSR1)
                first = gateway.complete(TOKEN,request())
                gateway.complete(TOKEN,feedback(request(),first))
        class Verifier:
            def __init__(self,*args): pass
            async def verify(self): return NS(model_dump=lambda **kwargs: {'rewards':{'reward':1}})
        async def revoke(): gateway.close()
        evidence = {}
        task = NS(instruction='harmless',config=NS(agent=NS(timeout_sec=180,user=None),verifier=NS(timeout_sec=30,user=None)))
        with BoundaryStop(rt) as stop:
            try:
                await execute_phases(agent=Agent(),environment=environment,task=task,paths=NS(),
                    revoke_model=revoke,setup_timeout_seconds=900,verifier_factory=Verifier,
                    phase_observer=trace,prepare_environment=preparation.prepare,retained_result=evidence)
            except asyncio.CancelledError:
                self.assertEqual(mode,'cancel_setup')
                if asyncio.current_task().cancelling(): asyncio.current_task().uncancel()
                evidence['status']='interrupted'
            finally: gateway.close()
            if mode == 'boundary_stop': self.assertTrue(stop.requested())
        result = dict(start,**evidence,task_image_id=self.official['image_id'],
            containers_removed=True,networks_removed=True,volumes_removed=True)
        result['billing'] = summarise(rt,trial_id)
        result['trace'] = trace.finish(rt / 'scored-attempts' / trial_id,result['billing'])
        result['recovery_preparation'] = preparation.finish()
        files.save(trial / 'result.json',result)
        self.assertEqual(environment.original_calls,1)
        case = dict(kind=probe.KIND,mode=mode,condition=policy.CONDITION,status='passed',live_api_calls=0,
            preparation_outcome=policy.PREPARATION_OUTCOMES[mode],checks=dict.fromkeys(sorted(policy.probe_checks(mode)),True),
            runtime_path=relative,preparation_observation_sha256=policy.fingerprint(result['recovery_preparation']))
        supporting = {str(p.relative_to(self.root)) for p in root.rglob('*') if p.is_file() and p.name != 'gateway.lock'}
        bound = files.capture(self.root,supporting)[0]
        files.save(root / 'producer.json',dict(kind='actual_native_recovery_supporting_producers',mode=mode,
            runtime_path=relative,source_sha256=self.proof['sources_sha256'],
            image_build_sha256=self.proof['image_build_sha256'],files=bound,paid_launch_ready=False))
        files.save(root / 'evidence.json',case)
        return case, result

    async def test_all_six_real_local_lifecycles_and_actual_producer_reads(self):
        for mode in policy.PROBE_MODES:
            with self.subTest(mode=mode):
                case,result = await self.produce(mode)
                bound = reader.case_files(self.root,case,self.proof)
                self.assertIn(case['runtime_path']+'/producer.json',bound)
                if mode in fixture.NO_MODEL:
                    self.assertEqual(result['billing']['requests'],0)
                    self.assertEqual(set(result['phase_seconds']),{'setup'})
                    self.assertTrue(retained.empty_agent_context(result['agent_context']))
                else: self.assertEqual(result['billing']['requests'],3)

    async def test_changed_actual_producer_fails_even_with_saved_passed_flag(self):
        case,result = await self.produce('prepare_nonzero')
        path = self.root / case['runtime_path'] / '.runtime/stage2/scored-trials' / result['trial_id'] / 'result.json'
        path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError): reader.case_files(self.root,case,self.proof)

    async def test_absent_deadline_cannot_be_fabricated_for_unexecuted_phase(self):
        case,result = await self.produce('prepare_exception')
        path = self.root / case['runtime_path'] / '.runtime/stage2/retry-lifecycle'
        path.mkdir(mode=0o700); files.save(path / (result['trial_id']+'.json'),{})
        with self.assertRaises(ValueError): reader.case_files(self.root,case,self.proof)

    def test_generated_preimport_program_is_valid_and_checks_complete_union(self):
        raw = (STAGE / 'no_cutoff_recovery_bootstrap.py').read_bytes()
        save(self.root,'stage2/no_cutoff_recovery_bootstrap.py',raw)
        live = dict(root=self.root,inputs={'files':{'stage2/no_cutoff_recovery_bootstrap.py':hashlib.sha256(raw).hexdigest()}})
        with patch.object(qualifier.session,'_live',return_value=live):
            program = qualifier._program(object())
        ast.parse(program)
        self.assertIn('b.check(p["sources"])',program)
        self.assertLess(program.index('b.check(p["sources"])'),program.index('import qualify_no_cutoff_recovery as worker'))
        self.assertIn('sys.modules[b.__name__]=b',program)

    def test_existing_qualification_intent_is_never_retried(self):
        files.save(self.rt / qualifier.INTENT,{'started':True})
        with self.assertRaises(ValueError): qualifier._fresh(self.root)

    async def test_saved_description_never_qualifies(self):
        with self.assertRaises(ValueError): await qualifier.qualify({'paid_launch_ready':True})

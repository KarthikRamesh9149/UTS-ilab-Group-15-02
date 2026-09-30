"""Real local orchestration/producer reads; native Docker/regressions mocked."""
import asyncio
from copy import deepcopy
import hashlib
import inspect
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import AsyncMock, patch

import no_cutoff_recovery_files as files
import no_cutoff_recovery_fixture as fixture
import no_cutoff_recovery_images as images
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_probe as probe
import no_cutoff_recovery_qualification as reader
import no_cutoff_recovery_session as session
import qualify_no_cutoff_recovery as qualifier
import test_no_cutoff_recovery_images as image_fixture
import test_no_cutoff_recovery_qualification as cases
import test_no_cutoff_recovery_connection as connection_fixture
from test_no_cutoff_recovery_runtime import save

STAGE=Path(__file__).resolve().parent
REAL_REGRESSION=qualifier._regression
LOCAL_RUN=subprocess.run


class QualifierTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.image=image_fixture.ImageTests('runTest')
        self.image._callCleanup=lambda function,*args,**kwargs:function(*args,**kwargs)
        self.addCleanup(self.image.doCleanups); self.image.setUp()
        self.q=self.image.q; self.root=self.q.root; self.rt=self.root/'.runtime/stage2'
        self.bundle=b'local-synthetic-bundle-not-native-runtime'
        self.enterContext(patch.object(policy,'PYTHON_SHA256',hashlib.sha256(self.bundle).hexdigest()))
        self.enterContext(patch.object(fixture,'network_isolation'))
        self.enterContext(patch.object(probe,'_environment'))
        self.enterContext(patch.object(probe,'_owned_clear'))
        all_names=set(self.q.f.final['sources'])|policy.REQUIRED_SOURCE_FILES
        self.q.bound.clear()
        for name in all_names:
            raw=(STAGE/name).read_bytes(); save(self.root,'stage2/'+name,raw)
            self.q.bound[name]=hashlib.sha256(raw).hexdigest()
        self.q.f.final['sources']={n:self.q.bound[n] for n in self.q.f.final['sources']}
        self.q.f.final['sources_sha256']=policy.fingerprint(self.q.f.final['sources'])
        self.q.f.final['python_runtime']={'sha256':policy.PYTHON_SHA256}
        raw=json.dumps(self.q.f.final).encode()
        for name,value in (('ORIGINAL_SOURCE_SET',self.q.f.final['sources_sha256']),
                ('ORIGINAL_QUALIFICATION',policy.fingerprint(self.q.f.final)),
                ('ORIGINAL_QUALIFICATION_FILE_SHA256',hashlib.sha256(raw).hexdigest())):
            self.enterContext(patch.object(policy,name,value))
        save(self.root,'.runtime/stage2/'+policy.ORIGINAL_FILE,raw)
        predecessor=dict(self.q.f.predecessor,qualification_sha256=policy.ORIGINAL_QUALIFICATION,
            sources_sha256=policy.ORIGINAL_SOURCE_SET)
        save(self.root,'.runtime/stage2/'+policy.PREDECESSOR_FILE,json.dumps(predecessor).encode())
        self.q.original=session._inputs(self.root)
        self.q.pred.update(predecessor=predecessor,current_sources_sha256=policy.fingerprint(self.q.bound),
            copied_files=self.q.original['files'])
        self.official=dict(image_id='sha256:'+'9'*64,agent_timeout_seconds=180,verifier_timeout_seconds=30)
        self.q.host.update(sources=self.q.bound,sources_sha256=policy.fingerprint(self.q.bound),
            original_qualification_sha256=policy.ORIGINAL_QUALIFICATION,
            predecessor_sha256=policy.fingerprint(predecessor),task_inventory={probe.RESOURCE_TASK:self.official})
        # The case helper binds the unchanged harmless source, not a benchmark payload.
        self.sources=deepcopy(self.q.bound)
        self.proof=None; self.calls=[]; self.fail_mode=None; self.tamper_after=None
        self.regression=self.enterContext(patch.object(qualifier,'_regression',side_effect=self.regressions))
        self.rehearsal=self.enterContext(patch.object(probe,'probe',side_effect=self.rehearse))

    def open(self): return session.open_session(self.q.stream)

    async def regressions(self,active,folder,bound):
        session.recheck(active); files.check(self.root,bound)
        files.save(folder/'regression.json',dict(modules=list(policy.test_modules(self.q.f.final)),
            tests=1,passed=True,skipped=0,errors=0,failures=0))
        save(self.root,str((folder/'regression.txt').relative_to(self.root)),b'LOCAL MOCK native regression producer\n')

    async def rehearse(self,active,mode):
        session.recheck(active); self.calls.append(mode)
        self.proof=dict(images.qualification_binding(active),sources=deepcopy(self.q.bound),
            sources_sha256=policy.fingerprint(self.q.bound))
        if mode==self.fail_mode: raise asyncio.CancelledError('local synthetic qualifier cancellation')
        case,result=await cases.QualificationCases.produce(self,mode)
        if mode==self.tamper_after:
            path=self.rt/policy.IMAGE_INTENT_FILE; raw=path.read_bytes()
            path.rename(path.with_suffix('.retained')); save(self.root,str(path.relative_to(self.root)),raw)
        return case

    async def test_actual_orchestration_six_retained_cases_real_reader_then_no_second_qualification(self):
        with self.open() as active:
            completed=await qualifier.qualify(active)
            verified=reader.verify(active)
        self.assertEqual(self.calls,list(policy.PROBE_MODES)); self.regression.assert_awaited_once()
        self.assertEqual(completed['native_cases'],6); self.assertFalse(completed['paid_launch_ready'])
        self.assertEqual(len(verified['proof']['evidence_files']),14)
        self.assertEqual(len(verified['proof']['image_evidence_files']),2)
        self.assertGreater(len(verified['files']),len(self.q.bound))
        with self.open() as active:
            with self.assertRaises(ValueError): await qualifier.qualify(active)
        self.assertEqual(self.rehearsal.await_count,6)

    async def test_cancelled_middle_case_retains_failure_and_earlier_producers(self):
        self.fail_mode='prepare_nonzero'
        with self.assertRaises(asyncio.CancelledError),self.open() as active:
            await qualifier.qualify(active)
        self.assertEqual(self.calls,list(policy.PROBE_MODES[:3]))
        self.assertTrue((self.rt/qualifier.FAILURE).is_file())
        self.assertEqual(json.loads((self.rt/qualifier.FAILURE).read_bytes())['stage'], 'native_case_prepare_nonzero')
        self.assertFalse((self.rt/policy.QUALIFICATION_FILE).exists())
        self.assertTrue(list(self.rt.glob('native-no-cutoff-recovery-tools-*/evidence.json')))

    async def test_same_byte_earlier_producer_replacement_refuses_completion(self):
        self.tamper_after='tools'
        with self.assertRaises(ValueError),self.open() as active: await qualifier.qualify(active)
        self.assertEqual(self.calls,['tools']); self.assertTrue((self.rt/qualifier.FAILURE).is_file())
        self.assertFalse((self.rt/qualifier.RESULT).exists())

    async def test_late_failure_marker_blocks_a_previously_written_proof(self):
        with self.open() as active: await qualifier.qualify(active)
        files.save(self.rt/qualifier.FAILURE,{'local_synthetic_late_failure':True})
        with self.assertRaises(ValueError),self.open() as active: reader.verify(active)

    async def test_cancel_during_owned_child_creation_settles_and_cleans_only_that_group(self):
        child=NS(pid=999998,returncode=None,communicate=AsyncMock(),wait=AsyncMock(return_value=-15))
        owner=asyncio.current_task()
        async def spawn(*args,**kwargs):
            owner.cancel('local-owned-regression-spawn'); await asyncio.sleep(0); return child
        folder=self.rt/'native-no-cutoff-recovery-qualification-child'; folder.mkdir(mode=0o700)
        with self.open() as active,patch.object(asyncio,'create_subprocess_exec',side_effect=spawn), \
                patch.object(os,'killpg') as kill:
            with self.assertRaises(asyncio.CancelledError): await REAL_REGRESSION(active,folder,{})
            owner.uncancel()
            kill.assert_called_once_with(child.pid,signal.SIGTERM); child.communicate.assert_not_called()
        self.assertTrue((folder/'regression.txt').is_file())

    async def test_real_harmless_child_cleanup_leaves_no_running_owned_process(self):
        child=await asyncio.create_subprocess_exec(sys.executable,'-I','-B','-c',
            'import time; time.sleep(30)',start_new_session=True,env={'PATH':'/usr/bin:/bin'})
        try:
            await qualifier._stop_regression(child)
            self.assertIsNotNone(child.returncode)
        finally:
            if child.returncode is None: child.kill(); await child.wait()


class RegressionProgramTests(connection_fixture.LocalTree):
    def child(self,*,drift=False,effect=False):
        raw=(b'import os\nos.environ["EXTERNAL_CREDENTIAL"]="synthetic"\n' if effect else b'')
        raw+=b'import ipaddress\n'+inspect.getsource(qualifier._network_guard).encode()
        raw+=b'def regression_worker(payload): print("local-bootstrap-only-not-native-qualification")\n'
        name='stage2/qualify_no_cutoff_recovery.py'; self.f.e.save(name,raw)
        bound=dict(self.files); bound[name]=hashlib.sha256(raw).hexdigest()
        with patch.object(session,'_live',return_value={'root':self.root,'inputs':{'files':bound}}):
            program=qualifier._program(object())
        # Only native platform/root/interpreter context is mocked in this local
        # child. Actual complete union, private bytes and import effects remain.
        setup='b.ROOT=pathlib.Path('+repr(str(self.root))+');b.QUALIFICATION_SHA='+repr(bound[qualifier.bootstrap.QUALIFICATION])+';b.context=lambda:None\n'
        if sys.platform == 'darwin': setup+='b.acl=lambda path:None\n'  # Linux ACL API is absent on this local Python.
        program=program.replace('ids=b.check(p["sources"])',setup+'ids=b.check(p["sources"])',1)
        if drift: bound.pop('stage2/no_cutoff_recovery_service.py')
        payload=dict(sources=bound,files={},folder='.runtime/stage2/native-no-cutoff-recovery-qualification-child',modules=[])
        return LOCAL_RUN([sys.executable,'-I','-B','-c',program],input=json.dumps(payload),
            capture_output=True,text=True,timeout=30,env={'PATH':'/usr/bin:/bin','PYTHON_DOTENV_DISABLED':'1'})

    def test_actual_isolated_program_checks_complete_sources_before_import(self):
        child=self.child(); self.assertEqual(child.returncode,0,child.stderr)
        self.assertEqual(child.stdout.strip(),'local-bootstrap-only-not-native-qualification')

    def test_missing_source_refuses_before_worker(self):
        child=self.child(drift=True); self.assertNotEqual(child.returncode,0)
        self.assertNotIn('local-bootstrap-only-not-native-qualification',child.stdout)

    def test_environment_effect_during_bound_import_refuses_before_worker(self):
        child=self.child(effect=True); self.assertNotEqual(child.returncode,0)
        self.assertNotIn('local-bootstrap-only-not-native-qualification',child.stdout)

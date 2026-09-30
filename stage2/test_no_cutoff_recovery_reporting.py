"""Actual synthetic files/traces/tar bytes; native qualification/host facts mocked."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import credit_only_accounting as accounting
from local_trace import observation
import no_cutoff_recovery_archive as archive
import no_cutoff_recovery_bootstrap as boot
import no_cutoff_recovery_files as files
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_report as report
import no_cutoff_recovery_reporting as reporting
import no_cutoff_recovery_result as retained
import no_cutoff_recovery_service as service
import no_cutoff_recovery_session as session
import no_cutoff_recovery_study as study
import run_no_cutoff_recovery as runner
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_policy import Fixture, qualification
from test_no_cutoff_recovery_setup import Environment
from test_no_cutoff_recovery_runtime import save

STAGE = Path(__file__).resolve().parent
BASE = int(datetime.fromisoformat('2026-09-29T01:00:00+00:00').timestamp()) * 1_000_000_000


class ReportingTests(LocalFiles, unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve()); self.f = Fixture(self, self.root)
        self.rt = self.root / report.RT
        self.sources = {}
        for name in set(self.f.final['sources']) | policy.REQUIRED_SOURCE_FILES:
            raw = (STAGE / name).read_bytes(); save(self.root, 'stage2/' + name, raw)
            self.sources[name] = hashlib.sha256(raw).hexdigest()
        for name in self.f.final['sources']:
            if name != 'scored_trial.py': self.f.final['sources'][name] = self.sources[name]
        self.f.final['sources_sha256'] = policy.fingerprint(self.f.final['sources'])
        original_raw = json.dumps(self.f.final).encode()
        for name, value in (('ORIGINAL_SOURCE_SET', self.f.final['sources_sha256']),
                ('ORIGINAL_QUALIFICATION', policy.fingerprint(self.f.final)),
                ('ORIGINAL_QUALIFICATION_FILE_SHA256', hashlib.sha256(original_raw).hexdigest())):
            self.enterContext(patch.object(policy, name, value))
        self.f.predecessor.update(qualification_sha256=policy.ORIGINAL_QUALIFICATION, sources_sha256=policy.ORIGINAL_SOURCE_SET)
        self.cells = policy.cells(self.f.manifest)
        self.host = dict(task_inventory={c['task_id']: dict(agent_timeout_seconds=180.0,
            verifier_timeout_seconds=30.0, cpus=1, memory_mb=2048, image_id='sha256:'+'9'*64) for c in self.cells})
        self.proof = qualification(self.f.final, self.f.predecessor, self.f.manifest)
        self.proof.update(sources=self.sources, sources_sha256=policy.fingerprint(self.sources),
            runtime_identity_sha256=policy.fingerprint(self.host),
            orchestration_changes=policy.source_transition(self.f.final, self.sources))
        for mapping in (self.proof['evidence_files'], self.proof['image_evidence_files']):
            for name in mapping:
                raw = b'{"local_test_fixture_not_native":true}'; save(self.root, name, raw)
                mapping[name] = hashlib.sha256(raw).hexdigest()
        self.block = policy.registration(self.f.final, self.f.predecessor, self.f.manifest, self.proof)
        self.f.proof = self.proof; self.f.block = self.block; self.f.write()
        self.f.save(policy.RUNTIME_FILE, self.host)
        save(self.root, 'stage2/input_manifest.json', self.f.manifest_raw)
        self.bound = {'stage2/'+n:h for n,h in self.sources.items()}
        for name in (*archive.qualification_inputs(), policy.REGISTRATION_FILE):
            self.bound.update(files.capture(self.root, [report.RT+name])[0])
        self.bound.update(self.proof['evidence_files']); self.bound.update(self.proof['image_evidence_files'])
        self.live = dict(root=self.root, inputs={'sources': self.sources, 'files': self.bound},
            host=self.host, predecessor={'predecessor': self.f.predecessor}, witness=object())
        self.enterContext(patch.object(service, 'ROOT', self.root))
        self.enterContext(patch.object(boot, 'ROOT', self.root))
        self.enterContext(patch.object(session, '_live', return_value=self.live))
        self.rechecks = self.enterContext(patch.object(session, 'recheck'))
        self.enterContext(patch.object(session.handoff, '_no_stop'))
        self.enterContext(patch.object(report.qualification, 'for_dispatch', side_effect=lambda active:dict(root=self.root,
            proof=deepcopy(self.proof), block=deepcopy(self.block), files=self.bound.copy(),
            identities=files.capture(self.root,self.bound)[1])))
        self.completion = self.enterContext(patch.object(service, 'completed_operation', return_value={'files':{},'identities':{}}))
        self.enterContext(patch.object(runner, '_owned_resources_clear'))
        self.resources = self.enterContext(patch.object(report.original_report, '_resources'))

    async def produce(self, rewards=(1,0,None), requests=0):
        for index,(cell,reward) in enumerate(zip(self.cells,rewards)):
            name=cell['trial_id']; trial=report.RT+'scored-trials/'+name
            start=dict(trial_id=name,task_id=cell['task_id'],harness=policy.CONDITION,stage='final',
                recovery_experiment=policy.EXPERIMENT,recovery_registration_sha256=policy.fingerprint(self.block),
                model_protocol_sha256=policy.MODEL_SHA256,accounting_mode='provider-credit-only',
                gateway_image_id=self.proof['gateway_image'],guard_image_id=self.proof['guard_image'],
                project='uts-scored-'+format(index+1,'012x'),started_utc='2026-09-29T00:00:00Z',status='starting')
            save(self.root,trial+'/started.json',json.dumps(start).encode()); save(self.root,trial+'/compose.json',b'{}')
            observer=retained.RetainedPreparation(); environment=Environment()
            if reward is None:
                async def nonzero(*args,**kwargs): return NS(return_code=42,stdout='local synthetic text',stderr='')
                environment.exec=nonzero
            try: await observer.prepare(environment)
            except RuntimeError:
                if reward is not None: raise
            observed=observer.finish()
            count=requests if index==0 else 0
            account=report.RT+'scored-attempts/'+name
            save(self.root,account+'/started.json',b'{}')
            for request in range(count):
                save(self.root,account+f'/{request:06d}.request.json',b'opaque unparsed model payload')
            billing=accounting.summarise(self.rt,name)
            result=dict(start,status='setup_failed' if reward is None else 'verified',
                task_image_id=self.host['task_inventory'][cell['task_id']]['image_id'],
                agent_error_type='RuntimeError' if reward is None else None,verifier_error_type=None,
                verifier_result=None if reward is None else {'rewards':{'reward':reward}},
                phase_seconds={'setup':1.0} if reward is None else {'setup':1.0,'agent':2.0,'verifier':1.0},
                model_revoked=True,containers_removed=True,networks_removed=True,volumes_removed=True,
                cleanup_errors=[],billing=billing,recovery_preparation=observed)
            specs=[('trial',0,0,2,'error',None),('setup',1,0,1,'error',None),('cleanup',2,1,2,'ok',None)] if reward is None else [
                ('trial',0,0,5,'ok',None),('setup',1,0,1,'ok',None),('agent',2,1,3,'ok',None),
                ('verifier',3,3,4,'ok',reward),('cleanup',4,4,5,'ok',None)]
            for kind,sequence,begin,end,status,score in specs:
                event=observation(trial_id=name,task_id=cell['task_id'],harness=policy.CONDITION,
                    protocol_sha256=policy.MODEL_SHA256,kind=kind,sequence=sequence,
                    started_ns=BASE+index*10_000_000_000+begin*1_000_000_000,
                    ended_ns=BASE+index*10_000_000_000+end*1_000_000_000,status=status,reward=score,
                    metrics={'duration_seconds':float(end-begin),**({'requests':count} if kind=='trial' else {})})
                save(self.root,trial+'/traces/'+event['event_id']+'.json',json.dumps(event).encode())
            result['trace']=dict(status='metadata_spool_not_cloud_export',events=len(specs),generations=0,
                missing_generation_timings=count,unknown_cost_requests=count)
            save(self.root,trial+'/result.json',json.dumps(result).encode())
            if reward is not None:
                save(self.root,report.RT+'retry-lifecycle/'+name+'.json',json.dumps(dict(trial_id=name,
                    model_protocol_sha256=policy.MODEL_SHA256,boot_id='local-test-boot',deadline_monotonic=180.0,
                    deadline_utc=BASE/1e9+index*10+1+180.0)).encode())
        files.save(self.rt/runner.INTENT,dict(registration_sha256=policy.fingerprint(self.block)))
        files.save(self.rt/runner.RESULT,dict(status='complete',intended=3,completed=3,stop_markers=[],
            dispatch_intent_sha256=files.capture(self.root,[report.RT+runner.INTENT])[0][report.RT+runner.INTENT]))

    def collect(self): return report.collect(object())

    def packed(self,data):
        record,state=archive.inventory(data); stream=io.BytesIO(); receipt=archive.pack(stream,record,state)
        framed=io.BytesIO(stream.getvalue()); compressed=bytearray()
        while raw:=framed.read(8):
            size=struct.unpack('!Q',raw)[0]; compressed.extend(framed.read(size))
        path=self.root/'private-backup'; path.mkdir(mode=0o700)
        reporting._private_bytes(path/'evidence.tar.gz',bytes(compressed))
        return path/'evidence.tar.gz',record,state,receipt

    async def test_actual_three_results_phase_accounting_and_separate_nulls(self):
        await self.produce(requests=105); data,state=self.collect()
        self.assertEqual((data['aggregate']['passed'],data['aggregate']['failed'],data['aggregate']['no_verifier_result']),(1,1,1))
        self.assertEqual(data['aggregate']['unknown_cost_requests'],105); self.assertIsNone(data['aggregate']['total_cost_usd'])
        self.assertIsNone(data['rows'][2]['agent_seconds']); self.assertEqual(len(data['absent_paths']),1)
        report.validate(data,self.f.manifest,self.sources); report.reread(self.root,data,state)
        self.assertGreaterEqual(self.rechecks.call_count,2); self.assertEqual(self.completion.call_count,2)

    async def test_all_setup_failures_preserve_absent_deadline_directory(self):
        await self.produce(rewards=(None,None,None)); data,_=self.collect()
        self.assertEqual(data['aggregate']['no_verifier_result'],3)
        self.assertFalse((self.rt/'retry-lifecycle').exists())

    async def test_missing_or_changed_actual_result_never_becomes_completed(self):
        await self.produce(); path=self.rt/'scored-trials'/self.cells[1]['trial_id']/'result.json'; path.unlink()
        with self.assertRaises(ValueError): self.collect()

    async def test_final_native_observation_followed_by_actual_byte_rereads(self):
        await self.produce(); path=self.rt/'scored-trials'/self.cells[0]['trial_id']/'result.json'
        def change(project):
            raw=path.read_bytes(); path.rename(path.with_suffix('.retained')); save(self.root,str(path.relative_to(self.root)),raw)
        self.resources.side_effect=change
        with self.assertRaises(ValueError): self.collect()

    async def test_actual_archive_all_members_hashes_and_genuine_absence(self):
        await self.produce(); data,state=self.collect(); path,record,inventory_state,receipt=self.packed(data)
        verified=archive.verify(path,data,record,receipt,self.f.manifest,self.sources)
        self.assertEqual(verified['verified_result_files'],3); self.assertEqual(verified['verified_absent_paths'],1)
        self.assertFalse(verified['full_runtime_restore_exercised']); archive.recheck(record,inventory_state)
        report.reread(self.root,data,state)

    async def test_archive_corruption_or_truncation_is_not_verified(self):
        await self.produce(); data,_=self.collect(); path,record,_,receipt=self.packed(data); raw=path.read_bytes()
        path.write_bytes(raw[:-1])
        with self.assertRaises(ValueError): archive.verify(path,data,record,receipt,self.f.manifest,self.sources)
        path.write_bytes(bytes([raw[0]^1])+raw[1:])
        with self.assertRaises((ValueError,OSError)): archive.verify(path,data,record,receipt,self.f.manifest,self.sources)

    async def test_extra_registered_logs_keep_permissions_and_exclude_credentials(self):
        await self.produce(); trial=self.rt/'scored-trials'/self.cells[0]['trial_id']
        agent=trial/'agent'; agent.mkdir(mode=0o777); agent.chmod(0o777)
        save(self.root,str((agent/'payload.txt').relative_to(self.root)),b'private payload not returned')
        save(self.root,str((trial/'token').relative_to(self.root)),b'synthetic-excluded-secret')
        agent.chmod(0o777)  # The private test file helper normalises its ancestors.
        data,_=self.collect(); path,record,_,receipt=self.packed(data)
        archive.verify(path,data,record,receipt,self.f.manifest,self.sources)
        self.assertEqual(agent.stat().st_mode&0o777,0o777)
        self.assertIn(str((trial/'token').relative_to(self.root)),record['excluded'])
        self.assertNotIn(b'private payload',json.dumps(data).encode())

    async def test_projection_keeps_original_and_recovery_separate_and_csv_nulls(self):
        await self.produce(); data,_=self.collect()
        output=reporting.projection(data,{'receipt':{'sha256':'a'*64}})
        summary=json.loads(output['summary.json']); rows=json.loads(output['trials.json'])['rows']
        self.assertEqual(summary['original_full89_denominator'],89); self.assertEqual(summary['separate_recovery_denominator'],3)
        self.assertFalse(summary['recovery_merged_into_original89']); self.assertIsNone(rows[2]['reward'])
        self.assertNotIn('opaque',output['trials.csv'].decode())

    async def test_fixed_mac_backup_and_export_read_same_archive_and_refuse_repetition(self):
        await self.produce(); data,_=self.collect(); source,inventory,_,receipt=self.packed(data)
        compressed=source.read_bytes(); calls=[]
        netcup=self.root/'.runtime/netcup'; netcup.mkdir(mode=0o700)
        public=self.root/reporting.PUBLIC; public.mkdir(parents=True,mode=0o700)
        (public/'README.md').write_bytes(b'existing recovery documentation')
        value={'current_sources':self.sources}
        identities=files.capture(self.root,self.bound)[1]
        def capture(commit,mode,*,path=None):
            calls.append(mode)
            if mode=='audit': return dict(data,collected_utc=data['collected_utc']),value,identities
            written={name:reporting._private_bytes(path/name,raw) for name,raw in {
                'snapshot.json':reporting._json(data),'inventory.json':reporting._json(inventory),
                'evidence.tar.gz':compressed}.items()}
            return (data,inventory,receipt,written),value,identities
        with patch.object(reporting.handoff.launch,'REPO',self.root), \
                patch.object(reporting.connection,'prepare',return_value=(value,self.bound)), \
                patch.object(reporting.connection,'_local_identities',return_value=identities), \
                patch.object(reporting.connection.operator,'_current',side_effect=lambda value:files.check(self.root,self.bound)), \
                patch.object(reporting,'_manifest',return_value=self.f.manifest), \
                patch.object(reporting,'_capture',side_effect=capture):
            result=reporting.backup('a'*40)
            self.assertEqual(result['archive_sha256'],receipt['sha256'])
            before=(self.root/reporting.BACKUP/'evidence.tar.gz').read_bytes()
            with self.assertRaises(ValueError): reporting.backup('a'*40)
            projected=reporting.export('a'*40)
            self.assertEqual(projected['aggregate']['attempted'],3)
            with self.assertRaises(ValueError): reporting.export('a'*40)
            self.assertEqual((self.root/reporting.BACKUP/'evidence.tar.gz').read_bytes(),before)
        self.assertEqual(calls,['backup','audit'])
        self.assertEqual((public/'README.md').read_bytes(),b'existing recovery documentation')
        self.assertEqual(set(p.name for p in (self.root/reporting.BACKUP).iterdir()),
            {'intent.json','snapshot.json','inventory.json','evidence.tar.gz','backup.json'})

    async def test_receiver_checks_actual_pipe_frames_commit_and_creates_only_one_archive(self):
        import threading
        await self.produce(); data,_=self.collect(); inventory,inventory_state=archive.inventory(data)
        wire=io.BytesIO(); archive.framing._write(wire,archive.MAGIC)
        archive.framing._metadata(wire,dict(snapshot=data,inventory=inventory))
        receipt=archive.pack(wire,inventory,inventory_state)
        archive.framing._write(wire,struct.pack('!Q',0)); archive.framing._metadata(wire,receipt)
        archive.framing._write(wire,archive.END)
        path=self.root/'receiver'; path.mkdir(mode=0o700)
        read,write=os.pipe()
        def producer():
            with os.fdopen(write,'wb',buffering=0) as stream: archive.framing._write(stream,wire.getvalue())
        thread=threading.Thread(target=producer); thread.start()
        try:
            with os.fdopen(read,'rb',buffering=0) as stream,patch.object(reporting,'_manifest',return_value=self.f.manifest):
                received=reporting._receive(NS(stdout=stream,wait=lambda **kw:0),'backup',
                    {'current_sources':self.sources},path=path)
                self.assertEqual(received[:3],(data,inventory,receipt))
        finally: thread.join(10)
        self.assertFalse(thread.is_alive())
        archive.verify(path/'evidence.tar.gz',data,inventory,receipt,self.f.manifest,self.sources)

    async def test_schema_cannot_turn_nulls_into_zero_or_change_official_limits(self):
        await self.produce(); data,_=self.collect()
        for key,value in [('agent_seconds',0),('reward',0),('setup_timeout_seconds',899)]:
            changed=deepcopy(data); changed['rows'][2][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): report.validate(changed,self.f.manifest,self.sources)

    async def test_native_backup_commit_follows_normal_session_exit_and_no_second_archive(self):
        await self.produce(); output=io.BytesIO(); read,write=os.pipe(); os.close(write)
        @contextmanager
        def open_session(stream): yield object()
        with os.fdopen(read,'rb',buffering=0) as incoming, \
                patch.object(reporting,'__file__',str(self.root/'stage2/no_cutoff_recovery_reporting.py')), \
                patch.object(boot,'check',side_effect=lambda bound,*args:files.capture(self.root,bound)[1]), \
                patch.object(service,'loaded'), patch.object(session,'open_session',side_effect=open_session), \
                patch.object(reporting.handoff,'_live',return_value={'header':{'operator':{'operator_commit':'a'*40}}}), \
                patch.object(sys,'stdin',NS(buffer=incoming)), patch.object(sys,'__stdout__',NS(buffer=output)):
            await reporting.native(self.bound,'a'*40,'backup')
            with self.assertRaises(ValueError): await reporting.native(self.bound,'a'*40,'backup')
        self.assertTrue(output.getvalue().endswith(archive.END))
        self.assertEqual({p.name for p in (self.root/reporting.NATIVE_BACKUP).iterdir()},{'intent.json','result.json'})

    async def test_native_exit_failure_withholds_commit_and_retains_failure(self):
        await self.produce(); output=io.BytesIO(); read,write=os.pipe(); os.close(write)
        @contextmanager
        def open_session(stream):
            yield object()
            raise ValueError('local synthetic final recheck failure')
        with os.fdopen(read,'rb',buffering=0) as incoming, \
                patch.object(reporting,'__file__',str(self.root/'stage2/no_cutoff_recovery_reporting.py')), \
                patch.object(boot,'check',side_effect=lambda bound,*args:files.capture(self.root,bound)[1]), \
                patch.object(service,'loaded'), patch.object(session,'open_session',side_effect=open_session), \
                patch.object(reporting.handoff,'_live',return_value={'header':{'operator':{'operator_commit':'a'*40}}}), \
                patch.object(sys,'stdin',NS(buffer=incoming)), patch.object(sys,'__stdout__',NS(buffer=output)):
            with self.assertRaises(ValueError): await reporting.native(self.bound,'a'*40,'backup')
        self.assertFalse(output.getvalue().endswith(archive.END))
        self.assertTrue((self.root/reporting.NATIVE_BACKUP/'failure.json').is_file())

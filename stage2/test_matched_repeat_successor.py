"""Real synthetic89 files/archives and local pipes; native observations mocked."""
import ast
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_terminus_predecessor as operator
import matched_repeat_terminus_handoff as handoff
import matched_repeat_composite_stream as composite
import matched_repeat_execution_bootstrap as boot
import matched_repeat_policy as policy
import test_matched_repeat_reporting as fixtures
import test_matched_repeat_amended_handoff as original_fixtures
import matched_repeat_openhands_handoff as successor
from test_no_cutoff_recovery_runtime import save


class TerminusReaderTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.f = fixtures.ReportingTests('runTest'); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.reporting = operator.reporting
        self.enterContext(patch.object(operator, 'REPO', self.root))
        self.enterContext(patch.object(handoff, 'ROOT', self.root))
        self.enterContext(patch.object(self.reporting.handoff.original.launch, 'REPO', self.root))
        self.enterContext(patch.object(self.reporting, '_manifest', return_value=self.f.f.manifest))
        self.enterContext(patch.object(self.reporting.handoff.original.launch, '_git',
            side_effect=lambda command, ref: (self.root/ref.split(':',1)[1]).read_bytes()))
        self.value = dict(sources=self.f.sources, bindings={'commit':'a'*40})

    def retained(self):
        data, _, source, inventory, _, receipt = self.f.sample()
        verified = self.reporting.mac_archive.verify(source,data,inventory,receipt,self.f.f.manifest,self.f.sources)
        backup = dict(kind='verified_off_server_baseline_backup',receipt=receipt,verified=verified,
            snapshot_sha256=policy.fingerprint(data),inventory_sha256=policy.fingerprint(inventory),
            automatic_resume=False,paid_launch_ready=False)
        files = {'intent.json':dict(kind='one_shot_off_server_baseline_backup',commit='a'*40,
                started_utc=data['collected_utc'],automatic_resume=False,paid_launch_ready=False),
            'snapshot.json':data,'inventory.json':inventory,'backup.json':backup}
        for name,value in files.items(): save(self.root,self.reporting.BACKUP+'/'+name,self.reporting._json(value))
        save(self.root,self.reporting.BACKUP+'/evidence.tar.gz',source.read_bytes())
        projection = self.reporting.public_projection.projection(data,self.f.f.manifest,self.f.sources,verified)
        public = {}
        for name,raw in projection.items():
            relative=self.reporting.PUBLIC+'/'+name;save(self.root,relative,raw);public[relative]=hashlib.sha256(raw).hexdigest()
        for name,value in (('intent.json',dict(kind='one_shot_separate_baseline_export',commit='a'*40,
                started_utc=data['collected_utc'],automatic_resume=False)),
                ('result.json',dict(kind='separate_baseline_allowlisted_export_complete',files=public,
                snapshot_sha256=policy.fingerprint(data),archive_sha256=receipt['sha256'],
                automatic_resume=False,paid_launch_ready=False))):
            save(self.root,self.reporting.EXPORT+'/'+name,self.reporting._json(value))
        return operator._retained(self.value)

    async def test_real_same_archive_publication_and_separate_89_lineage(self):
        retained=self.retained();document=retained['document']
        self.assertEqual(operator._retained(self.value),retained)
        block=operator.block(document,self.f.f.manifest,self.f.sources)
        self.assertEqual(len(block['results_sha256']),89);self.assertEqual(block['harness'],'terminus-2')
        self.assertIsNone(document['fresh_audit']['aggregate']['total_cost_usd'])
        self.assertEqual(document['fresh_audit']['aggregate']['no_verifier_result'],1)
        self.assertFalse(document['paid_launch_ready'])

    async def test_actual_archive_corruption_partial_export_and_uncommitted_publication_refuse(self):
        self.retained();path=self.root/self.reporting.BACKUP/'evidence.tar.gz';raw=path.read_bytes()
        path.write_bytes(raw[:-1])
        with self.assertRaises((ValueError,OSError,EOFError)):operator._retained(self.value)
        path.write_bytes(raw)
        with patch.object(self.reporting.handoff.original.launch,'_git',return_value=b'not committed'):
            with self.assertRaises(ValueError):operator._retained(self.value)
        save(self.root,self.reporting.EXPORT+'/failure.json',b'{}')
        with self.assertRaises(ValueError):operator._retained(self.value)

    async def test_same_byte_replacement_of_archive_or_publication_changes_current_identity(self):
        before=self.retained()
        for name in (self.reporting.BACKUP+'/evidence.tar.gz',self.reporting.PUBLIC+'/trials.json'):
            path=self.root/name;raw=path.read_bytes();old=path.with_name(path.name+'.old')
            path.rename(old);save(self.root,name,raw);old.unlink()
            self.assertNotEqual(operator._retained(self.value),before)

    async def test_schema_numeric_types_freshness_and_all89_are_strict(self):
        document=self.retained()['document']
        for mode in ('wrong-harness','stale','float-count','changed-row','unknown-field','changed-source'):
            altered=deepcopy(document)
            if mode=='wrong-harness':altered['fresh_audit']['harness']='openhands'
            elif mode=='stale':altered['fresh_audit']['collected_utc']='2000-01-01T00:00:00Z'
            elif mode=='float-count':altered['fresh_audit']['intended']=89.0
            elif mode=='changed-row':altered['fresh_audit']['rows'].pop()
            elif mode=='unknown-field':altered['raw_message']='forbidden'
            else:altered['sources_sha256']='a'*64
            with self.subTest(mode=mode),self.assertRaises((ValueError,KeyError)):
                operator.metadata(altered,self.f.f.manifest,self.f.sources)

    async def test_capture_always_calls_real_reporter_entry_and_late_drift_withholds_document(self):
        retained=self.retained();prepared=dict(value=self.value,files={},retained=retained)
        with patch.object(operator,'prepare',return_value=prepared),patch.object(operator,'current') as current,\
                patch.object(self.reporting,'_capture',return_value=(retained['data'],self.value,{})) as capture,\
                patch.object(self.reporting,'_current') as recheck:
            for _ in range(2):operator.capture('a'*40)
            self.assertEqual(capture.call_count,2);capture.assert_called_with('a'*40,'audit')
            self.assertEqual(recheck.call_count,2);self.assertEqual(current.call_count,2)
            current.side_effect=ValueError('late source drift')
            with self.assertRaises(ValueError):operator.capture('a'*40)

    def native(self):
        retained=self.retained();doc=retained['document'];data,inventory,backup=operator.metadata(
            doc,self.f.f.manifest,self.f.sources)
        bound={'stage2/'+n:h for n,h in self.f.sources.items()}
        for name in (policy.BASELINE_FILE,policy.FINAL_FILE):
            relative=self.reporting.report.RT+name
            bound[relative]=hashlib.sha256((self.root/relative).read_bytes()).hexdigest()
        for name,value in (('intent.json',dict(kind='one_shot_separate_baseline_backup',commit='a'*40,
                sources_sha256=policy.fingerprint(bound),automatic_resume=False,
                started_utc=data['collected_utc'],paid_launch_ready=False)),
                ('result.json',dict(backup['receipt'],automatic_resume=False,paid_launch_ready=False))):
            save(self.root,self.reporting.NATIVE_BACKUP+'/'+name,self.reporting._json(value))
        self.enterContext(patch.object(handoff,'_context',return_value=self.root))
        self.enterContext(patch.object(handoff.recovery,'_inputs',return_value=(bound,{})))
        self.enterContext(patch.object(boot,'check',return_value={}))
        self.finished=self.enterContext(patch.object(boot,'terminus_finished',return_value={'synthetic_native_status':True}))
        self.enterContext(patch.object(handoff.recovery,'recheck',return_value={'operator_commit':'a'*40}))
        self.f.resources.reset_mock()
        return doc,data,inventory,backup,bound

    @contextmanager
    def pipe(self,raw):
        r,w=os.pipe();errors=[]
        def send():
            try:
                with os.fdopen(w,'wb',buffering=0) as output:handoff.recovery.wire._write(output,raw)
            except BrokenPipeError:pass
            except BaseException as error:errors.append(error)
        worker=threading.Thread(target=send);worker.start()
        try:
            with os.fdopen(r,'rb',buffering=0) as stream:yield stream
        finally:worker.join(10);self.assertFalse(worker.is_alive());self.assertEqual(errors,[])

    def authenticate(self,doc,backup):
        initial_observations = self.finished.call_count
        raw=(self.root/self.reporting.BACKUP/'evidence.tar.gz').read_bytes();out=io.BytesIO()
        digest=handoff.recovery.wire.write_header(out,dict(kind=handoff.TRANSFER,schema_version=1,
            harness='openhands',operator=doc))
        out.write(raw);handoff.recovery.wire.commit(out,digest,backup['receipt']['sha256']);out.write(b'next')
        def inner(root,harness,stream,**kw):
            self.assertEqual(handoff.recovery.wire._exact(stream,4),b'next')
            self.assertEqual(kw,{'terminus_sha256':policy.fingerprint(doc)})
            self.assertEqual(self.finished.call_count, initial_observations)
            witness=handoff.recovery._Witness()
            handoff.recovery._WITNESSES[witness]=dict(pid=os.getpid(),thread=threading.get_ident(),task=asyncio.current_task())
            self.addCleanup(handoff.recovery.invalidate,witness)
            return witness,stream
        with self.pipe(out.getvalue()) as stream,patch.object(handoff.recovery,'_authenticate',side_effect=inner):
            witness,_,_=handoff.authenticate(self.root,'openhands',stream)
            self.addCleanup(handoff.invalidate,witness)
        return witness

    async def test_actual_native_inventory_producer_and_all89_rereads_follow_inner_header(self):
        doc,data,inventory,backup,bound=self.native();witness=self.authenticate(doc,backup)
        self.finished.assert_called_once_with(bound);self.assertEqual(self.f.resources.call_count,89)
        record=handoff.recheck(witness);self.assertFalse(record['paid_launch_ready'])
        self.assertEqual(len(record['block']['results_sha256']),89)
        self.finished.reset_mock();handoff.recheck(witness);self.finished.assert_not_called()

    async def test_native_drift_restoration_same_byte_replacement_and_lifetime_refuse(self):
        doc,data,_,backup,_=self.native();witness=self.authenticate(doc,backup)
        name=next(n for n in data['supporting_files'] if n.endswith('/result.json'))
        path=self.root/name;raw=path.read_bytes();path.write_bytes(raw+b' ')
        with self.assertRaises(ValueError):handoff.recheck(witness)
        path.write_bytes(raw)
        with self.assertRaises(ValueError):handoff.recheck(witness)
        witness=self.authenticate(doc,backup)
        with self.assertRaises(TypeError):copy.copy(witness)
        async def other():
            with self.assertRaises(ValueError):handoff.recheck(witness)
        await asyncio.create_task(other())
        with self.assertRaises(ValueError):handoff.recheck(witness)

    async def test_missing_native_backup_or_unsuccessful_service_cannot_authenticate(self):
        doc,_,_,backup,_=self.native()
        self.finished.side_effect=ValueError('Not actually completed')
        with self.assertRaises(ValueError):self.authenticate(doc,backup)
        self.finished.side_effect=None
        save(self.root,self.reporting.NATIVE_BACKUP+'/failure.json',b'{}')
        with self.assertRaises(ValueError):self.authenticate(doc,backup)


class SuccessorFrameTests(unittest.TestCase):
    def frame(self,footer):
        wire=composite.wire;out=io.BytesIO();payload=b'synthetic original-only bytes';sha=hashlib.sha256(payload).hexdigest()
        document={'actual_original_fixture':True};header=dict(operator=document,
            backup=json.dumps({'receipt':{'compressed_bytes':len(payload),'sha256':sha}}))
        digest=wire.write_header(out,header);out.write(payload);wire.commit(out,digest,sha)
        expected=out.getvalue();out.write(footer+bytes.fromhex('a'*64)+bytes.fromhex('b'*64)+
            bytes.fromhex(policy.fingerprint(document))+bytes.fromhex(sha))
        r,w=os.pipe();os.write(w,out.getvalue());os.close(w)
        return os.fdopen(r,'rb',buffering=0),expected

    def test_original_bytes_are_exact_and_three_document_commit_is_mandatory(self):
        for footer,works in ((composite.SUCCESSOR_END,True),(composite.END,False)):
            stream,expected=self.frame(footer)
            with stream:
                frame=composite.original_frame(stream,'b'*64,terminus_sha256='a'*64)
                self.assertEqual(composite.wire._exact(frame,len(expected)),expected)
                if works:self.assertEqual(frame.read(1),b'')
                else:
                    with self.assertRaises((ValueError,EOFError)):frame.read(1)

    def test_sender_footer_binds_all_documents_and_preserves_original_sender_schema(self):
        r,w=os.pipe()
        original=dict(kind='amended_off_server_predecessor_bytes_sent_not_admission',
            operator_document_sha256='c'*64,archive_sha256='d'*64,paid_launch_ready=False)
        with os.fdopen(w,'wb',buffering=0) as out:composite.finish(out,'b'*64,original,terminus_sha256='a'*64)
        with os.fdopen(r,'rb') as inp:
            self.assertEqual(inp.read(),composite.SUCCESSOR_END+b''.join(bytes.fromhex(c*64) for c in 'abcd'))


class OpenHandsOriginalConsumerTests(unittest.IsolatedAsyncioTestCase):
    """Actual original89 archive/anchors; native audit and Terminus witness mocked."""
    def setUp(self):
        self.f=f=original_fixtures.HandoffFixture('runTest');f.setUp();self.addCleanup(f.doCleanups)
        self.enterContext(patch.object(handoff,'_context',return_value=f.repo))
        self.header=f.header();self.packet=f.packet(self.header)
        manifest=boot.loads((f.repo/'stage2/input_manifest.json').read_bytes())
        self.earlier=handoff._Witness()
        self.record=dict(kind=handoff.KIND,harness='openhands',
            operator_commit=self.header['operator']['operator_commit'],
            block=dict(self.header['operator']['predecessors']['blocks'][0],
                experiment=policy.EXPERIMENT,harness='terminus-2'),paid_launch_ready=False)
        handoff._WITNESSES[self.earlier]=dict(pid=os.getpid(),thread=threading.get_ident(),
            task=None,manifest=manifest,data={'predecessors':deepcopy(self.header['operator']['predecessors'])})
        self.addCleanup(handoff.invalidate,self.earlier)
        # setUp has no running async task; assign the owning task at actual receive.
        self.read=self.enterContext(patch.object(handoff,'recheck',side_effect=self.term_read))

    def term_read(self,witness):handoff._live(witness);return deepcopy(self.record)

    def receive(self,*,bad_footer=False,packet=None):
        handoff._WITNESSES[self.earlier]['task']=asyncio.current_task()
        raw=self.packet if packet is None else packet
        original_hash=policy.fingerprint(self.header['operator'])
        end=(composite.END if bad_footer else composite.SUCCESSOR_END)+bytes.fromhex('a'*64)+bytes.fromhex('b'*64)
        end+=bytes.fromhex(original_hash)+bytes.fromhex(self.f.f.backup['receipt']['sha256'])
        with TerminusReaderTests.pipe(self,raw+end) as incoming:
            frame=composite.original_frame(incoming,'b'*64,terminus_sha256='a'*64)
            witness=successor.authenticate(self.f.repo,self.f.f.original,self.f.f.proof,'openhands',frame,self.earlier)
            self.addCleanup(successor.invalidate,witness)
            return witness

    def recheck(self,witness):
        return successor.recheck(self.f.repo,self.f.f.original,self.f.f.proof,'openhands',witness)

    async def test_actual_original_archive_real_collector_entry_and_two_distinct_lineage_blocks(self):
        witness=self.receive();self.f.audit.assert_called_once()
        record=self.recheck(witness)
        self.assertEqual(record['harness'],'openhands');self.assertEqual(record['kind'],successor.KIND)
        self.assertEqual([b['harness'] for b in record['predecessors']['blocks']],['C0-NC','terminus-2'])
        self.assertEqual(sum(map(len,record['preserved_result_files'].values())),182)
        self.f.audit.reset_mock();self.recheck(witness);self.f.audit.assert_not_called()

    async def test_two_document_footer_or_truncated_original_cannot_reach_native_audit(self):
        with self.assertRaises(ValueError):self.receive(bad_footer=True)
        with self.assertRaises((ValueError,EOFError,OSError)):self.receive(packet=self.packet[:-50])
        self.f.audit.assert_not_called()

    async def test_distinct_term_revision_changed_original_and_task_switch_latch(self):
        self.record['operator_commit']='f'*40
        with self.assertRaises(ValueError):self.receive()
        self.record['operator_commit']=self.header['operator']['operator_commit']
        witness=self.receive()
        name=self.f.f.data['absent_paths'][0];self.f.save(name,b'{}')
        with self.assertRaises(ValueError):self.recheck(witness)
        (self.f.repo/name).unlink()
        with self.assertRaises(ValueError):self.recheck(witness)
        witness=self.receive()
        async def other():
            with self.assertRaises(ValueError):self.recheck(witness)
        await asyncio.create_task(other())
        with self.assertRaises(ValueError):self.recheck(witness)

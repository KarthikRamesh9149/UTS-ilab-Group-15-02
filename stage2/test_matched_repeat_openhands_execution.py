"""Local successor routing/isolation and fixed program checks, not native proof."""
import ast
import asyncio
import copy
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import io
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_execution_connection as connection
import matched_repeat_terminus_predecessor as predecessor
import matched_repeat_terminus_handoff as terminus
import matched_repeat_openhands_install as installer
import matched_repeat_openhands_reporting as reporting
import matched_repeat_install as first_install
import matched_repeat_reporting as first_report
import matched_repeat_execution_bootstrap as boot
import matched_repeat_locks as locks
import no_cutoff_recovery_install as recovery_install
import matched_repeat_openhands_handoff as successor
import matched_repeat_session as session
import matched_repeat_policy as policy
import test_matched_repeat_session as session_fixture
import test_matched_repeat_completion as completion_fixture
import test_matched_repeat_reporting as reporting_fixture
import test_matched_repeat_execution_service as service_fixture
import test_matched_repeat_install as install_fixture
from test_no_cutoff_recovery_runtime import save


class OpenHandsRouteTests(unittest.TestCase):
    def test_fixed_successor_roots_states_and_full_existing_lock_order(self):
        self.assertEqual(installer.ROOT,boot.root_for('openhands'))
        self.assertNotEqual(installer.STATE,first_install.STATE)
        self.assertNotEqual(reporting.BACKUP,first_report.BACKUP)
        self.assertNotEqual(reporting.EXPORT,first_report.EXPORT)
        self.assertEqual(installer._lock_paths(recovery_install,boot),locks.paths(installer.ROOT,'openhands')[:-1])
        self.assertEqual(len(installer._lock_paths(recovery_install,boot)),54)
        self.assertEqual(installer._lock_paths(recovery_install,boot)[:-3],first_install._lock_paths(recovery_install,boot))

    def test_only_openhands_full_prepare_requires_actual_completed_terminus_reader(self):
        value=dict(bindings={'commit':'a'*40},sources={},harness='openhands')
        with patch.object(connection,'_source_inputs',return_value=(value,{})),\
                patch.object(connection.handoff.operator,'_sources',return_value={}),\
                patch.object(connection.handoff.operator,'_retained',return_value={}),\
                patch.object(connection,'_current'),patch.object(predecessor,'prepare',return_value={'actual':'reader'}) as call:
            observed,_=connection.prepare('a'*40,'openhands')
            self.assertEqual(observed['terminus'],{'actual':'reader'});call.assert_called_once_with('a'*40)
            call.side_effect=ValueError('Terminus not complete')
            with self.assertRaises(ValueError):connection.prepare('a'*40,'openhands')

    def test_fixed_sender_selects_real_three_archive_route_without_saved_input(self):
        destination=object()
        with patch.object(terminus,'send',return_value={'actual':'three'}) as send,\
                patch.object(connection.handoff,'send',return_value={'actual':'two'}) as first:
            self.assertEqual(connection.send('openhands',destination),{'actual':'three'});send.assert_called_once_with(destination)
            self.assertEqual(connection.send('terminus-2',destination),{'actual':'two'});first.assert_called_once_with(destination)
            with self.assertRaises(ValueError):connection.send('unknown',destination)

    def test_openhands_reporter_calls_real_three_predecessor_dispatch_and_own_bootstrap(self):
        import inspect
        source=inspect.getsource(reporting)
        self.assertIn('connection.send(HARNESS, process.stdin)',source)
        self.assertIn('session.operator_commit(active)',source)
        self.assertEqual(reporting.HARNESS,'openhands')
        self.assertEqual(reporting.ROOT,boot.root_for('openhands'))
        raw=inspect.getsource(boot).encode()
        with patch.object(reporting.handoff.original.launch,'_raw',return_value=raw):
            program=reporting._program({'stage2/matched_repeat_execution_bootstrap.py':'a'*64},'b'*40,'audit')
        ast.parse(program);self.assertIn("b.reporting('openhands'",program)
        self.assertIn(str(boot.root_for('openhands')),program)

    def test_installer_preserves_common_exclusive_copy_and_lock_algorithms(self):
        import inspect
        # Only explicit destination/consumer labels differ in these algorithms.
        names=('_payload','_runtime','_mkdir','_write','_copy','_installed','_install','_entry','prepare','deploy','_locked')
        for name in names:
            old=inspect.getsource(getattr(first_install,name))
            new=inspect.getsource(getattr(installer,name)).replace('openhands','terminus-2').replace(
                'matched_repeat_terminus-2_install.py','matched_repeat_install.py')
            self.assertEqual(ast.dump(ast.parse(old),include_attributes=False),
                ast.dump(ast.parse(new),include_attributes=False),name)

    def test_reporter_preserves_strict_backup_export_algorithm_with_explicit_three_way_sender(self):
        import inspect
        old=inspect.getsource(first_report)
        new=inspect.getsource(reporting).replace('Fixed OpenHands completed audit','Fixed Terminus completed audit').replace(
            'openhands','terminus-2').replace('matched_repeat_terminus-2_reporting.py','matched_repeat_reporting.py').replace(
            'Exact OpenHands baseline','Exact first baseline').replace('session.operator_commit(active)',
            "session.handoff._live(live['witness'])['header']['operator']['operator_commit']").replace(
            'connection.send(HARNESS, process.stdin)','handoff.send(process.stdin)')
        # Docstrings are intentionally distinct; executable AST must match.
        a,b=ast.parse(old),ast.parse(new);a.body=a.body[1:];b.body=b.body[1:]
        self.assertEqual(ast.dump(a,include_attributes=False),ast.dump(b,include_attributes=False))


class TerminusNativeReaderTests(unittest.TestCase):
    def setUp(self):
        self.bound={'stage2/matched_repeat_execution_bootstrap.py':hashlib.sha256(b'# fixture').hexdigest()}
        self.read=self.enterContext(patch.object(boot,'raw',side_effect=lambda root,name,*args:
            (b'a'*40+b'\n',(1,)) if name=='source-commit.txt' else (b'# fixture',(2,))))
        self.run=self.enterContext(patch.object(boot.subprocess,'run',side_effect=self.observe))

    def status(self,operation):
        return dict(kind='read_only_baseline_operation_status_not_admission',operation=operation,
            status='service_exited_successfully_not_completed_study_audit',paid_launch_ready=False,
            automatic_resume=False,counts=dict(study=policy.EXPERIMENT,harness='terminus-2',
                intended=89,started=89,completed=89,passed=0,failed=0,missing_verifier=89,active_tasks=[]))

    def observe(self,argv,**kw):
        self.assertEqual(argv[:3],[str(boot.root_for('terminus-2')/'.venv/bin/python'),'-I','-B'])
        self.assertEqual(kw['cwd'],boot.root_for('terminus-2'))
        self.assertEqual(kw['env'],boot.environment('terminus-2'));ast.parse(argv[-1])
        operation='qualify-repeat' if "'qualify-repeat'" in argv[-1] else 'run-repeat'
        return NS(returncode=0,stdout=json.dumps(self.status(operation)).encode())

    def test_both_actual_own_interpreter_readers_and_final_identity_reads_without_score_floor(self):
        result=boot.terminus_finished(self.bound)
        self.assertEqual(set(result),{'qualify-repeat','run-repeat'});self.assertEqual(self.run.call_count,2)
        self.assertEqual(self.read.call_count,4)

    def test_partial_failed_wrong_harness_types_or_stop_flags_never_count_as_completion(self):
        for key,value in (('status','running'),('automatic_resume',True),('harness','openhands'),
                ('study','wrong'),('completed',88),('passed',False),('missing_verifier',88),('active_tasks',[89])):
            record=self.status('qualify-repeat');target=record['counts'] if key in record['counts'] else record
            target[key]=value;self.run.side_effect=None
            self.run.return_value=NS(returncode=0,stdout=json.dumps(record).encode())
            with self.subTest(key=key),self.assertRaises(ValueError):boot.terminus_finished(self.bound)
        self.run.return_value=NS(returncode=1,stdout=b'')
        with self.assertRaises(ValueError):boot.terminus_finished(self.bound)

    def test_same_bytes_replaced_source_or_installed_revision_refuses(self):
        original=self.read.side_effect
        for selected in ('source-commit.txt','stage2/matched_repeat_execution_bootstrap.py'):
            counts={}
            def changed(root,name,*args):
                raw,item=original(root,name,*args);counts[name]=counts.get(name,0)+1
                return raw,(9,) if name==selected and counts[name]>1 else item
            self.read.side_effect=changed
            with self.subTest(selected=selected),self.assertRaises(ValueError):boot.terminus_finished(self.bound)


class OpenHandsSessionTests(unittest.TestCase):
    """Real owning session/local locks, synthetic live witnesses/native readers."""
    def setUp(self):
        self.q=q=session_fixture.SessionTests('runTest');q.setUp();self.addCleanup(q.doCleanups)
        self.root=q.root;self.events=[];self.earlier=self.recovered=self.original=None
        self.enterContext(patch.dict(session.runtime.DEPLOYMENTS,{'openhands':self.root}))
        self.enterContext(patch.object(terminus.recovery,'_task',side_effect=q.task))
        for record in (q.pred,q.old,q.library,q.host):record['harness']='openhands'
        q.pred['kind']=successor.KIND
        self.term_record=dict(kind=terminus.KIND,harness='openhands',operator_commit='a'*40,
            terminus_document_sha256='b'*64,archive_sha256='c'*64,paid_launch_ready=False)
        self.recovery_record=dict(kind=terminus.recovery.KIND,harness='openhands',operator_commit='a'*40,
            recovery_document_sha256='d'*64,archive_sha256='e'*64,paid_launch_ready=False)
        self.auth=self.enterContext(patch.object(terminus,'authenticate',side_effect=self.authenticate))
        self.term_read=self.enterContext(patch.object(terminus,'recheck',side_effect=self.term_recheck))
        self.recovery_read=self.enterContext(patch.object(terminus.recovery,'recheck',side_effect=self.recovery_recheck))
        self.original_auth=self.enterContext(patch.object(successor,'authenticate',side_effect=self.original_authenticate))
        self.original_read=self.enterContext(patch.object(successor,'recheck',side_effect=lambda *args:
            q.under_lock('original-openhands-recheck',q.pred)))
        def acquire(stack,root,harness):
            self.assertEqual(harness,'openhands');return q.locks(stack,root,'terminus-2')
        q.lock.side_effect=acquire
        before=q.before_release
        def release():
            for value,module in ((self.earlier,terminus),(self.recovered,terminus.recovery),(self.original,successor)):
                self.assertNotIn(value,module._WITNESSES)
            self.events.append('all-three-invalid-before-unlock');before()
        q.before_release=release

    def witness(self,module,**state):
        value=module._Witness();module._WITNESSES[value]=dict(pid=os.getpid(),thread=threading.get_ident(),
            task=self.q.task(),**state);self.addCleanup(module.invalidate,value);return value

    def authenticate(self,root,harness,stream):
        self.assertEqual((root,harness,stream),(self.root,'openhands',self.q.stream))
        self.assertFalse(self.q.locked);self.events.append('real-three-way-entry')
        self.earlier=self.witness(terminus);self.recovered=self.witness(terminus.recovery)
        return self.earlier,self.recovered,stream

    def original_authenticate(self,root,old,final,harness,stream,earlier):
        self.assertFalse(self.q.locked);self.assertIs(earlier,self.earlier)
        self.events.append('original-openhands-authentication')
        self.original=self.witness(successor,terminus=earlier,header={'operator':{'operator_commit':'a'*40}})
        return self.original

    def term_recheck(self,witness):terminus._live(witness);return deepcopy(self.term_record)
    def recovery_recheck(self,witness):terminus.recovery._live(witness);return deepcopy(self.recovery_record)
    def open(self):return session.open_execution_session(self.root,'openhands',self.q.stream)

    def test_real_same_task_three_handle_session_authenticates_before_locks_and_invalidates_before_unlock(self):
        with self.open() as active:
            self.assertEqual(self.events[:2],['real-three-way-entry','original-openhands-authentication'])
            self.assertTrue(self.q.locked);self.assertEqual(session.operator_commit(active),'a'*40)
            self.assertEqual(session.require_execution(active),self.recovery_record)
            self.assertEqual(session.describe(active)['completed_terminus'],self.term_record)
            with self.assertRaises(TypeError):copy.copy(active)
        self.assertIn('all-three-invalid-before-unlock',self.events)
        with self.assertRaises(ValueError):session.require_execution(active)
        self.q.auth.assert_not_called()

    def test_no_legacy_openhands_or_saved_witness_route(self):
        with self.assertRaises(ValueError):
            with session.open_session(self.root,'openhands',self.q.stream):self.fail('Legacy route')
        self.auth.side_effect=None;self.auth.return_value=(deepcopy(self.term_record),deepcopy(self.recovery_record),self.q.stream)
        with self.assertRaises(ValueError):
            with self.open():self.fail('Saved flags')
        self.assertFalse(session._GATE.locked())

    def test_failure_cancellation_partial_lock_and_closed_handle_revoke_all_authority(self):
        with self.assertRaises(asyncio.CancelledError):
            with self.open():raise asyncio.CancelledError()
        self.assertIn('all-three-invalid-before-unlock',self.events)
        self.q.lock.side_effect=ValueError('Actual contention')
        with self.assertRaises(ValueError):
            with self.open():self.fail('Partial lock')
        for value,module in ((self.earlier,terminus),(self.recovered,terminus.recovery),(self.original,successor)):
            self.assertNotIn(value,module._WITNESSES)
        self.assertFalse(session._GATE.locked())

    def test_actual_final_reads_and_latched_term_drift_even_after_restoration(self):
        initial=deepcopy(self.term_record)
        with self.assertRaises(ValueError):
            with self.open() as active:
                self.term_record['archive_sha256']='f'*64
                with self.assertRaises(ValueError):session.recheck(active)
                self.term_record=initial
                with self.assertRaises(ValueError):session.require_execution(active)
        with self.assertRaises(ValueError):
            with self.open():self.term_read.side_effect=ValueError('Final actual read failed')

    def test_real_task_switch_invalidates_every_handle_and_different_commit_refuses(self):
        async def run():
            with self.assertRaises(ValueError):
                with self.open() as active:
                    async def other():
                        with self.assertRaises(ValueError):session.require_execution(active)
                    await asyncio.create_task(other())
                    with self.assertRaises(ValueError):session.require_execution(active)
        asyncio.run(run())
        self.recovery_record['operator_commit']='f'*40
        with self.assertRaises(ValueError):
            with self.open():self.fail('Mismatched actual commit')
        self.assertFalse(session._GATE.locked())


class OpenHandsCompletionTests(unittest.TestCase):
    def setUp(self):
        self.f=f=completion_fixture.CompletionTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        c=completion_fixture.completion;self.c=c
        self.enterContext(patch.dict(c.runtime.DEPLOYMENTS,{'openhands':f.root}))
        self.enterContext(patch.object(session,'_live',return_value=dict(root=f.root,harness='openhands',files=f.bound)))
        self.expected=c.base('openhands','1'*32,f.bound,'2'*40,f.operation)
        for name in ('intent.json','service-started.json','accepted.json','result.json'):
            value=json.loads((f.path/name).read_bytes());value.update(self.expected);f.write(name,value)
        prior=json.loads((f.path/'prerequisites.json').read_bytes());prior['harness']='openhands'
        prior['completed_recovery']['harness']='openhands'
        self.term=dict(kind=terminus.KIND,harness='openhands',operator_commit='2'*40,
            terminus_document_sha256='8'*64,archive_sha256='9'*64,
            sources_sha256=policy.fingerprint({n[7:]:h for n,h in f.bound.items() if n.startswith('stage2/')}),
            block={'synthetic_actual_prior_block':'a'*64},paid_launch_ready=False,full_runtime_restore_exercised=False)
        prior['completed_terminus']=deepcopy(self.term)
        prior['predecessor']['predecessors']={'blocks':[{},deepcopy(self.term['block'])]}
        self.prerequisites=prior;self.retain(prior)

    def retain(self,prior):
        raw=self.f.write('prerequisites.json',prior)
        accepted=json.loads((self.f.path/'accepted.json').read_bytes())
        accepted.update(prerequisites_sha256=hashlib.sha256(raw).hexdigest(),
            terminus_document_sha256='8'*64,terminus_archive_sha256='9'*64)
        self.f.write('accepted.json',accepted)

    def test_actual_completed_openhands_requires_all_three_bound_predecessors(self):
        self.assertFalse(self.f.read()['paid_launch_ready']);self.assertEqual(self.f.manager.call_count,2)
        self.f.ended.assert_called_once()

    def test_missing_saved_changed_or_other_revision_terminus_record_refuses(self):
        for mode in ('missing','kind','revision','hash','block','source','flag'):
            value=deepcopy(self.prerequisites)
            if mode=='missing':value.pop('completed_terminus')
            else:
                key={'kind':'kind','revision':'operator_commit','hash':'archive_sha256','block':'block',
                    'source':'sources_sha256','flag':'paid_launch_ready'}[mode]
                value['completed_terminus'][key]={'synthetic':'drift'} if mode=='block' else True if mode=='flag' else 'f'*64
            self.retain(value)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.f.read()
        self.f.manager.assert_not_called()


class OpenHandsReportingTests(unittest.TestCase):
    """Actual synthetic OpenHands89 evidence, Darwin IO and one archive/export."""
    def setUp(self):
        self.f=f=reporting_fixture.ReportingTests('runTest');f.harness='openhands'
        f.setUp();self.addCleanup(f.doCleanups)
        self.enterContext(patch.object(reporting,'ROOT',f.root))
        self.enterContext(patch.object(reporting.handoff.original.launch,'REPO',f.root))
        self.enterContext(patch.object(reporting,'_manifest',return_value=f.f.manifest))

    def test_real_openhands89_backup_export_keeps_separate_original_and_prior_scores(self):
        f=self.f;data,_,source,inventory,_,receipt=f.sample();compressed=source.read_bytes();calls=[]
        (f.root/'.runtime/netcup').mkdir(mode=0o700,exist_ok=True)
        public=f.root/reporting.PUBLIC;public.mkdir(parents=True,mode=0o700)
        value={'sources':f.sources,'bindings':{}}
        ids=reporting_fixture.files.capture(f.root,f.bound)[1]
        def capture(commit,mode,*,path=None):
            calls.append(mode)
            if mode=='audit':return dict(data),value,ids
            written={name:reporting._private_bytes(path/name,raw) for name,raw in {
                'snapshot.json':reporting._json(data),'inventory.json':reporting._json(inventory),
                'evidence.tar.gz':compressed}.items()}
            return (data,inventory,receipt,written),value,ids
        with patch.object(connection,'prepare',return_value=(value,f.bound)),\
                patch.object(connection,'_identities',return_value=ids),\
                patch.object(connection,'_current',side_effect=lambda value:reporting_fixture.files.check(f.root,f.bound)),\
                patch.object(reporting,'_capture',side_effect=capture):
            result=reporting.backup('a'*40);self.assertEqual(result['completed'],89)
            path=f.root/reporting.BACKUP/'evidence.tar.gz';before=reporting.mac.identity(path.lstat())
            with self.assertRaises(ValueError):reporting.backup('a'*40)
            projected=reporting.export('a'*40)
            with self.assertRaises(ValueError):reporting.export('a'*40)
            self.assertEqual(reporting.mac.identity(path.lstat()),before);self.assertEqual(path.read_bytes(),compressed)
        summary=json.loads((public/'summary.json').read_bytes())
        self.assertEqual(calls,['backup','audit']);self.assertEqual(summary['harness'],'openhands')
        self.assertEqual(projected['aggregate']['attempted'],89)
        self.assertEqual(summary['original_scores'],{'terminus-2':52,'openhands':44})
        self.assertFalse(summary['repeat_merged_into_original89']);self.assertIsNone(projected['aggregate']['total_cost_usd'])

    def test_own_mac_command_preserves_route_and_actual_three_way_sender_after_readiness(self):
        from types import SimpleNamespace
        f=self.f;stage=Path(boot.__file__).parent
        sources={'stage2/'+name:(stage/name).read_bytes() for name in (
            'matched_repeat_execution_bootstrap.py','matched_repeat_policy.py','progress_dashboard.py')}
        files={'stage2/'+n:h for n,h in f.sources.items()}
        files.update({name:hashlib.sha256(raw).hexdigest() for name,raw in sources.items()})
        files.update({boot.BASELINE_INPUT:boot.BASELINE_SHA,boot.FINAL_INPUT:boot.FINAL_SHA})
        with patch.object(reporting.handoff.original.launch,'_raw',side_effect=lambda name,*args:sources[name]),\
                patch.object(reporting.handoff.original.receiver,'_parents'),patch.object(connection,'REPO',f.root),\
                patch.dict(boot.ROOTS,{'openhands':f.root}):
            command=reporting._command(files,'a'*40,'audit')
        self.assertEqual(command[:-1],connection.ssh_command(f.root)[:-2])
        self.assertIn(str(f.root/'.venv/bin/python'),command[-1])
        value={'bindings':{}};identities={};read,write=os.pipe()
        ready=reporting.service._line(reporting._ready(files,'a'*40,'audit'))
        os.write(write,ready);os.close(write)
        process=SimpleNamespace(stdin=io.BytesIO(),stdout=os.fdopen(read,'rb',buffering=0),poll=lambda:0)
        with process.stdout,patch.object(connection,'prepare',return_value=(value,files)),\
                patch.object(connection,'_identities',return_value=identities),patch.object(reporting,'_current'),\
                patch.object(reporting,'_command',return_value=['fixed-test-command']),\
                patch.object(reporting.subprocess,'Popen',return_value=process),\
                patch.object(connection,'send',return_value={}) as send,\
                patch.object(reporting,'_receive',return_value={'test':'audit'}):
            self.assertEqual(reporting._capture('a'*40,'audit')[0],{'test':'audit'})
            send.assert_called_once_with('openhands',process.stdin)


class OpenHandsServiceTests(unittest.IsolatedAsyncioTestCase):
    """Actual durable successor service flow; manager, live session and work mocked."""
    def setUp(self):
        # Only synchronous fixture ownership is embedded here. Constructing an
        # IsolatedAsyncioTestCase without running its runner prevents cleanups
        # and can leak mocks into later real-session tests.
        fixture=type('LocalServiceFixture',(service_fixture.LocalFiles,unittest.TestCase),{
            n:v for n,v in vars(service_fixture.ServiceExecutionTests).items()
            if callable(v) and not n.startswith('test_')})
        self.f=f=fixture('runTest');f.setUp();self.addCleanup(f.doCleanups)
        self.service=s=service_fixture.service
        self.enterContext(patch.dict(s.boot.ROOTS,{'openhands':f.root}))
        self.enterContext(patch.dict(s.runtime.DEPLOYMENTS,{'openhands':f.root}))
        f.recovered['harness']='openhands';f.record['harness']='openhands'
        f.record['completed_terminus']=dict(terminus_document_sha256='8'*64,archive_sha256='9'*64)
        def check(harness,files,ids):
            self.assertEqual(harness,'openhands');s.evidence.check(f.root,files,ids);return f.root
        self.enterContext(patch.object(s,'check',side_effect=check))
        @contextmanager
        def owning(root,harness,incoming):
            self.assertEqual((root,harness),(f.root,'openhands'))
            f.owner=asyncio.current_task();f.live=True;f.events.append('three-way-session')
            try:
                yield f;f.events.append('normal-exit-recheck')
                if f.exit_error:raise f.exit_error
            finally:f.live=False;f.events.append('all-three-invalid')
        self.enterContext(patch.object(s.session,'open_execution_session',side_effect=owning))
        self.select('qualify-repeat')

    def select(self,operation):
        f=self.f;s=self.service;f.operation=operation
        f.path=f.root/s.completion.operation_state(operation)
        f.expected=s.completion.base('openhands',f.nonce,f.files,f.commit,operation)
        f.intent_raw=f.intent()

    async def execute(self):
        f=self.f
        return await self.service.execute('openhands',f.nonce,f.files,f.commit,f.identities,
            object(),f.connection,f.path,f.intent_raw,f.operation)

    async def test_all_three_acknowledgements_and_lost_ack_finish_only_after_session_exit(self):
        f=self.f;f.ack_error=True
        await self.execute()
        self.assertEqual(f.accepted['terminus_document_sha256'],'8'*64)
        self.assertEqual(f.accepted['terminus_archive_sha256'],'9'*64)
        self.assertTrue((f.path/'result.json').exists());self.assertIn('all-three-invalid',f.events)
        self.assertLess(f.events.index('normal-exit-recheck'),f.events.index('all-three-invalid'))

    async def test_paid_openhands_requires_real_qualifier_exit_and_cancellation_cannot_publish_success(self):
        self.select('run-repeat');f=self.f
        f.completion.side_effect=ValueError('Actual qualifier not successfully exited')
        with self.assertRaises(ValueError):await self.execute()
        f.runner.assert_not_called();self.assertFalse((f.path/'accepted.json').exists())
        f.completion.side_effect=f.completed
        f.runner.side_effect=asyncio.CancelledError()
        with self.assertRaises(asyncio.CancelledError):await self.execute()
        self.assertTrue((f.path/'accepted.json').exists());self.assertFalse((f.path/'result.json').exists())
        self.assertFalse(f.live)

    async def test_final_exit_failure_does_not_turn_durable_producer_into_completion(self):
        self.f.exit_error=ValueError('Actual final reread refused')
        with self.assertRaises(ValueError):await self.execute()
        self.assertTrue((self.f.path/'accepted.json').exists());self.assertFalse((self.f.path/'result.json').exists())


class OpenHandsExclusiveInstallationTests(unittest.TestCase):
    """Actual local protected copies and lock descriptors; native preflight mocked."""
    def setUp(self):
        self.f=f=install_fixture.InstallTests('runTest');f.setUp();self.addCleanup(f.doCleanups)
        for name,value in (('ROOT',f.target),('ORIGINAL',f.old)):
            self.enterContext(patch.object(installer,name,value))
        self.enterContext(patch.object(installer,'_lock_paths',return_value=f.paths))
        self.enterContext(patch.object(installer,'_payload',side_effect=first_install._payload))
        self.enterContext(patch.object(installer,'_old',side_effect=first_install._old))

    def test_exclusive_new_openhands_copy_preserves_original_and_precreates_three_locks(self):
        f=self.f;before={p.relative_to(f.old).as_posix():p.read_bytes() for p in f.old.rglob('*') if p.is_file()}
        result=installer._install(f.value)
        self.assertEqual(result['harness'],'openhands');self.assertEqual(result['precreated_locks'],3)
        self.assertFalse(result['paid_launch_ready'])
        for name,raw in before.items():self.assertEqual((f.old/name).read_bytes(),raw)
        with self.assertRaises(ValueError):installer._install(f.value)

    def test_partial_or_changed_input_is_retained_without_restart(self):
        f=self.f;f.target.mkdir(mode=0o700);save(f.target,'partial.json',b'{}')
        with self.assertRaises(ValueError):installer._install(f.value)
        self.assertEqual({p.name for p in f.target.iterdir()},{'partial.json'})

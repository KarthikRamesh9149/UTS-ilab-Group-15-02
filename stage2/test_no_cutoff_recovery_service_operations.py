"""Actual local handoff/session transport with mocked native operation bodies."""
import ast
import asyncio
import io
import os
import threading
from unittest.mock import Mock, patch

import no_cutoff_recovery_bootstrap as boot
import no_cutoff_recovery_connection as connection
import no_cutoff_recovery_service as service
import no_cutoff_recovery_session as session
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_files as evidence
import no_cutoff_recovery_qualification as qualification
import qualify_no_cutoff_recovery as qualifier
import run_no_cutoff_recovery as runner
import test_no_cutoff_recovery_connection as fixtures

NONCE=fixtures.NONCE
PEER=fixtures.PEER


class OperationTests(fixtures.LocalTree):
    host=fixtures.ServiceSessionTests.host

    def setUp(self):
        super().setUp(); fixtures.ServiceSessionTests.configure_session(self,create=False)

    def invoke(self,operation,*,packet=None,disconnect=False,failure=False,drift=False,relay_failure=False):
        relative=service.operation_state(operation); path=self.root/relative
        path.mkdir(mode=0o700)
        expected=service.base(NONCE,self.files,self.commit,operation)
        intent=service.save(path/'intent.json',dict(expected,relay_process=PEER,created_utc='2026-09-29T22:00:00Z'))
        service.save(path/'service-started.json',dict(expected,native_process=PEER,invocation_id='b2'*16))
        self.f.e.save(relative+'/service.log',b'')
        reader,writer=os.pipe(); errors=[]; sent=[]
        def write():
            try:
                with os.fdopen(writer,'wb',buffering=0) as stream:
                    if packet is None: sent.append(handoff.send(stream))
                    else: stream.write(packet)
            except BrokenPipeError: pass
            except BaseException as error: errors.append(error)
        thread=threading.Thread(target=write); thread.start()
        peer=Mock()
        if disconnect: peer.sendall.side_effect=BrokenPipeError()
        terminal=qualifier.RESULT if operation=='qualify-recovery' else runner.RESULT
        async def consume(active):
            self.assertIs(session.handoff._task(),asyncio.current_task())
            self.assertEqual(session._live(active)['root'],self.root)
            peer.sendall.assert_called_once(); peer.shutdown.assert_called_once()
            self.assertTrue((path/'accepted.json').is_file())
            self.assertFalse((path/'result.json').exists())
            session.recheck(active)
            if failure: raise asyncio.CancelledError('local synthetic operation cancellation')
            evidence.save(self.root/'.runtime/stage2'/terminal,{'actual_local_producer_not_native':True})
            if drift:
                source=self.root/'stage2/no_cutoff_recovery_service.py'; source.write_bytes(source.read_bytes()+b' ')
            if relay_failure: service._failure(path,'relay-failure.json',expected)
            return {'ignored':'not terminal evidence'}
        module=qualifier if operation=='qualify-recovery' else runner
        name='qualify' if operation=='qualify-recovery' else 'run'
        async def execute():
            with os.fdopen(reader,'rb',buffering=0) as stream:
                try:
                    return await service.execute_session(NONCE,self.files,self.commit,self.identities,
                        stream,peer,path,intent,operation)
                except BaseException:
                    service._failure(path,'failure.json',expected); raise
        try:
            with patch.object(module,name,side_effect=consume) as entry:
                value=asyncio.run(execute())
                self.assertEqual(entry.await_count,1)
        finally:
            thread.join(10); self.assertFalse(thread.is_alive())
        if errors: raise errors[0]
        return path,value,peer,sent

    def test_qualifier_consumes_actual_session_and_success_follows_context_exit(self):
        path,value,peer,sent=self.invoke('qualify-recovery')
        accepted=boot.loads((path/'accepted.json').read_bytes())
        connection.reply(accepted,NONCE,self.files,self.commit,sent=sent[0],peer=PEER,operation='qualify-recovery')
        self.assertFalse(session._SESSIONS); self.assertFalse(handoff._WITNESSES)
        self.assertEqual(value,boot.loads((path/'result.json').read_bytes()))
        self.assertIn('.runtime/stage2/'+qualifier.RESULT,value['terminal_files'])
        self.assertFalse(value['paid_launch_ready']); self.f.e.collect.assert_called_once()

    def test_dispatch_stays_native_after_client_disconnect_and_binds_actual_terminal(self):
        path,value,peer,_=self.invoke('run-recovery',disconnect=True)
        self.assertTrue((path/'result.json').is_file())
        self.assertIn('.runtime/stage2/'+runner.RESULT,value['terminal_files'])
        self.assertFalse((path/'failure.json').exists())

    def test_late_relay_failure_is_retained_without_cancelling_committed_work(self):
        path,value,_,_=self.invoke('run-recovery',disconnect=True,relay_failure=True)
        self.assertTrue((path/'result.json').is_file()); self.assertTrue((path/'relay-failure.json').is_file())
        self.assertFalse((path/'failure.json').exists())

    def manager(self,**changes):
        return dict(LoadState='loaded',ActiveState='active',SubState='exited',MainPID='0',
            InvocationID='b2'*16,Result='success',ExecMainCode='1',ExecMainStatus='0',ExecMainPID=str(PEER['pid']),
            NRestarts='0',Restart='no',Type='exec',RemainAfterExit='yes',WorkingDirectory=str(self.root),**changes)

    def completed(self,operation,manager=None):
        live=dict(root=self.root,inputs={'files':self.files},witness=object())
        with patch.object(session,'_live',return_value=live), \
                patch.object(handoff,'_live',return_value={'header':{'operator':{'operator_commit':self.commit}}}), \
                patch.object(service,'_execution_manager',side_effect=manager or (lambda _:self.manager())), \
                patch.object(service,'_process_ended'):
            return service.completed_operation(object(),operation)

    def test_completed_reader_requires_manager_exit_and_rereads_actual_producers(self):
        path,_,_,_=self.invoke('qualify-recovery')
        value=self.completed('qualify-recovery')
        self.assertIn(service.operation_state('qualify-recovery')+'/result.json',value['files'])
        terminal=self.root/'.runtime/stage2'/qualifier.RESULT
        terminal.write_bytes(b'{}'); terminal.chmod(0o600)
        with self.assertRaises(ValueError): self.completed('qualify-recovery')

    def test_read_only_completed_status_never_opens_session_or_reads_archive(self):
        self.invoke('qualify-recovery')
        with patch.object(service,'_execution_manager',return_value=self.manager()), \
                patch.object(service,'_process_ended'), \
                patch.object(session,'open_session',side_effect=AssertionError('No new session')), \
                patch.object(handoff,'send',side_effect=AssertionError('No archive transfer')):
            value=service.operation_status(self.files,self.commit,self.identities,'qualify-recovery')
        self.assertEqual(value['status'],'service_exited_successfully_not_completed_study_audit')
        self.assertFalse(value['paid_launch_ready'])

    def test_later_revision_with_identical_bytes_preserves_actual_operation_commit(self):
        self.invoke('qualify-recovery')
        with patch.object(service,'_execution_manager',return_value=self.manager()), \
                patch.object(service,'_process_ended'):
            value=service._completed_operation(self.files,'f'*40,'qualify-recovery')
        self.assertFalse(value['paid_launch_ready'])

    def test_manager_refuses_not_found_defaults_restarts_and_wrong_root(self):
        for change in (None,('LoadState','not-found'),('NRestarts','1'),
                ('RemainAfterExit','no'),('WorkingDirectory','/other')):
            state=self.manager()
            if change: state[change[0]]=change[1]
            raw='\n'.join(k+'='+v for k,v in state.items())
            with patch.object(service.subprocess,'check_output',return_value=raw):
                if change:
                    with self.assertRaises(ValueError): service._execution_manager('qualify-recovery')
                else: self.assertEqual(service._execution_manager('qualify-recovery'),state)

    def test_completed_reader_refuses_running_failed_missing_or_different_invocation(self):
        self.invoke('qualify-recovery')
        for field,value in [('ActiveState','inactive'),('SubState','running'),('MainPID','123'),
                ('Result','exit-code'),('ExecMainStatus','1'),('InvocationID','c3'*16)]:
            state=self.manager(); state[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):
                self.completed('qualify-recovery',lambda _:state)

    def test_completed_reader_refuses_same_byte_replacement_after_last_manager_read(self):
        path,_,_,_=self.invoke('qualify-recovery'); calls=[]
        def manager(_):
            calls.append(1)
            if len(calls)==2:
                result=path/'result.json'; raw=result.read_bytes(); result.unlink()
                result.write_bytes(raw); result.chmod(0o600)
            return self.manager()
        with self.assertRaises(ValueError): self.completed('qualify-recovery',manager)

    def test_completed_reader_allows_only_valid_transport_failure_not_native_failure(self):
        path,_,_,_=self.invoke('run-recovery',relay_failure=True)
        self.completed('run-recovery')
        service._failure(path,'failure.json',service.base(NONCE,self.files,self.commit,'run-recovery'))
        with self.assertRaises(ValueError): self.completed('run-recovery')

    def test_paid_admission_requires_real_completed_service_read_not_only_qualification_json(self):
        sentinel=object(); verified=dict(root=self.root,files=self.files.copy(),identities=evidence.capture(self.root,self.files)[1])
        with patch.object(qualification,'verify',return_value=verified), \
                patch.object(service,'completed_operation',side_effect=ValueError('still running')) as actual, \
                patch.object(session,'invalidate') as invalidate:
            with self.assertRaises(ValueError): qualification.for_dispatch(sentinel)
            actual.assert_called_once_with(sentinel,'qualify-recovery'); invalidate.assert_called_once_with(sentinel)

    def test_only_execution_units_retain_successful_exit_metadata_without_live_jobs(self):
        for operation in ('qualify-recovery','run-recovery'):
            path=self.root/service.operation_state(operation); path.mkdir(mode=0o700)
            self.assertIn('--property=RemainAfterExit=yes',service.service_command(NONCE,self.files,self.commit,PEER,operation))

    def test_incomplete_handoff_never_acknowledges_or_runs_operation(self):
        with self.assertRaises(ValueError): self.invoke('run-recovery',packet=self.f.packet(committed=False))
        path=self.root/service.operation_state('run-recovery')
        self.assertFalse((path/'accepted.json').exists()); self.assertFalse((path/'result.json').exists())

    def test_cancelled_operation_retains_acceptance_and_failure_not_completion(self):
        with self.assertRaises(asyncio.CancelledError): self.invoke('qualify-recovery',failure=True)
        path=self.root/service.operation_state('qualify-recovery')
        self.assertTrue((path/'accepted.json').exists()); self.assertTrue((path/'failure.json').exists())
        self.assertFalse((path/'result.json').exists()); self.assertFalse(session._SESSIONS)

    def test_final_recheck_failure_cannot_turn_accepted_handoff_into_success(self):
        with self.assertRaises(ValueError): self.invoke('qualify-recovery',drift=True)
        path=self.root/service.operation_state('qualify-recovery')
        self.assertTrue((path/'accepted.json').exists()); self.assertFalse((path/'result.json').exists())

    def test_only_fixed_operations_generate_committed_programs_and_separate_state(self):
        states=set()
        for operation in service.OPERATIONS:
            states.add(service.operation_state(operation))
            program=connection.native_program(NONCE,self.files,self.commit,role='relay',operation=operation)
            ast.parse(program); self.assertIn(repr(operation),program)
            self.assertIn(service.OPERATIONS[operation],service.identity(NONCE,operation))
        self.assertEqual(len(states),3)
        for bad in ('restart','stop','shell','run-baseline',None):
            with self.assertRaises(ValueError): connection.native_program(NONCE,self.files,self.commit,role='relay',operation=bad)

    def test_mac_acknowledgement_is_not_completion_and_cannot_be_replayed(self):
        operation='qualify-recovery'
        base=service.base(NONCE,self.files,self.commit,operation)
        ready=dict(base,kind='recovery_receiver_ready_not_authenticated',native_process=PEER)
        sent=dict(operator_document_sha256='1'*64,archive_sha256='2'*64)
        accepted=dict(base,kind='recovery_handoff_committed_operation_accepted_not_completed',native_process=PEER,
            prerequisites_sha256='3'*64,**sent)
        process=Mock(stdin=io.BytesIO(),stdout=io.BytesIO(),wait=Mock(return_value=0),poll=Mock(return_value=None))
        with patch.object(connection.subprocess,'Popen',return_value=process) as start, \
                patch.object(connection,'read_reply',side_effect=[ready,accepted]), \
                patch.object(handoff,'send',return_value=sent) as send:
            self.assertEqual(connection.qualify_native(self.commit),accepted)
            send.assert_called_once_with(process.stdin); process.kill.assert_not_called()
            with self.assertRaises(ValueError): connection.qualify_native(self.commit)
            start.assert_called_once()
        self.assertFalse(accepted['recovery_execution_qualified'])

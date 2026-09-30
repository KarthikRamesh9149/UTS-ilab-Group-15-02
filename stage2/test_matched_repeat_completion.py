"""Protected real retained files, with actual manager/procfs calls mocked."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import matched_repeat_completion as completion
import matched_repeat_policy as policy
import matched_repeat_session as session
import no_cutoff_recovery_files as files
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


class CompletionTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.enterContext(patch.dict(completion.runtime.DEPLOYMENTS,{'terminus-2':self.root}))
        self.enterContext(patch.object(completion,'__file__',str(self.root/'stage2/matched_repeat_completion.py')))
        save(self.root,'stage2/fixture.py',b'# synthetic only')
        self.bound=files.capture(self.root,['stage2/fixture.py'])[0]
        self.enterContext(patch.object(session,'_live',return_value=dict(root=self.root,harness='terminus-2',files=self.bound)))
        self.operation='qualify-repeat'; self.relative=completion.operation_state(self.operation)
        self.path=self.root/self.relative
        self.expected=completion.base('terminus-2','1'*32,self.bound,'2'*40,self.operation)
        self.process=dict(pid=12345,start_ticks=123456)
        self.invocation='3'*32
        self.write('intent.json',dict(self.expected,relay_process=dict(pid=12344,start_ticks=123450),created_utc='2026-09-30T00:00:00Z'))
        self.write('service-started.json',dict(self.expected,native_process=self.process,invocation_id=self.invocation))
        prerequisites=dict(inputs=self.bound,harness='terminus-2',
            completed_recovery=dict(kind='live_completed_recovery_for_baseline_not_admission',harness='terminus-2',
                operator_commit='2'*40,paid_launch_ready=False,recovery_document_sha256='6'*64,archive_sha256='7'*64),
            predecessor=dict(operator_document_sha256='4'*64,streamed_backup={'sha256':'5'*64}))
        raw=self.write('prerequisites.json',prerequisites)
        self.write('accepted.json',dict(self.expected,kind='baseline_handoff_committed_operation_accepted_not_completed',
            native_process=self.process,prerequisites_sha256=hashlib.sha256(raw).hexdigest(),
            operator_document_sha256='4'*64,archive_sha256='5'*64,
            recovery_document_sha256='6'*64,recovery_archive_sha256='7'*64))
        save(self.root,self.relative+'/service.log',b'private diagnostic fixture\n')
        terminal=completion.RT+policy.QUALIFIER_RESULT_FILE
        save(self.root,terminal,b'{"synthetic_qualification_only":true}')
        self.result=dict(self.expected,kind='baseline_service_operation_finished_not_completed_study_audit',
            terminal_files=files.capture(self.root,[terminal])[0],
            log_files=files.capture(self.root,[self.relative+'/service.log'])[0],
            completed_utc='2026-09-30T00:01:00Z')
        self.write('result.json',self.result)
        self.state=dict(LoadState='loaded',ActiveState='active',SubState='exited',MainPID='0',
            InvocationID=self.invocation,Result='success',ExecMainCode='1',ExecMainStatus='0',
            ExecMainPID=str(self.process['pid']),NRestarts='0',Restart='no',Type='exec',
            RemainAfterExit='yes',WorkingDirectory=str(self.root))
        self.manager=self.enterContext(patch.object(completion,'manager',side_effect=lambda *a:deepcopy(self.state)))
        self.ended=self.enterContext(patch.object(completion,'process_ended'))

    def write(self,name,value):
        raw=json.dumps(value).encode(); save(self.root,self.relative+'/'+name,raw); return raw

    def read(self): return completion.read(object(),self.operation)

    def test_actual_files_and_two_manager_observations_are_required(self):
        value=self.read()
        self.assertEqual(len(value['files']),7); self.assertEqual(set(value['files']),set(value['identities']))
        self.assertFalse(value['paid_launch_ready']); self.assertEqual(self.manager.call_count,2)
        self.ended.assert_called_once_with(self.process)

    def test_no_saved_or_cross_scope_authority(self):
        with patch.object(session,'_live',side_effect=ValueError('Invalid live session')):
            with self.assertRaises(ValueError): completion.read({'paid_launch_ready':True},self.operation)
        with patch.object(completion,'__file__','/different/matched_repeat_completion.py'):
            with self.assertRaises(ValueError): self.read()

    def test_running_failed_missing_restarted_or_wrong_invocation_never_completes(self):
        for key,value in (('ActiveState','failed'),('SubState','running'),('MainPID','12345'),
                ('ExecMainStatus','1'),('ExecMainPID','999'),('InvocationID','f'*32),('Result','failure')):
            with self.subTest(key=key):
                old=self.state[key]; self.state[key]=value
                with self.assertRaises(ValueError): self.read()
                self.state[key]=old

    def test_manager_change_after_procfs_refuses(self):
        changed=dict(self.state,InvocationID='f'*32)
        self.manager.side_effect=[self.state,changed]
        with self.assertRaisesRegex(ValueError,'unit identity'): self.read()

    def test_process_still_alive_refuses(self):
        self.ended.side_effect=ValueError('Still alive')
        with self.assertRaisesRegex(ValueError,'alive'): self.read()

    def test_same_byte_file_replacement_after_last_observation_refuses(self):
        path=self.path/'accepted.json'
        def replace(*args):
            if self.manager.call_count==2:
                raw=path.read_bytes(); path.rename(path.with_suffix('.old')); path.write_bytes(raw); path.chmod(0o600)
            return deepcopy(self.state)
        self.manager.side_effect=replace
        with self.assertRaises(ValueError): self.read()

    def test_retained_failure_extra_file_and_partial_state_refuse(self):
        for name in ('failure.json','unexpected.json'):
            self.write(name,{'status':'failed'})
            with self.subTest(name=name),self.assertRaises(ValueError): self.read()
            (self.path/name).unlink()
        (self.path/'result.json').unlink()
        with self.assertRaises((OSError,ValueError)): self.read()

    def test_lost_relay_acknowledgement_is_retained_without_becoming_a_native_failure(self):
        self.write('relay-failure.json',dict(self.expected,status='uncertain_preserve_evidence_inspect_without_retry'))
        self.assertIn(self.relative+'/relay-failure.json',self.read()['files'])
        self.write('relay-failure.json',dict(self.expected,status='native_failed'))
        with self.assertRaises(ValueError): self.read()

    def test_changed_terminal_or_private_permissions_refuse(self):
        terminal=self.root/next(iter(self.result['terminal_files']))
        saved=terminal.read_bytes(); terminal.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.read()
        terminal.write_bytes(saved); terminal.chmod(0o644)
        with self.assertRaises(ValueError): self.read()

    def test_wrong_operation_harness_revision_and_source_maps_refuse(self):
        for args in (('custom','1'*32,self.bound,'2'*40,'qualify-repeat'),
                ('terminus-2','bad',self.bound,'2'*40,'qualify-repeat'),
                ('terminus-2','1'*32,self.bound,'2'*7,'qualify-repeat'),
                ('terminus-2','1'*32,{},'2'*40,'qualify-repeat'),
                ('terminus-2','1'*32,self.bound,'2'*40,'restart')):
            with self.subTest(args=args),self.assertRaises(ValueError): completion.base(*args)

    def test_reader_checks_raw_intent_prerequisite_and_accepted_identity(self):
        for name,field in (('intent.json','root'),('service-started.json','invocation_id'),
                ('prerequisites.json','harness'),('accepted.json','archive_sha256')):
            path=self.path/name; raw=path.read_bytes(); value=json.loads(raw); value[field]='incorrect'
            path.write_bytes(json.dumps(value).encode())
            with self.subTest(name=name),self.assertRaises(ValueError): self.read()
            path.write_bytes(raw)

    def test_duplicate_json_or_noninteger_process_identity_refuses(self):
        path=self.path/'intent.json'; raw=path.read_bytes()
        path.write_bytes(b'{"nonce":"a","nonce":"b"}')
        with self.assertRaises(ValueError): self.read()
        path.write_bytes(raw)
        value=json.loads((self.path/'service-started.json').read_bytes()); value['native_process']['pid']=True
        self.write('service-started.json',value)
        with self.assertRaises(ValueError): self.read()


class ManagerTests(unittest.TestCase):
    def test_actual_command_and_strict_manager_config(self):
        root=completion.runtime.DEPLOYMENTS['terminus-2']
        state=dict(LoadState='loaded',ActiveState='active',SubState='exited',MainPID='0',
            InvocationID='a'*32,Result='success',ExecMainCode='1',ExecMainStatus='0',ExecMainPID='123',
            NRestarts='0',Restart='no',Type='exec',RemainAfterExit='yes',WorkingDirectory=str(root))
        real=completion.manager
        def run(value):
            text='\n'.join(k+'='+v for k,v in value.items())+'\n'
            with patch.object(completion.subprocess,'check_output',return_value=text) as command:
                result=real(root,'fixed.service')
                self.assertEqual(command.call_args.args[0][:3],['systemctl','show','fixed.service'])
                self.assertEqual(command.call_args.kwargs['timeout'],10)
                return result
        self.assertEqual(run(state),state)
        for key,value in (('LoadState','not-found'),('Restart','always'),('NRestarts','1'),
                ('Type','simple'),('RemainAfterExit','no'),('WorkingDirectory','/other'),('InvocationID','')):
            with self.subTest(key=key),self.assertRaises(ValueError): run(dict(state,**{key:value}))
        raw='\n'.join(k+'='+v for k,v in state.items())+'\nLoadState=loaded\n'
        with patch.object(completion.subprocess,'check_output',return_value=raw),self.assertRaises(ValueError):
            real(root,'fixed.service')

    def test_process_ended_requires_absence_or_distinct_start_ticks(self):
        process=dict(pid=123,start_ticks=456)
        with patch.object(Path,'read_text',side_effect=FileNotFoundError): completion.process_ended(process)
        for content in ('123 (x) S','123 (x) '+' '.join(['S']*19+['456'])):
            with patch.object(Path,'read_text',return_value=content),self.assertRaises(ValueError):
                completion.process_ended(process)
        with patch.object(Path,'read_text',return_value='123 (x) '+' '.join(['S']*19+['999'])):
            completion.process_ended(process)

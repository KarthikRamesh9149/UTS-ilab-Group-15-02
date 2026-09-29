"""Local file/proc fixtures and mocked manager queries, not native proof."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import no_cutoff_final_guard as guard
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_backup as backup
import no_cutoff_final_report as report
import matched_repeat_amended_handoff as handoff


def state(load='not-found'):
    return dict(LoadState=load, ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0')


def journal():
    common = dict(_PID='1', _UID='0', _COMM='systemd', _BOOT_ID=guard.BOOT,
        SYSLOG_IDENTIFIER='systemd', UNIT=guard.SERVICE, INVOCATION_ID=guard.INVOCATION)
    return [dict(common, MESSAGE_ID=guard.START_ID, __REALTIME_TIMESTAMP=guard.START, JOB_TYPE='start', JOB_RESULT='done'),
        dict(common, MESSAGE_ID=guard.SUCCESS_ID, __REALTIME_TIMESTAMP=guard.END,
            MESSAGE=guard.SERVICE + ': Deactivated successfully.'),
        dict(common, MESSAGE_ID=guard.USAGE_ID, __REALTIME_TIMESTAMP=str(int(guard.END) + 553))]


class Files(unittest.TestCase):
    def setUp(self):
        self.base = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.root = self.base/'frozen'; self.root.mkdir(mode=0o700)
        self.enterContext(patch.object(guard, 'ROOT', self.root))
        self.enterContext(patch.object(guard, 'OWNER', os.getuid()))
        self.enterContext(patch.object(guard, 'GROUP', os.getgid()))
        # Linux ACL metadata is mocked on macOS; file bytes/modes stay real.
        self.enterContext(patch.object(guard.os, 'listxattr', return_value=[], create=True))
        self.file = self.root/'stage2/public.py'; self.file.parent.mkdir(mode=0o775)
        self.file.parent.chmod(0o775); self.file.write_bytes(b'bound source'); self.file.chmod(0o664)
        self.private = self.root/'.runtime/stage2/input.json'; self.private.parent.mkdir(parents=True,mode=0o700)
        self.private.write_bytes(b'{"value":1.0}'); self.private.chmod(0o600)

    def read(self, name='stage2/public.py'):
        return phase._file(self.root,name,{})


class ProtectionTests(Files):
    def test_root_only_tree_allows_unchanged_root_group_public_bytes(self):
        self.assertEqual(self.read(),hashlib.sha256(self.file.read_bytes()).hexdigest())
        self.assertEqual(self.file.stat().st_mode & 0o777,0o664)
        self.assertEqual(self.file.parent.stat().st_mode & 0o777,0o775)

    def test_protected_root_and_public_directory_are_checked_even_without_file_read(self):
        phase._path(self.root,'stage2')
        self.root.chmod(0o755)
        with self.assertRaises(ValueError):phase._path(self.root,'stage2/missing')

    def test_no_group_write_exception_for_another_root(self):
        other=self.base/'other';(other/'stage2').mkdir(parents=True)
        p=other/'stage2/public.py';p.write_bytes(b'bound');p.chmod(0o664)
        with self.assertRaises(ValueError):phase._file(other,'stage2/public.py',{})

    def test_private_inputs_cannot_be_group_readable_or_writable(self):
        for mode in (0o640,0o660,0o664,0o644):
            self.private.chmod(mode)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.read('.runtime/stage2/input.json')

    def test_world_writable_and_special_source_modes_refused(self):
        for mode in (0o666,0o1664,0o2664,0o4664):
            self.file.chmod(mode)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.read()

    def test_world_writable_or_special_public_directory_refused(self):
        for mode in (0o777,0o1775,0o2775):
            self.file.parent.chmod(mode)
            with self.subTest(mode=mode),self.assertRaises(ValueError):self.read()

    def test_private_directory_cannot_be_group_writable(self):
        self.private.parent.chmod(0o775)
        with self.assertRaises(ValueError):self.read('.runtime/stage2/input.json')

    def test_writable_parent_refuses_even_if_frozen_root_is_private(self):
        self.base.chmod(0o770)
        with self.assertRaises(ValueError):self.read()
        self.base.chmod(0o700)

    def test_wrong_source_group_refused(self):
        with patch.object(guard,'GROUP',os.getgid()+1),self.assertRaises(ValueError):self.read()

    def test_wrong_source_owner_refused(self):
        with patch.object(guard,'OWNER',os.getuid()+1),self.assertRaises(ValueError):self.read()

    def test_access_or_default_acl_refused(self):
        for attribute in ('system.posix_acl_access','system.posix_acl_default'):
            with patch.object(guard.os,'listxattr',return_value=[attribute]),self.assertRaises(ValueError):self.read()

    def test_acl_observation_error_is_fail_closed(self):
        with patch.object(guard.os,'listxattr',side_effect=PermissionError),self.assertRaises((OSError,ValueError)):self.read()

    def test_symlinked_source_directory_refused(self):
        target=self.base/'alias-target';self.file.parent.rename(target);self.file.parent.symlink_to(target)
        with self.assertRaises(ValueError):self.read()

    def test_source_hardlink_and_fifo_refused(self):
        os.link(self.file,self.base/'hard')
        with self.assertRaises(ValueError):self.read()
        self.file.unlink();os.mkfifo(self.file,0o600)
        with self.assertRaises(ValueError):self.read()

    def test_root_protection_change_during_hashing_refuses(self):
        real=guard.hashlib.file_digest
        def changed(*args,**kwargs):
            value=real(*args,**kwargs);self.root.chmod(0o755);return value
        with patch.object(guard.hashlib,'file_digest',side_effect=changed),self.assertRaises(ValueError):self.read()

    def test_file_replacement_during_hashing_refuses(self):
        real=guard.hashlib.file_digest
        def changed(*args,**kwargs):
            value=real(*args,**kwargs);self.file.rename(self.base/'old')
            self.file.write_bytes(b'bound source');self.file.chmod(0o664);return value
        with patch.object(guard.hashlib,'file_digest',side_effect=changed),self.assertRaises(ValueError):self.read()

    def test_backup_and_handoff_use_same_protected_source_rule(self):
        with patch.object(report,'ROOT',self.root):
            self.assertEqual(backup._digest(self.root,'stage2/public.py')[0],self.read())
            self.assertEqual(handoff._raw(self.root,'stage2/public.py'),b'bound source')
            self.root.chmod(0o755)
            with self.assertRaises(ValueError):backup._digest(self.root,'stage2/public.py')
            with self.assertRaises(ValueError):handoff._raw(self.root,'stage2/public.py')

    def test_backup_rechecks_protection_after_read(self):
        with patch.object(report,'ROOT',self.root),self.assertRaises(ValueError):
            with backup._open(self.root,'stage2/public.py') as (stream,_):
                stream.read();self.root.chmod(0o755)


class CompletionTests(Files):
    def setUp(self):
        super().setUp()
        self.proc=self.base/'proc';self.proc.mkdir()
        self.enterContext(patch.object(guard,'PROC',self.proc))
        self.cg=self.base/'absent-cgroup';self.enterContext(patch.object(guard,'CGROUP',self.cg))
        self.enterContext(patch.object(guard.sys,'platform','linux'))
        self.process(1)
        (self.proc/'1/comm').write_text('systemd\n')
        p=self.proc/'sys/kernel/random/boot_id';p.parent.mkdir(parents=True);p.write_text(guard.BOOT)
        self.records=journal();self.current=state()
        self.command=self.enterContext(patch.object(guard,'_command',side_effect=self.command_value))

    def process(self,pid,group='0::/system.slice/unrelated.service\n',cwd=None,exe=None):
        p=self.proc/str(pid);p.mkdir();(p/'cgroup').write_text(group)
        if cwd is not None:(p/'cwd').symlink_to(cwd)
        if exe is not None:(p/'exe').symlink_to(exe)

    def command_value(self,args):
        if args[0]=='systemctl':return ''.join(k+'='+v+'\n' for k,v in self.current.items())
        if args[0]=='journalctl':return '\n'.join(json.dumps(v) for v in self.records)
        raise AssertionError('Unexpected native command')

    def test_unloaded_unit_needs_actual_manager_and_process_checks(self):
        value=guard.service();guard.validate_service(value)
        self.assertEqual(value['LoadState'],'not-found')
        self.assertEqual(value['completion']['invocation_id'],guard.INVOCATION)
        self.assertEqual([v.args[0][0] for v in self.command.call_args_list],['systemctl','journalctl','systemctl'])

    def test_loaded_inactive_unit_still_needs_same_invocation_evidence(self):
        self.current=state('loaded');self.assertEqual(guard.service()['LoadState'],'loaded')
        self.records=[]
        with self.assertRaises(ValueError):guard.service()

    def test_default_exit_zero_without_journal_is_not_success(self):
        self.records=[]
        with self.assertRaises(ValueError):guard.service()

    def test_missing_success_record_refused(self):
        self.records.pop(1)
        with self.assertRaises(ValueError):guard.service()

    def test_duplicate_success_or_additional_invocation_refused(self):
        for row in (self.records[1],dict(self.records[0],INVOCATION_ID='0'*32)):
            original=deepcopy(self.records);self.records.append(row)
            with self.assertRaises(ValueError):guard.service()
            self.records=original

    def test_wrong_trusted_manager_fields_refused(self):
        for key in ('_PID','_UID','_COMM','_BOOT_ID','SYSLOG_IDENTIFIER','UNIT','INVOCATION_ID'):
            original=deepcopy(self.records);self.records[1][key]='wrong'
            with self.subTest(key=key),self.assertRaises(ValueError):guard.service()
            self.records=original

    def test_failure_message_or_id_is_not_success(self):
        for key,value in (('MESSAGE','failed'),('MESSAGE_ID','0'*32)):
            original=deepcopy(self.records);self.records[1][key]=value
            with self.assertRaises(ValueError):guard.service()
            self.records=original

    def test_wrong_start_completion_time_or_start_job_refused(self):
        for index,key,value in ((0,'__REALTIME_TIMESTAMP','1'),(1,'__REALTIME_TIMESTAMP','2'),
                (0,'JOB_RESULT','failed'),(0,'JOB_TYPE','restart'),(2,'__REALTIME_TIMESTAMP',str(int(guard.END)+2000000))):
            original=deepcopy(self.records);self.records[index][key]=value
            with self.assertRaises(ValueError):guard.service()
            self.records=original

    def test_duplicate_or_malformed_journal_json_refused(self):
        for raw in ('{"a":1,"a":2}','[]','not-json'):
            with patch.object(guard,'_command',return_value=raw),self.assertRaises(ValueError):guard._journal()

    def test_no_raw_manager_text_returned(self):
        self.records[0]['MESSAGE']='PRIVATE-MANAGER-SENTINEL'
        self.assertNotIn('PRIVATE-MANAGER-SENTINEL',json.dumps(guard.service()))

    def test_active_failed_unknown_or_nonzero_service_refused(self):
        for key,value in (('LoadState','error'),('ActiveState','active'),('SubState','running'),('MainPID','99'),('ExecMainStatus','1')):
            self.current=state();self.current[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):guard.service()

    def test_duplicate_or_malformed_service_properties_refused(self):
        good=''.join(k+'='+v+'\n' for k,v in state().items())
        for raw in (good+'MainPID=0\n',good+'unexpected\n',good+'Extra=field\n'):
            with patch.object(guard,'_command',return_value=raw),self.assertRaises(ValueError):guard._state()

    def test_changed_state_after_process_scan_refused(self):
        with patch.object(guard,'_state',side_effect=[state(),state('loaded')]),self.assertRaises(ValueError):guard.service()

    def test_reboot_or_non_manager_pid1_refused(self):
        p=self.proc/'1/comm';p.write_text('other')
        with self.assertRaises(ValueError):guard.service()
        p.write_text('systemd');(self.proc/'sys/kernel/random/boot_id').write_text('0'*32)
        with self.assertRaises(ValueError):guard.service()

    def test_existing_or_symlinked_service_cgroup_refused(self):
        self.cg.mkdir()
        with self.assertRaises(ValueError):guard.service()
        self.cg.rmdir();self.cg.symlink_to(self.base/'missing')
        with self.assertRaises(ValueError):guard.service()

    def test_process_in_service_cgroup_refused(self):
        self.process(123,group='0::/system.slice/'+guard.SERVICE+'/child\n')
        with self.assertRaises(ValueError):guard.service()

    def test_process_in_execution_directory_or_binary_refused(self):
        self.process(123,cwd=self.root/'stage2')
        with self.assertRaises(ValueError):guard.service()
        (self.proc/'123/cwd').unlink();(self.proc/'123/exe').symlink_to(self.root/'.venv/bin/python')
        with self.assertRaises(ValueError):guard.service()

    def test_only_observing_process_is_excluded(self):
        self.process(os.getpid(),cwd=self.root)
        guard.service()

    def test_unrelated_process_and_kernel_thread_are_not_rejected(self):
        self.process(123,cwd=self.base/'unrelated');self.process(124)
        guard.service()

    def test_unreadable_or_malformed_process_metadata_refused(self):
        self.process(123,group='malformed')
        with self.assertRaises(ValueError):guard.service()

    def test_stop_and_dangling_stop_symlink_refuse(self):
        p=self.root/'.runtime/stage2/provider-stop.json';p.write_bytes(b'{}')
        with self.assertRaises(ValueError):guard.service()
        p.unlink();p.symlink_to(self.base/'missing')
        with self.assertRaises(ValueError):guard.service()

    def test_snapshot_metadata_cannot_drop_loadstate_or_completion_evidence(self):
        value=guard.service()
        for key in ('LoadState','completion'):
            bad=deepcopy(value);del bad[key]
            with self.assertRaises(ValueError):guard.validate_service(bad)

    def test_snapshot_numeric_boolean_substitution_is_refused(self):
        value=guard.service();value['completion']['other_execution_processes']=False
        with self.assertRaises(ValueError):guard.validate_service(value)


class SourceTests(unittest.TestCase):
    def test_source_is_bound_before_stdlib_bootstrap_execution(self):
        raw=Path(guard.__file__).read_bytes()
        self.assertEqual(guard.source(hashlib.sha256(raw).hexdigest()),raw)
        with self.assertRaises(ValueError):guard.source('0'*64)

    def test_fixed_observer_has_no_root_service_callback_or_saved_proof_argument(self):
        for kwargs in ({'root':'/other'},{'service':'other.service'},{'proof':{}},{'callback':lambda:True}):
            with self.assertRaises(TypeError):guard.service(**kwargs)

    def test_native_command_is_credential_free_and_error_type_only(self):
        with patch.object(guard.subprocess,'run',return_value=NS(returncode=0,stdout='metadata')) as run:
            self.assertEqual(guard._command(['systemctl','show',guard.SERVICE]),'metadata')
        self.assertEqual(run.call_args.kwargs['env'],guard.ENVIRONMENT)
        with patch.object(guard.subprocess,'run',return_value=NS(returncode=1,stdout='PRIVATE',stderr='PRIVATE')):
            with self.assertRaises(ValueError) as caught:guard._command(['systemctl'])
        self.assertNotIn('PRIVATE',str(caught.exception))


if __name__=='__main__':unittest.main()

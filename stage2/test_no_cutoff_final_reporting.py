"""Real local files/guards with mocked Linux, SSH and native audit observations."""
from contextlib import ExitStack
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

import no_cutoff_final_reporting as launch
import no_cutoff_final_report as report
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_archive as archive
import test_no_cutoff_final_archive as fixtures


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory()); self.root=Path(self.temp).resolve()
        self.enterContext(patch.object(launch,'REPO',self.root))
        self.commit='a'*40
        self.bindings=dict(commit=self.commit,native={'stage2/frozen.py':'1'*64},
            reporting={'stage2/report.py':'2'*64},local={},anchors={})

    def file(self,name,raw=b'bound',mode=0o600):
        p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);p.chmod(mode);return p

    def test_exact_operator_file_read_is_private_and_hash_bound(self):
        self.file('.runtime/input.json',b'{"v":1.0}')
        self.assertEqual(launch._raw('.runtime/input.json',hashlib.sha256(b'{"v":1.0}').hexdigest()),b'{"v":1.0}')
        with self.assertRaises(ValueError):launch._raw('.runtime/input.json','0'*64)

    def test_permissions_links_and_missing_operator_files_refused(self):
        p=self.file('.runtime/input.json');p.chmod(0o644)
        with self.assertRaises(ValueError):launch._raw('.runtime/input.json')
        p.chmod(0o600);os.link(p,self.root/'hard')
        with self.assertRaises(ValueError):launch._raw('.runtime/input.json')
        (self.root/'alias').symlink_to(p)
        with self.assertRaises(ValueError):launch._raw('alias')
        with self.assertRaises(ValueError):launch._raw('missing')

    def test_operator_fifo_is_nonblocking_and_refused(self):
        os.mkfifo(self.root/'fifo',0o600);real=os.open
        def checked(path,flags,*args,**kwargs):
            self.assertTrue(flags & os.O_NONBLOCK);return real(path,flags,*args,**kwargs)
        with patch.object(launch.os,'open',side_effect=checked),self.assertRaises(ValueError):launch._raw('fifo')

    def test_operator_wrong_checkout_or_platform_refused(self):
        with self.assertRaises(ValueError):launch._operator()
        with patch.object(launch.platform,'system',return_value='Linux'),self.assertRaises(ValueError):launch._operator()

    def test_full_commit_head_and_fetched_origin_are_required(self):
        for commit in ('a'*7,'HEAD','a'*39+';',''):
            with self.assertRaises(ValueError):launch._prepare(commit)
        with patch.object(launch,'_bindings',return_value=self.bindings),patch.object(launch,'_git',return_value=b'b'*40),self.assertRaises(ValueError):
            launch._prepare(self.commit)

    def test_committed_source_bytes_cannot_differ(self):
        self.bindings['local']={'stage2/report.py':hashlib.sha256(b'good').hexdigest()}
        with patch.object(launch,'_bindings',return_value=self.bindings),patch.object(launch,'_git',side_effect=[self.commit.encode(),self.commit.encode(),b'changed']),self.assertRaises(ValueError):
            launch._prepare(self.commit)

    def test_prepare_reads_actual_committed_bytes_without_network(self):
        self.bindings['local']={'stage2/report.py':hashlib.sha256(b'good').hexdigest()}
        with patch.object(launch,'_bindings',return_value=self.bindings),patch.object(launch,'_git',side_effect=[self.commit.encode(),self.commit.encode(),b'good']) as git:
            value=launch._prepare(self.commit)
        self.assertEqual(value['commit'],self.commit);self.assertEqual(git.call_count,3)

    def test_recheck_detects_source_and_revision_changes(self):
        p=self.file('stage2/source.py');self.bindings['local']={'stage2/source.py':hashlib.sha256(b'bound').hexdigest()}
        with patch.object(launch,'_git',return_value=self.commit.encode()):launch._recheck(self.bindings)
        p.write_bytes(b'changed')
        with self.assertRaises(ValueError):launch._recheck(self.bindings)
        p.write_bytes(b'bound')
        with patch.object(launch,'_git',return_value=b'b'*40),self.assertRaises(ValueError):launch._recheck(self.bindings)

    def test_existing_pinned_ssh_options_and_single_original_interpreter(self):
        cmd=launch._command();remote=shlex.split(cmd[-1])
        self.assertEqual(cmd[:-1],launch.dashboard.ssh_command(self.root)[:-2])
        self.assertEqual(cmd[-2],'root@62.83.32.126')
        self.assertEqual(remote[-4:],[str(report.ROOT/'.venv/bin/python'),'-I','-B','-'])
        self.assertEqual(remote[:2],['/usr/bin/env','-i'])
        self.assertEqual(dict(v.split('=',1) for v in remote[2:-4]),report.ENVIRONMENT)
        self.assertNotIn('python3',cmd);self.assertIn('StrictHostKeyChecking=yes',cmd)

    def test_changed_ssh_destination_refused(self):
        with patch.object(launch.dashboard,'ssh_command',return_value=['ssh','other','python3','-']),self.assertRaises(ValueError):launch._command()

    def invoke(self,operation,reply=None,error=None,recheck=None):
        if reply is None:reply=dict(kind=launch.KIND,operation=operation,operator_commit=self.commit,
            reporting_source_files=self.bindings['reporting'],execution_source_set_sha256=phase.SOURCE_SET,
            completed_final_audit=False,off_server_backup_verified=False,paid_launch_ready=False)
        with ExitStack() as stack:
            stack.enter_context(patch.object(launch,'_prepare',return_value=self.bindings))
            stack.enter_context(patch.object(launch,'_program',return_value='fixed program'))
            checked=stack.enter_context(patch.object(launch,'_recheck',side_effect=recheck))
            called=stack.enter_context(patch.object(launch.subprocess,'run',side_effect=error,
                return_value=NS(returncode=0,stdout=json.dumps(reply).encode(),stderr=b'PRIVATE-DIAGNOSTIC')))
            value=launch._invoke(self.commit,operation)
        return value,called,checked

    def test_fixed_inspection_reply_is_not_audit_or_backup_authority(self):
        value,called,checked=self.invoke('inspect')
        self.assertFalse(value['paid_launch_ready']);self.assertEqual(called.call_count,1);self.assertEqual(checked.call_count,3)
        self.assertEqual(called.call_args.kwargs['env'],{'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        self.assertEqual(called.call_args.kwargs['input'],b'fixed program')

    def test_native_connection_failure_has_no_retry_or_raw_diagnostics(self):
        with self.assertRaisesRegex(ValueError,'uncertain') as caught:
            self.invoke('deploy',error=subprocess.TimeoutExpired('PRIVATE-DIAGNOSTIC',300))
        self.assertNotIn('PRIVATE-DIAGNOSTIC',str(caught.exception))

    def test_reply_cannot_claim_paid_authority_or_change_binding(self):
        for value in ({'paid_launch_ready':True},{'raw':'PRIVATE-DIAGNOSTIC'}):
            with self.subTest(value=value),self.assertRaises(ValueError):self.invoke('inspect',reply=value)

    def test_post_ssh_local_mutation_refuses_success(self):
        with self.assertRaisesRegex(ValueError,'changed'):
            self.invoke('inspect',recheck=[None,ValueError('changed')])

    def test_nonzero_ssh_exit_duplicate_or_oversized_metadata_refused(self):
        with patch.object(launch,'_prepare',return_value=self.bindings),patch.object(launch,'_program',return_value='fixed'),\
                patch.object(launch,'_recheck'),patch.object(launch,'WINDOW',100):
            for status,raw in ((1,b'{}'),(0,b'{"a":1,"a":2}'),(0,b' '*101)):
                with patch.object(launch.subprocess,'run',return_value=NS(returncode=status,stdout=raw,stderr=b'private')),self.assertRaises(ValueError):
                    launch._invoke(self.commit,'inspect')

    def test_collect_always_validates_fresh_returned_metadata(self):
        reply={'reporting_source_files':self.bindings['reporting']}
        with patch.object(archive,'validate_snapshot') as validate:
            value,called,_=self.invoke('collect',reply=reply)
        validate.assert_called_once_with(reply,{})
        self.assertEqual(value,reply);self.assertEqual(called.call_count,1)

    def test_public_operations_have_no_caller_root_or_callback(self):
        with patch.object(launch,'_invoke',return_value={}) as call:
            launch.deploy(self.commit);launch.inspect_deployment(self.commit);launch.collect(self.commit)
        self.assertEqual([v.args[1] for v in call.call_args_list],['deploy','inspect','collect'])
        with self.assertRaises(TypeError):launch.collect(self.commit,root=self.root)
        with self.assertRaises(ValueError):launch._program(self.bindings,'paid-run')


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temp=self.enterContext(tempfile.TemporaryDirectory());self.base=Path(self.temp).resolve()
        self.root=self.base/'execution';self.root.mkdir(mode=0o700);self.reporting=self.base/'reporting'
        p=self.root/'stage2/frozen.py';p.parent.mkdir();p.write_bytes(b'# frozen\n');p.chmod(0o644)
        (self.root/'.runtime/stage2').mkdir(parents=True,mode=0o700)
        self.native={'stage2/frozen.py':hashlib.sha256(p.read_bytes()).hexdigest()}
        self.payload={n:b'# source-bound synthetic bootstrap module\n' for n in
            ('stage2/no_cutoff_final_report.py','stage2/no_cutoff_final_archive.py','stage2/no_cutoff_final_backup.py')}
        self.sources={n:hashlib.sha256(raw).hexdigest() for n,raw in self.payload.items()}
        self.bindings=dict(commit='a'*40,native=self.native,reporting=self.sources)
        self.enterContext(patch.object(report,'ROOT',self.root));self.enterContext(patch.object(report,'REPORTING',self.reporting))
        self.enterContext(patch.object(launch,'_raw',side_effect=lambda n,sha:self.payload[n]))
        self.service=self.enterContext(patch.object(subprocess,'check_output',return_value=
            'LoadState=loaded\nActiveState=inactive\nSubState=dead\nMainPID=0\nExecMainStatus=0\n'))
        self.snapshot=dict(reporting_source_files=self.sources,supporting_file_sha256=self.native,
            directory_entries={},absent_paths=['.runtime/stage2/absent.json'],preserved_result_files={})

    def namespace(self,operation):
        program=launch._program(self.bindings,operation)
        ns={};exec(compile(program.split('\ntry:\n value=main()')[0],'<synthetic-report-bootstrap>','exec'),ns)
        return ns

    def installed(self):
        self.reporting.mkdir(mode=0o700);(self.reporting/'stage2').mkdir(mode=0o700)
        for name,raw in self.payload.items():
            p=self.reporting/name;p.write_bytes(raw);p.chmod(0o600)

    def main(self,ns):
        # Context and root ownership are simulated; byte, link, directory and
        # hash guards still use actual temporary files. This is not Linux proof.
        uid=os.getuid();real_read=ns['read'];real_inventory=ns['inventory']
        def owned(function):
            def call(*args,**kwargs):
                with patch.object(os,'getuid',return_value=uid):return function(*args,**kwargs)
            return call
        ns['read']=owned(real_read);ns['inventory']=owned(real_inventory)
        fake=NS(platform='linux',flags=NS(isolated=True),dont_write_bytecode=True,
            prefix=str(self.root/'.venv'),path=list(sys.path),modules=dict(sys.modules),pycache_prefix=None)
        collector=NS(__file__=str(self.reporting/'stage2/no_cutoff_final_report.py'),collect=Mock(return_value=self.snapshot))
        validator=NS(__file__=str(self.reporting/'stage2/no_cutoff_final_archive.py'),validate_snapshot=Mock())
        self.producer=NS(__file__=str(self.reporting/'stage2/no_cutoff_final_backup.py'),stream=Mock())
        fake.modules.update(no_cutoff_final_report=collector,no_cutoff_final_archive=validator,no_cutoff_final_backup=self.producer)
        ns['sys']=fake
        with patch.object(os,'getuid',return_value=0),patch.dict(os.environ,report.ENVIRONMENT,clear=True),\
                patch.dict(sys.modules,{'no_cutoff_final_report':collector,'no_cutoff_final_archive':validator,'no_cutoff_final_backup':self.producer}),\
                patch.object(launch.os,'chdir'):
            # This tiny fixture has no historical anchors. Real operator
            # bindings always derive them from the exact pinned originals.
            ns['c']['anchor_files']={}
            value=ns['main']()
        return value,collector,validator

    def test_exclusive_deployment_writes_only_reporting_bundle(self):
        before=(self.root/'stage2/frozen.py').read_bytes()
        value,_,_=self.main(self.namespace('deploy'))
        self.assertFalse(value['completed_final_audit']);self.assertFalse(value['paid_launch_ready'])
        self.assertEqual((self.root/'stage2/frozen.py').read_bytes(),before)
        self.assertEqual({p.relative_to(self.reporting).as_posix() for p in self.reporting.rglob('*.py')},set(self.payload))
        for name,raw in self.payload.items():self.assertEqual((self.reporting/name).read_bytes(),raw)

    def test_deploy_refuses_existing_complete_or_partial_directory(self):
        self.reporting.mkdir(mode=0o700)
        with self.assertRaises(ValueError):self.main(self.namespace('deploy'))
        self.assertEqual(list(self.reporting.iterdir()),[])

    def test_partial_deployment_is_retained_and_not_automatically_retried(self):
        ns=self.namespace('deploy');name=list(self.sources)[-1];ns['c']['payload'][name]='AAAA'
        with self.assertRaises(ValueError):self.main(ns)
        first=next(iter(self.sources));self.assertTrue((self.reporting/first).is_file())
        self.assertFalse((self.reporting/name).exists())
        with self.assertRaises(ValueError):self.main(self.namespace('deploy'))
        self.assertTrue((self.reporting/first).is_file())

    def test_deployment_payload_contains_only_separate_source_files(self):
        ns=self.namespace('deploy')
        self.assertEqual(set(ns['c']['payload']),set(self.sources))
        self.assertFalse(any(name.startswith('.runtime') for name in ns['c']['payload']))
        self.assertNotIn('payload',self.namespace('collect')['c'])

    def test_active_service_refuses_before_any_reporting_write(self):
        self.service.return_value='LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=748079\nExecMainStatus=0\n'
        with self.assertRaises(ValueError):self.main(self.namespace('deploy'))
        self.assertFalse(self.reporting.exists())

    def test_failed_unknown_and_duplicate_service_states_refused(self):
        for text in ('','ActiveState=failed\n','ActiveState=inactive\nActiveState=inactive\n'):
            self.service.return_value=text
            with self.subTest(text=text),self.assertRaises(ValueError):self.namespace('deploy')['check'](False)

    def test_operator_provider_and_symlink_stop_refused(self):
        for name in ('operator-stop-request.json','provider-stop.json'):
            p=self.root/'.runtime/stage2'/name;p.write_bytes(b'{}')
            with self.assertRaises(ValueError):self.namespace('deploy')['check'](False)
            p.unlink()
        (self.root/'.runtime/stage2/provider-stop.json').symlink_to(self.root/'missing')
        with self.assertRaises(ValueError):self.namespace('deploy')['check'](False)

    def test_native_source_drift_refuses_before_deployment(self):
        (self.root/'stage2/frozen.py').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.main(self.namespace('deploy'))
        self.assertFalse(self.reporting.exists())

    def test_separate_reporting_directory_cannot_be_nested_in_execution(self):
        self.enterContext(patch.object(report,'REPORTING',self.root/'reporting'))
        with self.assertRaises(ValueError):self.main(self.namespace('deploy'))

    def test_inspection_is_read_only_and_does_not_import_collector(self):
        self.installed();value,collector,validator=self.main(self.namespace('inspect'))
        collector.collect.assert_not_called();validator.validate_snapshot.assert_not_called()
        self.assertEqual(value['operation'],'inspect');self.assertFalse(value['paid_launch_ready'])

    def test_reporting_extra_file_missing_file_cache_or_permissions_refused(self):
        self.installed();p=self.reporting/'extra';p.write_bytes(b'x')
        with self.assertRaises(ValueError):self.namespace('inspect')['check']()
        p.unlink();p=self.reporting/'stage2/no_cutoff_final_report.py';p.chmod(0o644)
        with self.assertRaises(ValueError):self.namespace('inspect')['check']()
        p.chmod(0o600);p.unlink()
        with self.assertRaises(ValueError):self.namespace('inspect')['check']()

    def test_reporting_symlink_and_hardlink_refused(self):
        self.installed();p=self.reporting/'stage2/no_cutoff_final_report.py';os.link(p,self.base/'hard')
        with self.assertRaises(ValueError):self.namespace('inspect')['check']()
        p.unlink();p.symlink_to(self.base/'hard')
        with self.assertRaises(ValueError):self.namespace('inspect')['check']()

    def test_existing_bytecode_prefix_refuses_even_before_deployment(self):
        self.reporting.mkdir(mode=0o700);(self.reporting/'.absent-bytecode-cache').mkdir()
        with self.assertRaises(ValueError):self.namespace('deploy')['check'](False)

    def test_real_fifo_in_native_binding_is_refused_without_waiting(self):
        p=self.root/'stage2/frozen.py';p.unlink();os.mkfifo(p,0o600)
        with self.assertRaises(ValueError):self.namespace('deploy')['check'](False)

    def test_collect_calls_actual_entry_and_validator_in_order(self):
        self.installed();value,collector,validator=self.main(self.namespace('collect'))
        collector.collect.assert_called_once_with();validator.validate_snapshot.assert_called_once_with(self.snapshot,{})
        self.assertIs(value,self.snapshot);self.assertGreaterEqual(self.service.call_count,4)

    def test_binary_backup_enters_fixed_producer_not_a_saved_audit(self):
        self.installed();value,collector,validator=self.main(self.namespace('backup'))
        self.assertIsNone(value);self.producer.stream.assert_called_once_with()
        collector.collect.assert_not_called();validator.validate_snapshot.assert_not_called()

    def test_retained_backup_states_are_inspectable_but_not_sources(self):
        self.installed();p=self.reporting/'.backup-intent.json';p.write_bytes(b'{}');p.chmod(0o600)
        value,collector,_=self.main(self.namespace('inspect'))
        self.assertEqual(value['operation'],'inspect');collector.collect.assert_not_called()
        p.chmod(0o644)
        with self.assertRaises(ValueError):self.namespace('inspect')['check']()

    def test_backup_bootstrap_never_appends_a_json_reply_to_binary_stream(self):
        program=launch._program(self.bindings,'backup')
        tail='try:\n value=main()'+program.split('\ntry:\n value=main()')[1]
        output=io.StringIO()
        with patch.object(sys,'stdout',output):
            exec(tail,dict(main=lambda:None,c={'operation':'backup'},sys=sys,json=json))
        self.assertEqual(output.getvalue(),'')

    def test_post_audit_absence_inventory_and_source_mutations_refused(self):
        self.installed();p=self.root/'.runtime/stage2/absent.json';p.write_bytes(b'{}')
        with self.assertRaises(ValueError):self.main(self.namespace('collect'))
        p.unlink();self.snapshot['directory_entries']={'.runtime/stage2':['not-present.json']}
        with self.assertRaises(ValueError):self.main(self.namespace('collect'))

    def test_evidence_is_reread_after_last_native_service_observation(self):
        self.installed();p=self.root/'.runtime/stage2/result.json';p.write_bytes(b'bound');p.chmod(0o600)
        self.snapshot['supporting_file_sha256']={**self.native,'.runtime/stage2/result.json':hashlib.sha256(b'bound').hexdigest()}
        output=self.service.return_value;calls=0
        def observed(*args,**kwargs):
            nonlocal calls
            calls+=1
            if calls==4:p.write_bytes(b'changed')
            return output
        self.service.side_effect=observed
        with self.assertRaises(ValueError):self.main(self.namespace('collect'))
        self.assertEqual(calls,4)

    def test_loaded_wrong_deployment_or_unbound_project_module_refused(self):
        self.installed();ns=self.namespace('inspect');fake=NS(modules={'wrong':NS(__file__=str(self.base/'no_cutoff_final_report.py'))})
        ns['sys']=fake
        with self.assertRaises(ValueError):ns['loaded']()
        fake.modules={'unbound':NS(__file__=str(self.root/'stage2/unbound.py'))}
        with self.assertRaises(ValueError):ns['loaded']()

    def test_bootstrap_catches_failures_without_raw_exception_text(self):
        program=launch._program(self.bindings,'inspect')
        stream=io.StringIO()
        with patch.object(sys,'stderr',stream),self.assertRaises(SystemExit):exec(compile(program,'<real-context-refusal>','exec'),{})
        value=json.loads(stream.getvalue());self.assertFalse(value['paid_launch_ready']);self.assertFalse(value['automatic_resume'])
        self.assertNotIn('Traceback',stream.getvalue())


class ActualLocalBindingTests(unittest.TestCase):
    def test_actual_synthetic_anchor_copies_and_all_reporting_files_are_read(self):
        ssh=(Path(__file__).parent/'progress_dashboard.py').read_bytes()
        self.enterContext(patch.dict(phase.FROZEN_HELPERS,{'progress_dashboard.py':hashlib.sha256(ssh).hexdigest()}))
        f=fixtures.ArchiveTests();f.setUp();self.addCleanup(f.doCleanups)
        root=f.root;files={phase.RT+n for n in report.INPUTS if n!='python-runtime.tar.gz'}|set(f.f.f.proof['evidence_files'])
        for name in files:
            target=root/launch.COPIES/('no-cutoff-final-matrix.json' if name.endswith('/no-cutoff-final-matrix.json') else name)
            target.parent.mkdir(parents=True,exist_ok=True,mode=0o700);target.write_bytes((root/name).read_bytes());target.chmod(0o600)
        for name in report.REPORTING_FILES:
            p=root/'stage2'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((Path(__file__).parent/name).read_bytes())
        (root/'stage2/progress_dashboard.py').write_bytes(ssh)
        with patch.object(launch,'REPO',root),patch.object(launch,'_operator'):
            value=launch._bindings()
            self.assertEqual(len(value['reporting']),len(report.REPORTING_FILES));self.assertEqual(len(value['anchors']),5)
            self.assertEqual(value['native']['stage2/local_trace.py'],phase.FROZEN_HELPERS['local_trace.py'])
            target=root/launch.COPIES/'no-cutoff-final-matrix.json';target.write_bytes(target.read_bytes()+b' ')
            with self.assertRaises(ValueError):launch._bindings()


if __name__=='__main__':unittest.main()

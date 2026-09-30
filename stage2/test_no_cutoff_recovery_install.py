"""Real exclusive local copies/locks; native manager and interpreter mocked."""
import base64
import fcntl
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import no_cutoff_recovery_install as install
import no_cutoff_recovery_files as files
import no_cutoff_recovery_policy as policy
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save


class InstallTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.protect(Path(temp.name).resolve())
        self.base=self.root; self.old=self.base/'old'; self.target=self.base/'new'; self.reporter=self.base/'reporter'
        self.old.mkdir(mode=0o700); self.reporter.mkdir(mode=0o700)
        for name in ('ROOT','ORIGINAL','REPORTER'):
            self.enterContext(patch.object(install,name,{'ROOT':self.target,'ORIGINAL':self.old,'REPORTER':self.reporter}[name]))
        self.enterContext(patch.object(files.libraries,'ORIGINAL',self.old))
        self.enterContext(patch.object(install,'EARLY',('old',))); self.enterContext(patch.object(install,'LATE',()))
        self.enterContext(patch.object(install,'_context'))
        self.enterContext(patch.object(install,'_interpreter',return_value=('local-synthetic-executable','a'*64,())))
        self.quiet=self.enterContext(patch.object(install,'_quiet'))
        self.qual=b'{"local_synthetic_original":true}'
        sha=install._sha(self.qual); self.enterContext(patch.object(install,'QUALIFICATION_SHA',sha))
        save(self.old,install.ORIGINAL_QUALIFICATION,self.qual)
        for name in ('matrix.lock','scored.lock','gateway.lock'): save(self.old,'.runtime/stage2/'+name,b'')
        save(self.old,'stage2/original.py',b'original unchanged source\n')
        save(self.reporter,'stage2/reporter.py',b'archived unchanged source\n')
        save(self.old,'.venv/lib/python3.12/site-packages/example.py',b'installed-library-bytes\n')
        save(self.old,'.venv/bin/python',b'synthetic-not-an-interpreter\n')
        save(self.old,'.cache/tasks/one/task.toml',b'harmless synthetic config\n')
        save(self.old,'.cache/stage2-tokenizer/cache',b'current-tokenizer-bytes\n')
        save(self.old,'.runtime/stage2/python-runtime.tar.gz',b'synthetic-not-real-archive\n')
        save(self.old,'.env',b'OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
        provenance=dict(dataset_path='.cache/tasks',canonical={'file_hashes':[dict(path='one/task.toml',
            sha256=files.libraries.read(self.old,'.cache/tasks/one/task.toml'))]})
        self.decoded={'stage2/current.py':b'new source\n','stage2/dataset_provenance.json':json.dumps(provenance).encode()}
        self.final={'python_runtime':{'sha256':files.libraries.read(self.old,'.runtime/stage2/python-runtime.tar.gz')}}
        self.value=dict(commit='a'*40,hashes={n:install._sha(v) for n,v in self.decoded.items()},
            native={install.ORIGINAL_QUALIFICATION:sha,'stage2/original.py':files.libraries.read(self.old,'stage2/original.py')},
            reporter={'stage2/reporter.py':files.libraries.read(self.reporter,'stage2/reporter.py')})
        self.enterContext(patch.object(install,'_payload',return_value=(self.decoded,self.final,
            files.bootstrap,files.libraries,SimpleNamespace())))

    def test_actual_exclusive_copy_rereads_precreates_locks_and_never_reuses_target(self):
        original={p.relative_to(self.old).as_posix():p.read_bytes() for p in self.old.rglob('*') if p.is_file()}
        result=install._install(self.value)
        self.assertFalse(result['paid_launch_ready']); self.assertFalse(result['recovery_execution_qualified'])
        self.assertEqual(result['precreated_locks'],3)
        self.assertEqual((self.target/'.env').read_bytes(),original['.env'])
        self.assertTrue((self.target/'installation-result.json').is_file())
        self.assertFalse((self.target/'installation-failure.json').exists())
        for name,raw in original.items(): self.assertEqual((self.old/name).read_bytes(),raw)
        self.assertEqual(self.target.stat().st_mode&0o777,0o700)
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertEqual(json.loads((self.target/'installation-result.json').read_bytes()),result)

    def test_existing_partial_root_refuses_before_copy(self):
        self.target.mkdir(mode=0o700); save(self.target,'partial.json',b'{}')
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertEqual({p.name for p in self.target.iterdir()},{'partial.json'})

    def test_same_byte_source_replacement_during_copy_retains_failed_root(self):
        original=install._copy; changed=False
        def copy(name,*args):
            nonlocal changed
            answer=original(name,*args)
            if not changed:
                path=self.old/'stage2/original.py'; raw=path.read_bytes()
                path.rename(path.with_suffix('.retained')); save(self.old,'stage2/original.py',raw); changed=True
            return answer
        with patch.object(install,'_copy',side_effect=copy),self.assertRaises(ValueError): install._install(self.value)
        self.assertTrue((self.target/'installation-failure.json').is_file())
        self.assertFalse((self.target/'installation-result.json').exists())

    def test_unexpected_target_file_refuses_completion_and_does_not_delete_it(self):
        original=install._copy; changed=False
        def copy(name,*args):
            nonlocal changed
            answer=original(name,*args)
            if not changed: save(self.target,'unexpected.json',b'{}'); changed=True
            return answer
        with patch.object(install,'_copy',side_effect=copy),self.assertRaises(ValueError): install._install(self.value)
        self.assertTrue((self.target/'unexpected.json').is_file())
        self.assertTrue((self.target/'installation-failure.json').is_file())

    def test_held_ancestor_lock_does_not_create_root(self):
        import fcntl
        with (self.old/'.runtime/stage2/matrix.lock').open('rb') as stream:
            fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): install._install(self.value)
        self.assertFalse(self.target.exists())

    def test_symlinked_runtime_input_is_refused_before_any_root_write(self):
        path=self.old/'.cache/stage2-tokenizer/cache'; path.rename(path.with_suffix('.retained'))
        path.symlink_to('cache.retained')
        with self.assertRaises(ValueError): install._install(self.value)
        self.assertFalse(self.target.exists())

    def lock_file(self):
        path=self.old/'.venv/.lock'; save(self.old,'.venv/.lock',b''); path.chmod(0o666)
        return path

    def test_observed_empty_installer_lock_copied_private_original_unchanged(self):
        path=self.lock_file(); before=files.libraries.identity(path.lstat())
        install._install(self.value)
        copied=self.target/'.venv/.lock'
        self.assertEqual(copied.read_bytes(),b''); self.assertEqual(copied.stat().st_mode&0o777,0o600)
        self.assertEqual(files.libraries.identity(path.lstat()),before)
        self.assertEqual(path.stat().st_mode&0o777,0o666)

    def test_installer_lock_exception_does_not_include_payload_or_other_paths(self):
        for name,raw in (('.venv/.lock',b'not empty'),('.venv/other-lock',b''),
                ('.venv/lib/python3.12/site-packages/unsafe.py',b'')):
            with self.subTest(name=name):
                save(self.old,name,raw); path=self.old/name; path.chmod(0o666)
                try:
                    with self.assertRaises(ValueError): install._install(self.value)
                    self.assertFalse(self.target.exists())
                finally: path.unlink()

    def test_held_empty_installer_lock_refuses_without_native_target(self):
        path=self.lock_file()
        with path.open('rb') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): install._install(self.value)
        self.assertFalse(self.target.exists())

    def test_installer_lock_symlink_hardlink_acl_and_unobserved_modes_refuse(self):
        path=self.lock_file()
        for mode in (0o600,0o664,0o777,0o4666):
            path.chmod(mode)
            with self.assertRaises(ValueError): install._input_read(self.old,'.venv/.lock',files.libraries)
        path.chmod(0o666)
        alias=path.with_name('.lock-alias'); os.link(path,alias)
        with self.assertRaises(ValueError): install._input_read(self.old,'.venv/.lock',files.libraries)
        alias.unlink()
        with patch.object(files.libraries.os,'listxattr',return_value=['system.posix_acl_access']):
            with self.assertRaises(ValueError): install._input_read(self.old,'.venv/.lock',files.libraries)
        path.rename(alias); path.symlink_to(alias.name)
        with self.assertRaises((ValueError,OSError)): install._input_read(self.old,'.venv/.lock',files.libraries)

    def test_installer_lock_same_byte_identity_replacement_refuses(self):
        path=self.lock_file(); original=hashlib.file_digest
        def replace(stream,*args):
            answer=original(stream,*args)
            path.rename(path.with_name('.retained-lock')); self.lock_file()
            return answer
        with patch.object(hashlib,'file_digest',side_effect=replace):
            with self.assertRaises(ValueError): install._input_read(self.old,'.venv/.lock',files.libraries)

    def test_installer_lock_change_after_inventory_preserves_partial_target(self):
        path=self.lock_file(); original=install._copy; changed=False
        def copy(name,*args):
            nonlocal changed
            answer=original(name,*args)
            if not changed: path.write_bytes(b'changed'); changed=True
            return answer
        with patch.object(install,'_copy',side_effect=copy),self.assertRaises(ValueError): install._install(self.value)
        self.assertTrue((self.target/'installation-failure.json').is_file())
        self.assertFalse((self.target/'installation-result.json').exists())


class FailedOperatorTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        import no_cutoff_recovery_predecessor as operator
        self.operator=operator
        temp=tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.protect(Path(temp.name).resolve())
        self.enterContext(patch.object(operator.launch,'REPO',self.root))
        self.folder=self.root/install.FAILED_STATE
        for name in ('intent.json','failure.json'): save(self.root,install.FAILED_STATE+'/'+name,b'{}')
        self.enterContext(patch.object(install,'FAILED_FILES',dict.fromkeys(('intent.json','failure.json'),install._sha(b'{}'))))

    def test_exact_failed_state_reread_detects_same_bytes_replacement(self):
        before=install._failed_installation(); path=self.folder/'intent.json'
        path.rename(path.with_suffix('.retained')); path.write_bytes(b'{}'); path.chmod(0o600)
        with self.assertRaises(ValueError): install._failed_installation()
        path.with_suffix('.retained').unlink()
        self.assertNotEqual(install._failed_installation(),before)

    def test_failed_state_wrong_bytes_permissions_and_extra_result_refuse(self):
        path=self.folder/'failure.json'; path.write_bytes(b'{ }')
        with self.assertRaises(ValueError): install._failed_installation()
        path.write_bytes(b'{}'); path.chmod(0o644)
        with self.assertRaises(ValueError): install._failed_installation()
        path.chmod(0o600); save(self.root,install.FAILED_STATE+'/result.json',b'{}')
        with self.assertRaises(ValueError): install._failed_installation()

    def test_second_operator_destination_is_distinct_and_failed_hashes_are_fixed(self):
        self.assertNotEqual(install.STATE,install.FAILED_STATE)
        self.assertTrue(install.STATE.endswith('20260930-r2'))

    def test_mac_acl_reader_observes_fixed_command_and_exact_environment(self):
        with patch.object(install.platform,'system',return_value='Darwin'),patch.object(install.subprocess,'run',
                return_value=SimpleNamespace(returncode=0,stdout=b'drwx------@ 4 owner group 128 Sep 30 10:13 path\n',stderr=b'')) as run:
            install._operator_acl(self.folder)
        self.assertEqual(run.call_args.args[0],['/bin/ls','-lde',str(self.folder)])
        self.assertEqual(run.call_args.kwargs['env'],{'PATH':'/usr/bin:/bin','LANG':'C','LC_ALL':'C'})

    def test_mac_acl_entries_failure_and_unexpected_output_refuse(self):
        for output,err,code in ((b'drwx------+ 4 owner group path\n 0: everyone allow read\n',b'',0),
                (b'drwx------+ 4 owner group path\n',b'',0),(b'',b'',0),(b'unknown\n',b'',0),
                (b'drwx------ 4 owner group path\n',b'warning',0),(b'drwx------ 4 owner group path\n',b'',1)):
            with patch.object(install.platform,'system',return_value='Darwin'),patch.object(install.subprocess,'run',
                    return_value=SimpleNamespace(returncode=code,stdout=output,stderr=err)):
                with self.assertRaises(ValueError): install._operator_acl(self.folder)

    def test_linux_operator_acl_keeps_actual_bootstrap_reader(self):
        with patch.object(install.platform,'system',return_value='Linux'),patch.object(files.bootstrap,'acl') as acl:
            install._operator_acl(self.folder)
        acl.assert_called_once_with(self.folder)


class PayloadTests(unittest.TestCase):
    def payload(self):
        root=Path(__file__).resolve().parent.parent
        old_names={'input_manifest.json','task_preparation.py','scored_trial.py','no_cutoff_final_guard.py'}
        final=dict(sources={n:install._sha((root/'stage2'/n).read_bytes()) for n in old_names},
            evidence_files={'.runtime/stage2/synthetic-native-producer.json':'c'*64})
        raw=json.dumps(final).encode(); sha=install._sha(raw)
        self.enterContext(patch.object(install,'QUALIFICATION_SHA',sha))
        names=set(final['sources'])|policy.REQUIRED_SOURCE_FILES
        hashes={n:hashlib.sha256((root/'stage2'/n).read_bytes()).hexdigest() for n in names}
        decoded={'stage2/'+n:(root/'stage2'/n).read_bytes() for n in names}
        decoded['stage2/no_cutoff_recovery_bootstrap.py']=decoded['stage2/no_cutoff_recovery_bootstrap.py'].replace(
            policy.ORIGINAL_QUALIFICATION_FILE_SHA256.encode(),sha.encode())
        prefix='stage2/results/custom-no-cutoff-final-20260928/'
        for name in ('qualification.json','registration-c0-nc.json','lineage.json','credit-policy.json',
                'c0-nc/summary.json','c0-nc/trials.json','c0-nc/trials.csv'):
            decoded[prefix+name]=b'{"synthetic":true}'
        decoded[install.QUALIFICATION]=raw; decoded[install.MANIFEST]=decoded['stage2/input_manifest.json']
        native={'stage2/'+n:h for n,h in final['sources'].items()}
        native.update(final['evidence_files']); native[install.ORIGINAL_QUALIFICATION]=install.QUALIFICATION_SHA
        value=dict(kind=install.KIND,commit='a'*40,files={n:base64.b64encode(v).decode() for n,v in decoded.items()},
            hashes={n:install._sha(v) for n,v in decoded.items()},native=native,
            reporter={'stage2/no_cutoff_final_guard.py':hashes['no_cutoff_final_guard.py']})
        return value

    def test_complete_current_original_union_and_raw_manifest_are_derived(self):
        value=self.payload(); decoded,final,*_=install._payload(value)
        self.assertEqual(decoded[install.MANIFEST],decoded['stage2/input_manifest.json'])
        self.assertEqual(len(final['sources']),4)  # Synthetic minimal original fixture, not historical evidence.
        for name in ('stage2/scored_trial.py','stage2/no_cutoff_recovery_install.py'):
            changed=deepcopy(value); changed['files'].pop(name); changed['hashes'].pop(name)
            with self.assertRaises(ValueError): install._payload(changed)

    def test_missing_original_producer_or_source_cannot_use_caller_incomplete_list(self):
        value=self.payload()
        for name in ('stage2/task_preparation.py',next(n for n in value['native'] if n.startswith('.runtime/')
                and n!=install.ORIGINAL_QUALIFICATION)):
            changed=deepcopy(value); changed['native'].pop(name)
            with self.assertRaises(ValueError): install._payload(changed)

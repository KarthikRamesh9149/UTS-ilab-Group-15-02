"""Real exclusive local copies/locks; native manager and interpreter mocked."""
import base64
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

"""Synthetic retained archives and fixed child dispatch; no native invocation."""
import ast
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace as NS

import matched_repeat_recovery_operator as operator
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_reporting import ReportingTests
from test_no_cutoff_recovery_runtime import save
from test_no_cutoff_recovery_mac_reporting import failed_fixture


class RecoveryOperatorTests(LocalFiles,unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        factory=tempfile.TemporaryDirectory
        with patch.object(tempfile,'TemporaryDirectory',side_effect=lambda:factory(
                prefix='.uts-recovery-reader-',dir=Path.home())):
            ReportingTests.setUp(self)
        if sys.platform != 'darwin':
            # Native Linux receiver tests need synthetic Mac-side evidence.
            # Only that OS boundary is emulated here; the separate real Mac
            # suite exercises actual ls/ACL/ancestry and Linux refusal.
            self.enterContext(patch.object(operator.mac,'_darwin'))
            self.enterContext(patch.object(operator.mac,'_acl',side_effect=operator.recovery.boot.acl))
    produce=ReportingTests.produce
    collect=ReportingTests.collect
    packed=ReportingTests.packed

    async def retained(self):
        await self.produce(); data,_=self.collect(); path,inventory,_,receipt=self.packed(data)
        recovery=operator.recovery
        verified=recovery.archive.verify(path,data,inventory,receipt,self.f.manifest,self.sources)
        backup=dict(kind='verified_off_server_recovery_backup',receipt=receipt,verified=verified,
            snapshot_sha256=recovery.policy.fingerprint(data),inventory_sha256=recovery.policy.fingerprint(inventory),
            automatic_resume=False,paid_launch_ready=False)
        intent=dict(kind='one_shot_off_server_recovery_backup',commit='a'*40,
            started_utc=data['collected_utc'],automatic_resume=False,paid_launch_ready=False)
        for name,value in (('intent.json',intent),('snapshot.json',data),('inventory.json',inventory),('backup.json',backup)):
            save(self.root,operator.BACKUP+'/'+name,json.dumps(value).encode())
        save(self.root,operator.BACKUP+'/evidence.tar.gz',path.read_bytes())
        failed_fixture(self.root)
        public=recovery.projection(data,backup); bound={}
        for name,raw in public.items():
            relative=recovery.PUBLIC+'/'+name;save(self.root,relative,raw);bound[relative]=hashlib.sha256(raw).hexdigest()
        for name,value in (('intent.json',dict(kind='one_shot_separate_recovery_export',commit='a'*40,
                started_utc=data['collected_utc'],automatic_resume=False)),
                ('result.json',dict(kind='separate_recovery_allowlisted_export_complete',files=bound,
                snapshot_sha256=recovery.policy.fingerprint(data),archive_sha256=receipt['sha256'],
                automatic_resume=False,paid_launch_ready=False))):
            save(self.root,recovery.EXPORT+'/'+name,json.dumps(value).encode())
        self.enterContext(patch.object(operator,'REPO',self.root))
        self.enterContext(patch.object(recovery.handoff.launch,'REPO',self.root))
        self.enterContext(patch.object(recovery,'_manifest',return_value=self.f.manifest))
        self.enterContext(patch.object(operator.mac_recovery,'_manifest',return_value=self.f.manifest))
        self.enterContext(patch.object(operator.original.launch,'_git',side_effect=lambda action,ref:
            (self.root/ref.split(':',1)[1]).read_bytes()))
        return data,backup

    async def test_real_retained_reader_rereads_same_archive_and_committed_public_bytes(self):
        data,backup=await self.retained()
        actual=operator._retained({'commit':'a'*40},self.sources)
        self.assertEqual(actual['data'],data);self.assertEqual(actual['backup'],backup)
        self.assertEqual(len(actual['records']),13)
        self.assertEqual(operator._retained({'commit':'a'*40},self.sources),actual)

    async def test_archive_corruption_and_partial_export_refuse_without_replacement(self):
        await self.retained();recovery=operator.recovery
        path=self.root/operator.BACKUP/'evidence.tar.gz';original=path.read_bytes()
        path.write_bytes(original[:-1])
        with self.assertRaises((ValueError,OSError)):operator._retained({'commit':'a'*40},self.sources)
        path.write_bytes(original)
        save(self.root,recovery.EXPORT+'/failure.json',b'{}')
        with self.assertRaises(ValueError):operator._retained({'commit':'a'*40},self.sources)
        self.assertEqual(path.read_bytes(),original)

    async def test_publication_identity_and_nulls_are_preserved(self):
        data,_=await self.retained();before=operator._retained({'commit':'a'*40},self.sources)
        name=operator.recovery.PUBLIC+'/trials.json';path=self.root/name;raw=path.read_bytes()
        path.rename(path.with_suffix('.retained'));save(self.root,name,raw)
        after=operator._retained({'commit':'a'*40},self.sources)
        self.assertNotEqual(before,after);self.assertIsNone(data['rows'][2]['reward'])
        with patch.object(operator.original.launch,'_git',return_value=b'not committed public bytes'):
            with self.assertRaises(ValueError):operator._retained({'commit':'a'*40},self.sources)


class RecoveryChildDispatchTests(unittest.TestCase):
    def test_generated_child_has_actual_fixed_audit_and_credential_free_preimport_guards(self):
        code=operator._program('a'*40,{'stage2/example.py':'b'*64},{'example.py':'b'*64})
        ast.parse(code)
        self.assertIn("reporting._capture(commit,'audit')",code)
        self.assertIn("reporting._current(captured,captured_ids)",code)
        self.assertLess(code.index('before=current()'),code.index('import no_cutoff_recovery_mac_reporting'))
        self.assertNotIn('CALLBACK',code);self.assertNotIn('OPENROUTER_API_KEY',operator._environment())
        self.assertEqual(operator._environment()['PYTHON_DOTENV_DISABLED'],'1')
        self.assertIn("reporting.bridge._loaded({'bound':mac_bound})",code)
        self.assertNotIn('import no_cutoff_recovery_reporting as reporting', code)

    def fixture(self):
        bound={'commit':'a'*40,'local':{'stage2/example.py':'b'*64}}
        fresh={'collected_utc':'2026-09-30T00:00:00Z','measured':1.0,'unknown':None}
        retained=dict(data=deepcopy(fresh),backup={'receipt':{'sha256':'c'*64}},
            records={'snapshot.json':(json.dumps(fresh).encode(),())})
        self.enterContext(patch.object(operator.original,'_prepare',return_value=(bound,{})))
        self.enterContext(patch.object(operator,'_sources',return_value={'example.py':'b'*64}))
        self.enterContext(patch.object(operator,'_retained',return_value=retained))
        current=self.enterContext(patch.object(operator,'_current'))
        self.enterContext(patch.object(operator.recovery,'_manifest',return_value={}))
        self.enterContext(patch.object(operator.recovery.report,'validate'))
        return fresh,current

    def test_public_entry_really_invokes_only_the_fixed_isolated_child_every_time(self):
        fresh,current=self.fixture()
        with patch.object(operator.subprocess,'run',return_value=NS(returncode=0,stdout=json.dumps(fresh).encode())) as run:
            _,result=operator.capture('a'*40)
        args,kw=run.call_args
        self.assertEqual(args[0][:4],[str(operator.PYTHON),'-I','-B','-c'])
        self.assertIn("reporting._capture(commit,'audit')",args[0][-1])
        self.assertEqual(kw['cwd'],operator.REPO);self.assertEqual(kw['env'],operator._environment())
        self.assertEqual(kw['stdin'],subprocess.DEVNULL);self.assertEqual(kw['stderr'],subprocess.DEVNULL)
        self.assertEqual(current.call_count,2);self.assertFalse(result['paid_launch_ready'])
        self.assertIs(type(result['fresh_audit']['measured']),float);self.assertIsNone(result['fresh_audit']['unknown'])

    def test_failed_child_changed_audit_and_late_source_change_never_return_capture(self):
        fresh,current=self.fixture()
        for mode in ('failed','mismatch','stale','source'):
            changed=deepcopy(fresh)
            if mode=='mismatch':changed['measured']=2.0
            if mode=='stale':changed['collected_utc']='2026-09-29T00:00:00Z'
            current.side_effect=[None,ValueError('changed')] if mode=='source' else None
            with self.subTest(mode=mode),patch.object(operator.subprocess,'run',return_value=NS(
                    returncode=1 if mode=='failed' else 0,stdout=json.dumps(changed).encode())):
                with self.assertRaises(ValueError):operator.capture('a'*40)


class RecoveryChildProgramTests(unittest.TestCase):
    def execute(self,prefix='',*,drift=False):
        # The real isolated child reads a tiny bound synthetic source. Git's
        # returned committed bytes are mocked; no native Git dependency or
        # actual recovery collector/provider call is introduced by this test.
        with tempfile.TemporaryDirectory(prefix='.uts-baseline-reader-test-',dir=Path.home()) as folder:
            root=Path(folder).resolve();(root/'stage2').mkdir(mode=0o700);(root/'.runtime').mkdir(mode=0o700)
            source=(prefix+"\nfrom types import SimpleNamespace as N\n"
                "bridge=N(EXTRAS=(),_loaded=lambda value:None)\n"
                "def _capture(commit,mode):\n"
                " assert mode=='audit'\n"
                " return dict(synthetic_child_only=True,measured=1.0,unknown=None),{},{}\n"
                "def _current(value,identities):pass\n").encode()
            save(root,'stage2/no_cutoff_recovery_mac_reporting.py',source)
            commit='a'*40
            bound={'stage2/no_cutoff_recovery_mac_reporting.py':hashlib.sha256(source).hexdigest()}
            if drift:save(root,'stage2/no_cutoff_recovery_mac_reporting.py',source+b'\n# drift\n')
            with patch.object(operator,'REPO',root),patch.object(operator,'PYTHON',Path(sys.executable).absolute()),\
                    patch.object(operator,'CACHE',root/'.runtime/absent-cache'):
                code=operator._program(commit,bound,{'no_cutoff_recovery_mac_reporting.py':bound[next(iter(bound))]})
                git_fixture=("import subprocess\n"
                    "def synthetic_git(argv,**kwargs):\n"
                    " if argv==['git','show',"+repr(commit+':stage2/no_cutoff_recovery_mac_reporting.py')+"]:return "+repr(source)+"\n"
                    " if argv in (['git','rev-parse','HEAD'],['git','rev-parse','origin/main']):return "+repr((commit+'\n').encode())+"\n"
                    " raise AssertionError('Unexpected synthetic Git command')\n"
                    "subprocess.check_output=synthetic_git\n")
                code=git_fixture+code
                result=subprocess.run([sys.executable,'-I','-B','-c',code],cwd=root,env=operator._environment(),
                    stdin=subprocess.DEVNULL,capture_output=True,timeout=20)
            self.assertFalse((root/'must-not-exist').exists())
            return result

    def test_real_isolated_child_reads_bound_source_with_mocked_git_and_preserves_types(self):
        result=self.execute();self.assertEqual(result.returncode,0,result.stderr)
        value=json.loads(result.stdout);self.assertTrue(value['synthetic_child_only'])
        self.assertIs(type(value['measured']),float);self.assertIsNone(value['unknown'])

    def test_real_child_refuses_drift_before_import_and_latches_caught_import_write(self):
        result=self.execute(drift=True);self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)
        result=self.execute("try:open('must-not-exist','w')\nexcept RuntimeError:pass\n")
        self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

    def test_caught_socket_probe_constructs_nothing_but_credentials_always_refuse(self):
        result=self.execute("import socket\ntry:socket.socket()\nexcept RuntimeError:pass\nelse:raise AssertionError('created socket')\n")
        self.assertEqual(result.returncode,0,result.stderr)
        result=self.execute("try:open('.env')\nexcept RuntimeError:pass\n")
        self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

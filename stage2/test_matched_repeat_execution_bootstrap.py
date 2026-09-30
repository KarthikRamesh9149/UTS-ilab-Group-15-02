"""Real protected local bytes and isolated effect guard; native facts mocked."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import matched_repeat_execution_bootstrap as boot
import no_cutoff_recovery_files as files
from test_no_cutoff_recovery_execution import LocalFiles
from test_no_cutoff_recovery_runtime import save

STAGE = Path(__file__).resolve().parent


class BootstrapFilesTests(LocalFiles, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.protect(Path(temporary.name).resolve())
        self.enterContext(patch.dict(boot.ROOTS, {'terminus-2':self.root}))
        self.enterContext(patch.object(boot, 'context', return_value=self.root))
        self.enterContext(patch.object(boot, 'directories', side_effect=files.bootstrap.directories))
        policy = b"REQUIRED_SOURCE_FILES = frozenset({'extra.py'})\n"
        self.bound = {}
        for name,raw in {'fixture.py':b'# actual synthetic source\n', 'matched_repeat_policy.py':policy,
                'extra.py':b'# extra independently bound source\n'}.items():
            save(self.root, 'stage2/'+name, raw); self.bound['stage2/'+name] = hashlib.sha256(raw).hexdigest()
        final = json.dumps({'sources':{n.removeprefix('stage2/'):h for n,h in self.bound.items()
            if n != 'stage2/extra.py'}}).encode()
        for name,raw,key in ((boot.BASELINE_INPUT,b'{"synthetic_original":true}','BASELINE_SHA'),
                (boot.FINAL_INPUT,final,'FINAL_SHA')):
            save(self.root,name,raw); digest=hashlib.sha256(raw).hexdigest();self.bound[name]=digest
            self.enterContext(patch.object(boot,key,digest))

    def test_full_inventory_is_derived_from_real_private_anchor_and_bound_policy_ast(self):
        observed = boot.check('terminus-2',self.bound)
        self.assertEqual(set(observed),set(self.bound)); boot.check('terminus-2',self.bound,observed)
        shortened = dict(self.bound); shortened.pop('stage2/extra.py')
        with self.assertRaisesRegex(ValueError,'Incomplete'): boot.check('terminus-2',shortened)

    def test_same_byte_file_replacement_and_raw_private_drift_refuse(self):
        observed=boot.check('terminus-2',self.bound); path=self.root/'stage2/fixture.py';raw=path.read_bytes()
        path.rename(path.with_suffix('.old'));save(self.root,'stage2/fixture.py',raw)
        with self.assertRaisesRegex(ValueError,'replaced'): boot.check('terminus-2',self.bound,observed)
        path=self.root/boot.FINAL_INPUT;path.write_bytes(path.read_bytes()+b' ')
        with self.assertRaises(ValueError):boot.check('terminus-2',self.bound)

    def test_hardlinks_symlinks_private_modes_and_nonfinite_or_duplicate_json_refuse(self):
        path=self.root/boot.FINAL_INPUT;path.chmod(0o644)
        with self.assertRaises(ValueError):boot.check('terminus-2',self.bound)
        path.chmod(0o600);os.link(path,path.with_suffix('.link'))
        with self.assertRaises(ValueError):boot.check('terminus-2',self.bound)
        path.with_suffix('.link').unlink();path.rename(path.with_suffix('.retained'));path.symlink_to(path.with_suffix('.retained'))
        with self.assertRaises((ValueError,OSError)):boot.check('terminus-2',self.bound)
        for value in (b'{"x":1,"x":2}',b'{"x":NaN}'):
            with self.assertRaises(ValueError):boot.loads(value)

    def test_required_inventory_expression_is_not_executed(self):
        for value in (b"REQUIRED_SOURCE_FILES = frozenset(__import__('os').listdir())",b"REQUIRED_SOURCE_FILES = set()",
                b"REQUIRED_SOURCE_FILES = frozenset({'a'}, unexpected=True)"):
            with self.assertRaises(ValueError):boot._required(value)


class BootstrapContextTests(unittest.TestCase):
    def test_protected_stdlib_readers_are_ast_identical_to_reviewed_recovery_helpers(self):
        select=lambda name:{n.name:ast.dump(n) for n in ast.parse((STAGE/name).read_bytes()).body
            if isinstance(n,ast.FunctionDef) and n.name in {'identity','acl','directories','raw','loads'}}
        self.assertEqual(select('matched_repeat_execution_bootstrap.py'),select('no_cutoff_recovery_bootstrap.py'))

    def test_exact_harnesses_and_credential_free_own_tokenizer_environment_only(self):
        for harness in ('terminus-2','openhands'):
            env=boot.environment(harness)
            self.assertTrue(env['TIKTOKEN_CACHE_DIR'].startswith(str(boot.ROOTS[harness])+'/'))
            self.assertEqual(env['PYTHON_DOTENV_DISABLED'],'1')
            self.assertFalse(any('KEY' in name or 'TOKEN' in name and name!='TIKTOKEN_CACHE_DIR' for name in env))
        for harness in ('C0-NC','/arbitrary/root',None):
            with self.assertRaises(ValueError):boot.root_for(harness)
        with patch.object(boot.platform,'system',return_value='Darwin'),self.assertRaises(ValueError):
            boot.context('terminus-2')

    def status(self):
        return dict(kind='read_only_recovery_operation_status_not_admission',operation='run-recovery',
            status='service_exited_successfully_not_completed_study_audit',paid_launch_ready=False,automatic_resume=False,
            counts=dict(study='custom-no-cutoff-recovery-20260929',intended=3,started=3,completed=3,
                passed=0,failed=0,missing_verifier=3,active_tasks=[]))

    def test_recovery_preflight_invokes_fixed_real_reader_then_rereads_sources_without_score_floor(self):
        bindings={'stage2/no_cutoff_recovery_bootstrap.py':hashlib.sha256(b'# fixture').hexdigest()}
        with patch.object(boot,'_recovery_files',return_value=bindings) as reread,patch.object(boot,'raw',return_value=(b'# fixture',())),\
                patch.object(boot.subprocess,'run',return_value=NS(returncode=0,stdout=json.dumps(self.status()).encode())) as run:
            self.assertEqual(boot.recovery_finished(),self.status());self.assertEqual(reread.call_count,2)
            args,kw=run.call_args;self.assertEqual(args[0][:3],[str(boot.RECOVERY/'.venv/bin/python'),'-I','-B'])
            self.assertEqual(kw['cwd'],boot.RECOVERY);self.assertNotIn('OPENROUTER_API_KEY',kw['env'])
            self.assertIn("'run-recovery'",args[0][-1]);ast.parse(args[0][-1])

    def test_failed_partial_changed_or_active_recovery_never_becomes_bootstrap_completion(self):
        bindings={'stage2/no_cutoff_recovery_bootstrap.py':'a'*64}
        with patch.object(boot,'_recovery_files',return_value=bindings),patch.object(boot,'raw',return_value=(b'# fixture',())),\
                patch.object(boot.subprocess,'run') as run:
            for mode in ('returncode','running','partial','boolean','active','total'):
                value=self.status()
                if mode=='running':value['status']='running'
                elif mode=='partial':value['counts']['completed']=2
                elif mode=='boolean':value['counts']['passed']=False
                elif mode=='active':value['counts']['active_tasks']=[63]
                elif mode=='total':value['counts']['failed']=1
                run.return_value=NS(returncode=1 if mode=='returncode' else 0,stdout=json.dumps(value).encode())
                with self.subTest(mode=mode),self.assertRaises(ValueError):boot.recovery_finished()
            run.return_value=NS(returncode=0,stdout=json.dumps(self.status()).encode())
            with patch.object(boot,'_recovery_files',side_effect=[bindings,dict(bindings,changed='b'*64)]),self.assertRaises(ValueError):
                boot.recovery_finished()

    def test_isolated_import_effect_guard_refuses_socket_creation_writes_processes_and_credentials(self):
        code="""
import os,socket,subprocess,sys,tempfile
sys.path.insert(0,STAGE)
import matched_repeat_execution_bootstrap as b
temporary=tempfile.TemporaryDirectory()
target=os.path.join(temporary.name,'must-not-be-created')
b.ACTIVE_HARNESS='terminus-2';b.IMPORTING=True
sys.addaudithook(b.no_effects)
try: socket.socket()
except RuntimeError: pass
else: raise AssertionError('Socket created')
assert not b.VIOLATION
for action in (lambda:open(target,'w'),lambda:subprocess.run(['/usr/bin/true']),lambda:open('.env')):
 try:action()
 except RuntimeError:pass
 else:raise AssertionError('Effect accepted')
 assert b.VIOLATION
b.IMPORTING=False
assert not os.path.exists(target)
temporary.cleanup()
print('isolated-effects-refused')
""".replace('STAGE',repr(str(STAGE)))
        result=subprocess.run([sys.executable,'-I','-B','-c',code],capture_output=True,text=True,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},timeout=20)
        self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(result.stdout.strip(),'isolated-effects-refused')

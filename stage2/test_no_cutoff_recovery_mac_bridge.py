"""Actual isolated Darwin child tests; native audit/provider remain synthetic."""
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import no_cutoff_recovery_mac_bridge as bridge

STAGE = Path(__file__).resolve().parent


class CommitTests(unittest.TestCase):
    def test_commit_is_withheld_until_explicit_final_check(self):
        output=io.BytesIO(); marker=b'commit\n'; value=bridge._CommitTail(output,marker)
        payload=b'payload'*40; footer=marker+b'h'*32+b'a'*32
        value.write(payload+footer); value.flush()
        self.assertEqual(output.getvalue(),payload)
        value.commit((b'a'*32).hex())
        self.assertEqual(output.getvalue(),payload+footer)
        with self.assertRaises(ValueError):value.commit((b'a'*32).hex())
        with self.assertRaises(ValueError):value.write(b'next')

    def test_bad_or_missing_commit_never_flushes_tail(self):
        for payload in (b'',b'wrong'+b'x'*64,b'commit\n'+b'x'*64):
            output=io.BytesIO(); value=bridge._CommitTail(output,b'commit\n'); value.write(payload)
            before=output.getvalue()
            with self.assertRaises(ValueError):value.commit('0'*64)
            self.assertEqual(output.getvalue(),before)

    def test_partial_real_pipe_writes_preserve_exact_bytes(self):
        class Short:
            def __init__(self): self.value=bytearray()
            def write(self,value): self.value.extend(value[:3]); return min(3,len(value))
            def flush(self): pass
        output=Short(); value=bridge._CommitTail(output,b'X')
        expected=b'head'*100+b'X'+b'h'*32+b'a'*32
        for offset in range(0,len(expected),7):value.write(expected[offset:offset+7])
        value.commit((b'a'*32).hex())
        self.assertEqual(bytes(output.value),expected)

    def test_program_is_fixed_extracted_bound_code(self):
        raw=(STAGE/'no_cutoff_recovery_mac_bridge.py').read_bytes()
        import mac_operator_files as mac
        value={'commit':'a'*40,'bound':{'no_cutoff_recovery_mac_bridge.py':hashlib.sha256(raw).hexdigest()}}
        with patch.object(mac,'raw',return_value=(raw,())):
            code=bridge._program(value,'prepare'); ast.parse(code)
            self.assertIn('connection.handoff.send(output)',code)
            self.assertIn('output.commit(sent[',code)
            self.assertIn('connection.operator.loaded(root,native)',code)
            with self.assertRaises(ValueError):bridge._program(value,'callback')


class SenderDiagnosticTests(unittest.TestCase):
    def record(self):
        return dict(stage='original_audit_archive', error_class='ValueError', transport=None)

    def child(self, code):
        process=subprocess.Popen([sys.executable,'-I','-B','-c',code],
            stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        self.addCleanup(process.stderr.close)
        def finish():
            if process.poll() is None:process.kill();process.wait(timeout=10)
        self.addCleanup(finish)
        return process

    def test_real_child_stream_discards_large_untrusted_stderr(self):
        record=self.record()
        code='import os\nos.write(2,b"private payload"*100000+b"\\n")\nos.write(2,'+repr(
            b'UTS_MAC_RECOVERY_CHILD_FAILURE_V1 '+json.dumps(record).encode()+b'\n')+')\nraise SystemExit(1)'
        process=self.child(code)
        with self.assertRaises(bridge._SenderFailure) as caught:bridge._sender_result(process)
        self.assertEqual(caught.exception.diagnostic,record)
        self.assertEqual(caught.exception.returncode,1)
        self.assertNotIn('private',str(caught.exception))
        self.assertEqual(process.poll(),1)

    def test_missing_duplicate_or_untrusted_record_never_becomes_trusted_metadata(self):
        valid=b'UTS_MAC_RECOVERY_CHILD_FAILURE_V1 '+json.dumps(self.record()).encode()+b'\n'
        for raw in (b'private error text\n',valid+valid,
                b'UTS_MAC_RECOVERY_CHILD_FAILURE_V1 '+b'{"stage":"private payload"}\n'):
            with self.subTest(raw_length=len(raw)):
                process=self.child('import os\nos.write(2,'+repr(raw)+')\nraise SystemExit(1)')
                with self.assertRaises(bridge._SenderFailure) as caught:bridge._sender_result(process)
                self.assertEqual(caught.exception.diagnostic,
                    dict(stage='unreported_child',error_class='OtherError',transport=None))

    def test_success_requires_no_failure_record_and_successful_exit(self):
        self.assertIsNone(bridge._sender_result(self.child('pass')))
        raw=b'UTS_MAC_RECOVERY_CHILD_FAILURE_V1 '+json.dumps(self.record()).encode()+b'\n'
        with self.assertRaises(bridge._SenderFailure):
            bridge._sender_result(self.child('import os\nos.write(2,'+repr(raw)+')'))

    def test_schema_rejects_arbitrary_fields_classes_and_noninteger_codes(self):
        self.assertTrue(bridge._valid_failure(self.record()))
        for value in (dict(self.record(),message='private text'),
                dict(self.record(),error_class='PrivateClassName'),
                dict(self.record(),stage='private path'),
                dict(self.record(),transport=dict(status='child_exit',error_class='ValueError',
                    returncode=True,stdout_bytes=0))):
            self.assertFalse(bridge._valid_failure(value))

    def test_real_error_projection_drops_messages_frames_and_other_metadata(self):
        from no_cutoff_final_transport import AuditTransportError
        error=AuditTransportError(dict(status='child_exit',error_type='ValueError',returncode=1,
            stdout_bytes=0,diagnostics={'private':'not retained'},message='private payload'))
        record=bridge._child_failure(error)
        self.assertEqual(record,dict(stage='entry',error_class='AuditTransportError',
            transport=dict(status='child_exit',error_class='ValueError',returncode=1,stdout_bytes=0)))
        self.assertNotIn('private',json.dumps(record))

    def test_duplicate_json_keys_and_truncated_or_oversized_markers_are_untrusted(self):
        for raw in (bridge.FAILURE_PREFIX+b'{"stage":"entry","stage":"entry"}\n',
                bridge.FAILURE_PREFIX+json.dumps(self.record()).encode(),
                bridge.FAILURE_PREFIX+b'x'*2000+b'\n'):
            process=self.child('import os\nos.write(2,'+repr(raw)+')\nraise SystemExit(1)')
            with self.assertRaises(bridge._SenderFailure) as caught:bridge._sender_result(process)
            self.assertEqual(caught.exception.diagnostic['stage'],'unreported_child')

    def test_transport_timeout_does_not_signal_a_native_or_other_process(self):
        process=self.child('import time\ntime.sleep(20)')
        with patch.object(bridge,'TIMEOUT',0.01):
            with self.assertRaises(subprocess.TimeoutExpired):bridge._sender_result(process)
        self.assertIsNone(process.poll())  # Only this test's owned-child cleanup may kill it.

    def test_sender_failure_closes_only_its_owned_local_child_and_pipe(self):
        record=self.record();raw=bridge.FAILURE_PREFIX+json.dumps(record).encode()+b'\n'
        command=[sys.executable,'-I','-B','-c','import os\nos.write(2,'+repr(raw)+')\nraise SystemExit(1)']
        with patch.object(bridge,'current') as current, \
                patch.object(bridge,'_child_command',return_value=command):
            with self.assertRaises(bridge._SenderFailure) as caught:
                bridge.send({},subprocess.DEVNULL)
        self.assertEqual(caught.exception.diagnostic,record)
        self.assertEqual(current.call_count,1)


class ChildTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='.uts-report-child-',dir=Path.home() if sys.platform=='darwin' else None)
        self.addCleanup(temp.cleanup); self.root=Path(temp.name).resolve(); self.root.chmod(0o700)
        self.stage=self.root/'stage2'; self.stage.mkdir(mode=0o700)
        self.python=self.root/'.tools/stage2-custom/bin/python'; self.python.parent.mkdir(parents=True,mode=0o700)
        self.python.symlink_to(Path(sys.executable).resolve())
        self.environment=bridge._environment()
        self.environment['TIKTOKEN_CACHE_DIR']=str(self.root/'.tools/stage2-custom/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers')

    def fixture(self,effect='',delay=False,send_prelude='',prepare_prelude=''):
        self.native_names={'no_cutoff_recovery_connection.py','no_cutoff_recovery_policy.py'}
        for name in bridge.EXTRAS:
            path=self.stage/name; path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes((STAGE/name).read_bytes() if name in ('mac_operator_files.py','no_cutoff_recovery_mac_bridge.py') else b'# synthetic bound fixture\n')
            path.chmod(0o600)
        (self.stage/'no_cutoff_recovery_policy.py').write_text('REQUIRED_SOURCE_FILES = frozenset('+repr(self.native_names)+')\n')
        connection = '''import hashlib,os,sys,time
from pathlib import Path
from types import SimpleNamespace as NS
'''+effect+'''
root=Path.cwd()
def identity(s):
 return (s.st_dev,s.st_ino,s.st_mode,s.st_uid,s.st_gid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def mapping():
 return {'stage2/'+n:hashlib.sha256((root/'stage2'/n).read_bytes()).hexdigest() for n in NATIVE}
def loaded(root,native):
 for label,module in tuple(sys.modules.items()):
  filename=getattr(module,'__file__',None)
  if filename and Path(filename).is_relative_to(root/'stage2') and Path(filename).name not in native:
   raise ValueError('Unbound synthetic import')
def prepare(commit):
PREPARE_PRELUDE
 local=mapping()
 return {'bindings':{'local':local},'recovery_local':local,'publication':{}},local
def ids(value):
 return {n:identity((root/n).stat()) for n in value['bindings']['local']}
def merge(a,b):
 for n,h in b.items():
  if n in a and a[n]!=h:raise ValueError('Conflict')
  a[n]=h
def send(output):
SEND_PRELUDE
 output.write(b'synthetic-payload'*40)
 output.flush()
 time.sleep(DELAY)
 output.write(b'COMMIT\\n'+b'h'*32+b'a'*32)
 return {'archive_sha256':(b'a'*32).hex()}
operator=NS(loaded=loaded,_current=lambda value:None)
handoff=NS(report=NS(_merge=merge),send=send,wire=NS(COMMIT=b'COMMIT\\n'))
_local_identities=ids
'''.replace('NATIVE',repr(self.native_names)).replace('DELAY','0.3' if delay else '0').replace(
    'SEND_PRELUDE','\n'.join(' '+line for line in send_prelude.splitlines())).replace(
    'PREPARE_PRELUDE','\n'.join(' '+line for line in prepare_prelude.splitlines()))
        (self.stage/'no_cutoff_recovery_connection.py').write_text(connection)
        final=self.root/bridge.FINAL; final.parent.mkdir(parents=True,mode=0o700)
        # Every private leaf in the real metadata path is actually protected.
        for path in final.parents:
            if path==self.root:break
            path.chmod(0o700)
        self.final_raw=b'{"sources":{}}'; final.write_bytes(self.final_raw); final.chmod(0o600)
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','GIT_CONFIG_NOSYSTEM':'1'}
        commands=[['init','-q'],['config','user.name','Synthetic Test'],['config','user.email','test@example.invalid'],
            ['add','stage2'],['commit','-qm','Synthetic source-bound child fixture']]
        for command in commands:subprocess.run(['git','-C',str(self.root),*command],env=env,check=True,capture_output=True)
        self.commit=subprocess.check_output(['git','-C',str(self.root),'rev-parse','HEAD'],env=env).decode().strip()
        subprocess.run(['git','-C',str(self.root),'update-ref','refs/remotes/origin/main',self.commit],env=env,check=True)
        self.bound={n:hashlib.sha256((self.stage/n).read_bytes()).hexdigest() for n in self.native_names|set(bridge.EXTRAS)}
        native={n:self.bound[n] for n in sorted(self.native_names)}
        frozen=hashlib.sha256(json.dumps(native,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        raw=(STAGE/'no_cutoff_recovery_mac_bridge.py').read_text(); tree=ast.parse(raw)
        pieces=[ast.get_source_segment(raw,n) for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))
            and n.name in ('_CommitTail','_valid_failure','_child_failure','_child')]
        constants=dict(ROOT_LITERAL=str(self.root),EXPECTED_ENV=self.environment,FINAL_LITERAL=bridge.FINAL,
            FINAL_SHA_LITERAL=hashlib.sha256(self.final_raw).hexdigest(),FROZEN_MAP_LITERAL=frozen,
            FAILURE_PREFIX=bridge.FAILURE_PREFIX,CHILD_STAGES=bridge.CHILD_STAGES,
            CHILD_ERRORS=bridge.CHILD_ERRORS,TRANSPORT_STAGES=bridge.TRANSPORT_STAGES,
            VALIDATION_STAGES=bridge.VALIDATION_STAGES)
        self.program='\n'.join(k+'='+repr(v) for k,v in constants.items())+'\n'+'\n\n'.join(pieces)

    def run_child(self,mode='prepare',env=None):
        code=self.program+'\n_child('+','.join(map(repr,(mode,self.commit,self.bound)))+')'
        return subprocess.run([str(self.python),'-I','-B','-c',code],cwd=self.root,
            env=env or self.environment,capture_output=True,timeout=30)

    def test_actual_isolated_child_checks_preimport_sources_and_origins(self):
        self.fixture(); result=self.run_child()
        if sys.platform!='darwin':
            self.assertNotEqual(result.returncode,0);return
        self.assertEqual(result.returncode,0,result.stderr.decode())
        record=json.loads(result.stdout)
        self.assertFalse(record['native_operation']); self.assertFalse(record['archive_read'])
        self.assertEqual(record['commit'],self.commit);self.assertEqual(set(record['current_sources']),self.native_names)
        self.assertFalse((self.root/'.runtime/absent-mac-recovery-reporting-bytecode').exists())

    def test_actual_complete_sender_pipe_footer(self):
        self.fixture(); result=self.run_child('send')
        if sys.platform!='darwin':self.assertNotEqual(result.returncode,0);return
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(result.stdout,b'synthetic-payload'*40+b'COMMIT\n'+b'h'*32+b'a'*32)

    def test_actual_child_failure_handler_emits_stage_not_private_payload(self):
        self.fixture(send_prelude="raise ValueError('private synthetic task payload')")
        raw=(STAGE/'no_cutoff_recovery_mac_bridge.py').read_bytes()
        import mac_operator_files as mac
        with patch.object(mac,'raw',return_value=(raw,())):
            generated=bridge._program({'commit':self.commit,'bound':{
                'no_cutoff_recovery_mac_bridge.py':hashlib.sha256(raw).hexdigest()}},'send')
        marker='\nexcept BaseException as error:\n'
        self.assertEqual(generated.count(marker),1)
        code=self.program+'\ntry:\n _child('+','.join(map(repr,('send',self.commit,self.bound)))+')'+marker+generated.split(marker)[1]
        result=subprocess.run([str(self.python),'-I','-B','-c',code],cwd=self.root,
            env=self.environment,capture_output=True,timeout=30)
        self.assertEqual(result.returncode,1)
        self.assertEqual(result.stdout,b'')
        self.assertTrue(result.stderr.startswith(bridge.FAILURE_PREFIX))
        record=json.loads(result.stderr[len(bridge.FAILURE_PREFIX):])
        self.assertTrue(bridge._valid_failure(record))
        self.assertEqual(record['stage'],'original_audit_archive' if sys.platform=='darwin' else 'entry')
        self.assertEqual(record['error_class'],'ValueError')
        self.assertNotIn(b'private synthetic',result.stderr)

    def test_send_allows_fdopen_of_own_existing_anonymous_pipe(self):
        self.fixture(send_prelude="""reader,writer=os.pipe()
with os.fdopen(writer,'wb',buffering=0) as stream: stream.write(b'pipe-check')
with os.fdopen(reader,'rb',buffering=0) as stream:
 assert stream.read()==b'pipe-check'""")
        result=self.run_child('send')
        if sys.platform!='darwin':self.assertNotEqual(result.returncode,0);return
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(result.stdout,b'synthetic-payload'*40+b'COMMIT\n'+b'h'*32+b'a'*32)

    def test_send_regular_file_write_still_latches_refusal(self):
        self.fixture(send_prelude="""try: open('must-not-exist-after-import','wb')
except PermissionError: pass""")
        result=self.run_child('send')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'must-not-exist-after-import').exists())
        self.assertNotIn(b'COMMIT\n'+b'h'*32+b'a'*32,result.stdout)

    def test_send_regular_descriptor_write_still_latches_refusal(self):
        self.fixture(send_prelude="""descriptor=os.open(root/'stage2/no_cutoff_recovery_policy.py',os.O_RDONLY)
try:
 try: os.fdopen(descriptor,'wb')
 except PermissionError: pass
finally:
 try: os.close(descriptor)
 except OSError: pass""")
        result=self.run_child('send')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn(b'COMMIT\n'+b'h'*32+b'a'*32,result.stdout)

    def test_send_arbitrary_process_with_stdin_pipe_still_refused(self):
        self.fixture(effect='import subprocess',send_prelude="""try: subprocess.Popen(['/usr/bin/true'],stdin=subprocess.PIPE)
except PermissionError: pass""")
        result=self.run_child('send')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn(b'COMMIT\n'+b'h'*32+b'a'*32,result.stdout)

    def test_exact_sender_popen_reaches_local_veto_without_launching_ssh(self):
        argv=['ssh','-F','/dev/null','-i',str(self.root/'.runtime/netcup/id_ed25519'),
            '-o','IdentitiesOnly=yes','-o','StrictHostKeyChecking=yes','-o','BatchMode=yes',
            '-o','UserKnownHostsFile='+str(self.root/'.runtime/netcup/known_hosts'),
            '-o','ConnectTimeout=10','-o','ConnectionAttempts=1','-o','ClearAllForwardings=yes',
            '-o','RequestTTY=no','-o','LogLevel=ERROR','root@62.83.32.126','python3 -']
        self.fixture(effect='import subprocess',send_prelude=f"""expected={argv!r}
observed=[]
def veto(event,args):
 if event=='subprocess.Popen' and args[1][0]=='ssh':
  assert list(args[1])==expected
  observed.append(True)
  raise RuntimeError('Synthetic veto before actual process creation')
sys.addaudithook(veto)
try: subprocess.Popen(expected,stdin=subprocess.PIPE)
except RuntimeError: pass
assert observed==[True]""")
        result=self.run_child('send')
        if sys.platform!='darwin':self.assertNotEqual(result.returncode,0);return
        self.assertEqual(result.returncode,0,result.stderr.decode())
        self.assertEqual(result.stdout,b'synthetic-payload'*40+b'COMMIT\n'+b'h'*32+b'a'*32)

    def test_import_pipe_write_still_latches_refusal(self):
        self.fixture(effect="""reader,writer=os.pipe()
try:
 try: os.fdopen(writer,'wb',buffering=0)
 except PermissionError: pass
finally:
 for descriptor in (reader,writer):
  try: os.close(descriptor)
  except OSError: pass""")
        result=self.run_child('send')
        self.assertNotEqual(result.returncode,0)
        self.assertNotIn(b'COMMIT\n'+b'h'*32+b'a'*32,result.stdout)

    def test_prepare_pipe_write_still_latches_refusal(self):
        self.fixture(prepare_prelude="""reader,writer=os.pipe()
try:
 try: os.fdopen(writer,'wb',buffering=0)
 except PermissionError: pass
finally:
 for descriptor in (reader,writer):
  try: os.close(descriptor)
  except OSError: pass""")
        result=self.run_child('prepare')
        self.assertNotEqual(result.returncode,0)
        self.assertFalse(result.stdout)

    def test_preimport_drift_refused(self):
        self.fixture(); (self.stage/'no_cutoff_recovery_policy.py').write_bytes(b'raise AssertionError("should never import")')
        result=self.run_child();self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

    def test_wrong_environment_refused(self):
        self.fixture(); result=self.run_child(env={**self.environment,'PROVIDER_API_KEY':'synthetic-forbidden'})
        self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

    def test_caught_socket_probe_is_denied_before_construction(self):
        self.fixture('import socket\ntry: socket.socket()\nexcept RuntimeError: pass\n')
        result=self.run_child()
        if sys.platform!='darwin':self.assertNotEqual(result.returncode,0);return
        self.assertEqual(result.returncode,0,result.stderr.decode())

    def test_caught_credential_read_remains_failure(self):
        self.fixture("try: open('.env','rb')\nexcept PermissionError: pass\n")
        result=self.run_child();self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

    def test_caught_file_write_remains_failure(self):
        self.fixture("try: open('must-not-exist','w')\nexcept PermissionError: pass\n")
        result=self.run_child();self.assertNotEqual(result.returncode,0)
        self.assertFalse((self.root/'must-not-exist').exists())

    def test_caught_process_creation_remains_failure(self):
        self.fixture("import subprocess\ntry: subprocess.run(['/usr/bin/true'])\nexcept PermissionError: pass\n")
        result=self.run_child();self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

    def test_caught_environment_mutation_remains_failure(self):
        self.fixture("try: os.environ['FORBIDDEN']='x'\nexcept PermissionError: pass\n")
        result=self.run_child();self.assertNotEqual(result.returncode,0);self.assertFalse(result.stdout)

    def test_late_same_byte_source_replacement_withholds_commitment(self):
        self.fixture(delay=True)
        code=self.program+'\n_child('+','.join(map(repr,('send',self.commit,self.bound)))+')'
        process=subprocess.Popen([str(self.python),'-I','-B','-c',code],cwd=self.root,
            env=self.environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            first=process.stdout.read(1)
            if sys.platform=='darwin':
                self.assertEqual(first,b's')
                path=self.stage/'no_cutoff_recovery_policy.py'; raw=path.read_bytes()
                path.rename(self.stage/'retained-original-policy');path.write_bytes(raw)
            output,error=process.communicate(timeout=30)
            self.assertNotEqual(process.returncode,0)
            self.assertNotIn(b'COMMIT\n'+b'h'*32+b'a'*32,first+output)
        finally:
            if process.poll() is None:process.kill();process.wait(timeout=10)
            process.stdout.close();process.stderr.close()


if __name__=='__main__':unittest.main()

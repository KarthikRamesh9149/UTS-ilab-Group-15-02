"""Pinned operator SSH connection for prerequisite inspection only.

No deployment, qualification, registration or paid-run operation exists here.
Use only after predecessor completion/export/backup. The actual sender freshly
captures and reads the existing off-server archive. A detached native service
receives it and opens its own live locked session; no witness crosses processes.
"""
import base64
import os
import secrets
import selectors
import shlex
import subprocess
import time

import matched_repeat_baseline as baseline
import matched_repeat_amended_handoff as handoff
import matched_repeat_policy as policy
import matched_repeat_predecessor as operator
import matched_repeat_runtime as runtime
import matched_repeat_stream as wire
from progress_dashboard import ssh_command, REMOTE_HOST
from scored_gateway import durable_json, private_directory

TIMEOUT = handoff.launch.transport.HANDOFF_SECONDS  # Reporting only, not task time.
REPLY_LIMIT = 16384


def bindings(repo, harness):
    handoff._first(harness)
    repo = operator._operator(repo)
    anchors = operator._anchors(repo)
    names = set(anchors['proof']['sources']) | policy.REQUIRED_SOURCE_FILES
    files = {'stage2/' + name: anchors['local']['stage2/' + name] for name in names}
    files.update({'.runtime/stage2/' + policy.BASELINE_FILE: baseline.ORIGINAL_FILE_SHA256,
        '.runtime/stage2/' + policy.FINAL_FILE: baseline.FINAL_FILE_SHA256})
    # Refuse unfinished predecessor evidence locally before starting a service.
    # send() still performs its independent fresh audit/archive read, not reuse.
    # The amended route uses its own exclusive destination. The old reader's
    # completed path retains a failed operation and is never a fallback.
    for name in ('snapshot.json', 'backup.json', 'evidence.tar.gz'):
        operator._regular(repo, handoff.receiver.DESTINATION + '/' + name)
    # Current committed amended sources and completed backup/export inventory
    # are required BEFORE starting a service; send still freshly audits/reads.
    commit = handoff.launch._git('rev-parse', 'HEAD').decode().strip()
    handoff.operator._prepare(commit, harness)
    # Only the archived reporting bundle is tied to its retained old commit.
    # Current repeat sources are separately checked above; a later qualified
    # repeat-service addition must not retroactively rewrite the final backup.
    handoff.export._read_backup(handoff.export._operator(commit))
    handoff.export._public_folder(True)
    handoff.export._private_folder(handoff.export.STATE, {'intent.json', 'result.json'})
    return files


def native_program(harness, nonce, files, *, role, relay_pid=None):
    """Stdlib pre-import guard and fixed command; stdin is solely archive data."""
    from matched_repeat_service import identity
    identity(harness, nonce)
    if role not in ('relay', 'service') or (role == 'service' and (type(relay_pid) is not int or relay_pid <= 0)):
        raise ValueError('Exact native connection role required')
    handoff._maps(files)
    required = {'stage2/' + name for name in policy.REQUIRED_SOURCE_FILES}
    inputs = {'.runtime/stage2/' + policy.BASELINE_FILE: baseline.ORIGINAL_FILE_SHA256,
        '.runtime/stage2/' + policy.FINAL_FILE: baseline.FINAL_FILE_SHA256}
    if (not required.issubset(files) or any(not name.startswith('stage2/') and name not in inputs for name in files)
            or any(files.get(name) != sha for name, sha in inputs.items())):
        raise ValueError('Complete source-bound native connection required')
    root = str(runtime.DEPLOYMENTS[harness])
    program = '''
import hashlib, json, os, platform, subprocess, sys
from pathlib import Path
root=Path(ROOT); files=FILES
FINAL_GUARD
if (platform.system()!='Linux' or os.getuid()!=0 or not sys.flags.isolated or not sys.dont_write_bytecode
 or root.is_symlink() or root.resolve()!=root or not root.is_dir()
 or (root/'.venv').is_symlink() or Path(sys.prefix).resolve()!=root/'.venv'):
 raise ValueError('Exact isolated native repeat interpreter required')
cache=root/'.runtime/unused-matched-connection-bytecode'
if cache.exists() or cache.is_symlink(): raise ValueError('Connection cache prefix must not exist')
sys.pycache_prefix=str(cache)
def check():
 for name in ('operator-stop-request.json','provider-stop.json'):
  p=root/'.runtime/stage2'/name
  if p.exists() or p.is_symlink(): raise ValueError('Persistent repeat stop')
 for directory,unit in ANCESTORS:
  base=Path(directory)
  if base==final_guard['ROOT']:
   final_guard['service']()
   continue
  if base.is_symlink() or base.resolve()!=base or not base.is_dir(): raise ValueError('Regular ancestor required')
  for name in ('operator-stop-request.json','provider-stop.json'):
   p=base/'.runtime/stage2'/name
   if p.exists() or p.is_symlink(): raise ValueError('Persistent ancestor stop')
  raw=subprocess.check_output(['systemctl','show',unit,'--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus'],text=True,timeout=10)
  state=dict(line.split('=',1) for line in raw.splitlines() if '=' in line)
  if state!=dict(LoadState='loaded',ActiveState='inactive',SubState='dead',MainPID='0',ExecMainStatus='0'):
   raise ValueError('Successful inactive ancestors required before native imports')
 for name,expected in files.items():
  path=root
  for part in Path(name).parts:
   path/=part
   if path.is_symlink(): raise ValueError('Symlinked connection input')
  st=path.stat()
  if (not path.is_file() or (name.startswith('.runtime/') and (st.st_uid!=0 or st.st_mode & 0o077))):
   raise ValueError('Private owned connection inputs required')
  with path.open('rb') as stream:
   if hashlib.file_digest(stream,'sha256').hexdigest()!=expected: raise ValueError('Native connection source/input drift')
 # The exact raw, independently pinned final proof authenticates the complete
 # inherited inventory before imports, not only the new repeat modules.
 proof=json.loads((root/FINAL_INPUT).read_bytes())
 inherited={'stage2/'+name for name in proof['sources']}
 if set(files)!=inherited|REQUIRED|INPUTS: raise ValueError('Incomplete native source inventory')
check()
os.chdir(root);sys.path.insert(0,str(root/'stage2'))
from matched_repeat_service import relay,serve
check()
try:
 CALL
except BaseException:
 print(json.dumps(dict(status='connection_failed_preserve_private_evidence',paid_launch_ready=False)),file=sys.stderr)
 raise SystemExit(1) from None
'''
    ancestors = [(str(baseline.ORIGINAL_ROOT), 'uts-stage2-corrected-20260923.service'),
        (str(baseline.FINAL_ROOT), 'uts-stage2-custom-no-cutoff-final-20260928.service')]
    call = ('relay(root,' + repr(harness) + ',' + repr(nonce) + ',files)' if role == 'relay' else
        'serve(root,' + repr(harness) + ',' + repr(nonce) + ',files,' + repr(relay_pid) + ')')
    program = program.replace('Path(ROOT)', 'Path(' + repr(root) + ')').replace('files=FILES', 'files=' + repr(files))
    raw = baseline.final_guard.source(files['stage2/no_cutoff_final_guard.py'])
    setup = "final_guard={}\nexec(compile(" + repr(raw) + ",'<bound-final-compatibility>','exec'),final_guard)"
    program = program.replace('FINAL_GUARD', setup)
    program = program.replace('in ANCESTORS:', 'in ' + repr(ancestors) + ':').replace(' CALL', ' ' + call)
    program = program.replace('root/FINAL_INPUT', 'root/' + repr('.runtime/stage2/' + policy.FINAL_FILE))
    program = program.replace('|REQUIRED|INPUTS', '|' + repr(required) + '|' + repr(set(inputs)))
    # No shell/systemd variable expansion can change the encoded Python source.
    encoded = base64.b64encode(program.encode()).decode()
    return "import base64;exec(compile(base64.b64decode(" + repr(encoded) + "),'<matched-repeat-connection>','exec'))"


def command(repo, harness, nonce, files):
    args = ssh_command(repo)
    if args[-3:] != [REMOTE_HOST, 'python3', '-'] or REMOTE_HOST != 'root@62.83.32.126':
        raise ValueError('Existing pinned SSH command shape changed')
    # Replace the existing interpreter, do not append another one. No -tt,
    # proxy, extra destination, password prompt or host-key relaxation is added.
    remote = ['/usr/bin/env', '-i', 'PATH=/usr/bin:/bin', 'LANG=C.UTF-8',
        'DO_NOT_TRACK=1', 'LITELLM_LOCAL_MODEL_COST_MAP=True',
        str(runtime.DEPLOYMENTS[harness] / '.venv/bin/python'), '-I', '-B', '-c',
        native_program(harness, nonce, files, role='relay')]
    return args[:-2] + [shlex.join(remote)]


def read_reply(stream):
    """Bounded metadata read, not a polling watcher or a study runtime limit."""
    data = bytearray(); deadline = time.monotonic() + TIMEOUT
    with selectors.DefaultSelector() as selector:
        selector.register(stream, selectors.EVENT_READ)
        while b'\n' not in data:
            left = deadline - time.monotonic()
            if left <= 0 or not selector.select(left):
                raise ValueError('Native connection acknowledgement timed out; inspect before retrying')
            raw = os.read(stream.fileno(), min(4096, REPLY_LIMIT + 1 - len(data)))
            if not raw or len(data) + len(raw) > REPLY_LIMIT:
                raise ValueError('Incomplete or oversized native acknowledgement')
            data.extend(raw)
    line, trailing = bytes(data).split(b'\n', 1)
    if trailing:
        raise ValueError('Unexpected extra native acknowledgement bytes')
    return wire.loads(line)


def _reply(value, harness, nonce, files, *, sent=None, pid=None):
    from matched_repeat_service import identity, OPERATION
    expected = dict(operation=OPERATION, nonce=nonce, unit=identity(harness, nonce),
        root=str(runtime.DEPLOYMENTS[harness]), harness=harness,
        bindings_sha256=policy.fingerprint(files), paid_launch_ready=False)
    if (any(policy.fingerprint(value.get(k)) != policy.fingerprint(v) for k, v in expected.items())
            or type(value.get('native_pid')) is not int or value['native_pid'] <= 0):
        raise ValueError('Native acknowledgement does not match the exact operation')
    if sent is None:
        if value.get('kind') != 'matched_repeat_receiver_ready_not_authenticated' or set(value) != set(expected) | {'kind', 'native_pid'}:
            raise ValueError('Receiver readiness is not predecessor authentication')
    else:
        expected.update(kind='matched_repeat_prerequisites_checked_not_dispatch', native_pid=pid,
            operator_document_sha256=sent['operator_document_sha256'], archive_sha256=sent['archive_sha256'])
        if (set(value) != set(expected) | {'prerequisites_sha256'}
                or any(policy.fingerprint(value.get(k)) != policy.fingerprint(v) for k, v in expected.items())):
            raise ValueError('Native session did not authenticate this exact live operator transfer')
        policy._hash(value['prerequisites_sha256'])
    return value


def inspect_native(repo, harness='terminus-2'):
    """One explicit inspection, no retries or saved-record shortcut.

    This is not called while custom final89 is active. On uncertain transport
    failure inspect the retained native intent/log/result before a new action;
    never infer that a service did not start and never signal it via this helper.
    """
    repo = operator._operator(repo); files = bindings(repo, harness)
    nonce = secrets.token_hex(16)
    from matched_repeat_service import identity, OPERATION
    parent = repo / '.runtime/netcup/matched-repeat-connections'
    if parent.is_symlink() or parent.resolve() != parent:
        raise ValueError('Regular operator connection evidence directory required')
    private_directory(parent)
    folder = parent / nonce; folder.mkdir(mode=0o700)
    intent = dict(operation=OPERATION, nonce=nonce, unit=identity(harness, nonce), harness=harness,
        root=str(runtime.DEPLOYMENTS[harness]), bindings_sha256=policy.fingerprint(files),
        paid_launch_ready=False)
    durable_json(folder / 'intent.json', intent)
    process = None
    try:
        process = subprocess.Popen(command(repo, harness, nonce, files), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        ready = _reply(read_reply(process.stdout), harness, nonce, files)
        durable_json(folder / 'receiver.json', ready)
        sent = handoff.send(repo, process.stdin, harness)  # Real capture and archive read, every time.
        process.stdin.close()  # EOF ends only the archive stream, not the native service.
        result = _reply(read_reply(process.stdout), harness, nonce, files, sent=sent, pid=ready['native_pid'])
        if process.wait(timeout=10) != 0 or process.stdout.read(1):
            raise ValueError('SSH connection ended ambiguously; inspect retained native evidence')
        durable_json(folder / 'result.json', result)
        return result
    except BaseException as error:
        # Terminate only our SSH client if necessary; never stop the detached
        # native service or replay a study/qualification operation.
        if process is not None and process.poll() is None:
            process.kill(); process.wait(timeout=10)
        durable_json(folder / 'failure.json', dict(intent,
            status='connection_uncertain_inspect_native_evidence_before_another_operation'))
        error.add_note('Inspect native unit ' + intent['unit'] + '; operator evidence: ' + str(folder))
        raise
    finally:
        if process is not None:
            process.stdin.close(); process.stdout.close()

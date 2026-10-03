"""Stdlib pre-import gate for the fixed baseline execution roots.

This is not an installer, qualification, recovery audit or paid permission.
The actual service must consume the real predecessor session in its own task.
"""
import ast
import base64
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import stat
import sys

ROOTS = {
    'terminus-2': Path('/opt/uts-capstone-matched-repeat-terminus-2-20261003-r4'),
    'openhands': Path('/opt/uts-capstone-matched-repeat-openhands-20260928')}
RECOVERY = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r6')
RETIRED = Path('/opt/uts-capstone-matched-repeat-terminus-2-20260928')
RETIRED_SECOND = Path('/opt/uts-capstone-matched-repeat-terminus-2-20261002-r2')
RETIRED_THIRD = Path('/opt/uts-capstone-matched-repeat-terminus-2-20261003-r3')
RECOVERY_COMMIT = 'fbefc033cd04c7981e7374f68c9d5b20186d461a'
RECOVERY_SOURCES_SHA = 'bc6adb1cdd6792c1617946de5c876972016884d6a3ceb4851c7a39deae23175d'
BASELINE_INPUT = '.runtime/stage2/matched-repeat-original-qualification.json'
FINAL_INPUT = '.runtime/stage2/matched-repeat-custom-final-qualification.json'
BASELINE_SHA = '813b8762eae8caa6b32ccf2bee9c7fa5d0c272ff0e756b07e7251bcb2cd9e433'
FINAL_SHA = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
WINDOW = 64 * 1024 * 1024
IMPORTING = False
VIOLATION = False
ACTIVE_HARNESS = None


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def acl(path):
    if not hasattr(os, 'listxattr') or any(n in {'system.posix_acl_access', 'system.posix_acl_default'}
            for n in os.listxattr(path, follow_symlinks=False)):
        raise ValueError('ACL-free protected recovery connection required')

def directories(path, *, private=False):
    """Full canonical ancestry; directory writes do not change its identity."""
    saved = []
    for directory in (*reversed(path.parents), path):
        s = directory.lstat(); acl(directory)
        if (directory.resolve() != directory or not stat.S_ISDIR(s.st_mode)
                or s.st_uid not in {0, os.getuid()} or s.st_gid not in {0, os.getgid()}
                or s.st_mode & 0o7022 or directory == path and private
                and (stat.S_IMODE(s.st_mode) != 0o700 or s.st_uid != os.getuid() or s.st_gid != os.getgid())):
            raise ValueError('Protected canonical connection directory required')
        saved.append((str(directory), s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid))
    return tuple(saved)

def raw(root, name, expected=None):
    if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or any(p in ('', '.', '..') for p in name.split('/')) or name.startswith('/')):
        raise ValueError('Exact relative connection input required')
    path = root / name; before = directories(path.parent)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        s = os.fstat(stream.fileno()); acl(path)
        if (not stat.S_ISREG(s.st_mode) or s.st_nlink != 1 or s.st_uid != os.getuid()
                or s.st_gid != os.getgid() or s.st_mode & 0o7022 or s.st_size > WINDOW
                or name.startswith('.runtime/') and stat.S_IMODE(s.st_mode) != 0o600):
            raise ValueError('Protected single-link connection file required')
        value = stream.read(WINDOW + 1)
        if identity(os.fstat(stream.fileno())) != identity(s):
            raise ValueError('Connection file changed while reading')
    if (len(value) > WINDOW or identity(path.lstat()) != identity(s)
            or before != directories(path.parent)
            or expected is not None and hashlib.sha256(value).hexdigest() != expected):
        raise ValueError('Connection source/input bytes or identity changed')
    return value, identity(s)

def loads(raw_bytes):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result: raise ValueError('Duplicate connection JSON key')
            result[k] = v
        return result
    def constant(_): raise ValueError('Nonfinite connection JSON')
    value = json.loads(raw_bytes.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    if type(value) is not dict: raise ValueError('Connection JSON object required')
    return value


def root_for(harness):
    if type(harness) is not str or harness not in ROOTS:
        raise ValueError('Exact fixed baseline harness required')
    return ROOTS[harness]


def environment(harness):
    root = root_for(harness)
    return dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        LANG='C.UTF-8', DO_NOT_TRACK='1', LITELLM_LOCAL_MODEL_COST_MAP='True',
        LITELLM_MODE='PRODUCTION', PYTHON_DOTENV_DISABLED='1',
        TIKTOKEN_CACHE_DIR=str(root/'.venv/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers'))


def context(harness):
    root = root_for(harness)
    if (platform.system() != 'Linux' or os.getuid() != 0 or os.getgid() != 0
            or not sys.flags.isolated or not sys.dont_write_bytecode
            or Path(sys.prefix).resolve() != root/'.venv'
            or Path(sys.executable).absolute() != root/'.venv/bin/python'
            or Path(__file__).absolute() != root/'stage2/matched_repeat_execution_bootstrap.py'
            or dict(os.environ) != environment(harness)):
        raise ValueError('Own isolated credential-free baseline interpreter required')
    directories(root, private=True); directories(root/'.runtime/stage2', private=True)
    directories(root/'.venv'); directories(root/'stage2')
    cache = root/'.absent-baseline-execution-bytecode'
    if cache.exists() or cache.is_symlink() or sys.pycache_prefix != str(cache):
        raise ValueError('Exact absent baseline execution bytecode prefix required')
    return root


def _required(source):
    nodes = [n.value for n in ast.parse(source).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id == 'REQUIRED_SOURCE_FILES' for t in n.targets)]
    if (len(nodes) != 1 or not isinstance(nodes[0],ast.Call)
            or not isinstance(nodes[0].func,ast.Name) or nodes[0].func.id != 'frozenset'
            or len(nodes[0].args) != 1 or nodes[0].keywords):
        raise ValueError('Complete independently bound source inventory required')
    names = ast.literal_eval(nodes[0].args[0])
    if type(names) is not set or not names or any(type(n) is not str for n in names):
        raise ValueError('Exact literal source inventory required')
    return names


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _fingerprint(value):
    return _hash(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def check(harness, files, previous=None):
    root = context(harness)
    if type(files) is not dict or not files:
        raise ValueError('Complete committed baseline bindings required')
    observed = {}
    for name, digest in files.items():
        if type(digest) is not str or not re.fullmatch('[a-f0-9]{64}',digest):
            raise ValueError('Exact committed source hash required')
        _, observed[name] = raw(root,name,digest)
    if files.get(BASELINE_INPUT) != BASELINE_SHA or files.get(FINAL_INPUT) != FINAL_SHA:
        raise ValueError('Exact original baseline and custom-final private bytes required')
    final = loads(raw(root,FINAL_INPUT,FINAL_SHA)[0])
    source = raw(root,'stage2/matched_repeat_policy.py',files['stage2/matched_repeat_policy.py'])[0]
    required = set(final['sources']) | _required(source)
    if set(files) != {'stage2/'+n for n in required} | {BASELINE_INPUT,FINAL_INPUT}:
        raise ValueError('Incomplete original/current baseline inventory')
    if previous is not None and observed != previous:
        raise ValueError('Baseline source/private identity was replaced')
    return observed


def _recovery_files():
    """Actual frozen source reads, not a saved recovery completion flag."""
    original = '.runtime/stage2/no-cutoff-recovery-original-qualification.json'
    final = loads(raw(RECOVERY,original,FINAL_SHA)[0])
    source = raw(RECOVERY,'stage2/no_cutoff_recovery_policy.py')[0]
    names = set(final['sources']) | _required(source)
    sources = {n:_hash(raw(RECOVERY,'stage2/'+n)[0]) for n in names}
    if _fingerprint(sources) != RECOVERY_SOURCES_SHA:
        raise ValueError('Exact frozen completed recovery source bytes required')
    bound = {'stage2/'+n:h for n,h in sources.items()}
    bound[original] = FINAL_SHA
    return bound


def recovery_finished():
    """Actual fixed service exit and3 counts only, not fresh audit/admission."""
    bindings = _recovery_files()
    module, _ = raw(RECOVERY,'stage2/no_cutoff_recovery_bootstrap.py',
        bindings['stage2/no_cutoff_recovery_bootstrap.py'])
    program = ("import base64,types,sys\n"
        "m=types.ModuleType('no_cutoff_recovery_bootstrap')\n"
        "m.__file__="+repr(str(RECOVERY/'stage2/no_cutoff_recovery_bootstrap.py'))+"\n"
        "sys.modules[m.__name__]=m\n"
        "exec(compile(base64.b64decode("+repr(base64.b64encode(module).decode())+"),m.__file__,'exec'),m.__dict__)\n"
        "m.main("+','.join(map(repr,('0'*32,bindings,RECOVERY_COMMIT,'status',None,'run-recovery')))+")\n")
    env = dict(environment('terminus-2'))
    env['TIKTOKEN_CACHE_DIR'] = str(RECOVERY/'.venv/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers')
    result = subprocess.run([str(RECOVERY/'.venv/bin/python'),'-I','-B','-c',program],
        cwd=RECOVERY,env=env,capture_output=True,timeout=300)
    if result.returncode or len(result.stdout)>16384:
        raise ValueError('Actual successful recovery service completion required')
    value = loads(result.stdout)
    counts = value.get('counts',{})
    if (value.get('kind') != 'read_only_recovery_operation_status_not_admission'
            or value.get('operation') != 'run-recovery'
            or value.get('status') != 'service_exited_successfully_not_completed_study_audit'
            or value.get('paid_launch_ready') is not False or value.get('automatic_resume') is not False
            or counts.get('study') != 'custom-no-cutoff-recovery-20260929'
            or any(type(counts.get(n)) is not int or counts[n] != 3 for n in ('intended','started','completed'))
            or counts.get('active_tasks') != []
            or any(type(counts.get(n)) is not int or counts[n]<0 for n in ('passed','failed','missing_verifier'))
            or sum(counts[n] for n in ('passed','failed','missing_verifier')) != 3):
        raise ValueError('All three actual retained recovery outcomes and successful exit required')
    if _recovery_files() != bindings:
        raise ValueError('Recovery source bytes changed after completion observation')
    return value


def terminus_finished(files):
    """Actual first-repeat service reads in its OWN isolated interpreter.

    This is completion metadata, not its fresh completed audit/SAME archive
    handoff. It runs before successor locks; no collector or writer is called.
    """
    root = root_for('terminus-2')
    before = {n: raw(root, n, h) for n, h in files.items()}
    commit_raw, commit_id = raw(root, 'source-commit.txt')
    commit = commit_raw.decode('ascii').strip()
    if not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Actual installed Terminus source revision required')
    module = before['stage2/matched_repeat_execution_bootstrap.py'][0]
    results = {}
    for operation in ('qualify-repeat', 'run-repeat'):
        program = ('import base64,sys,types\n'
            + 'b=types.ModuleType("matched_repeat_execution_bootstrap")\n'
            + 'b.__file__=' + repr(str(root/'stage2/matched_repeat_execution_bootstrap.py')) + '\n'
            + 'sys.modules[b.__name__]=b\n'
            + 'exec(compile(base64.b64decode(' + repr(base64.b64encode(module).decode())
            + '),b.__file__,"exec"),b.__dict__)\n'
            + 'b.main(' + ','.join(map(repr, ('terminus-2', '0'*32, files, commit,
                'status', None, operation))) + ')\n')
        observed = subprocess.run([str(root/'.venv/bin/python'), '-I', '-B', '-c', program],
            cwd=root, env=environment('terminus-2'), stdin=subprocess.DEVNULL,
            capture_output=True, timeout=300)
        if observed.returncode or len(observed.stdout) > 16384:
            raise ValueError('Actual completed Terminus service reader refused')
        value = loads(observed.stdout); counts = value.get('counts', {})
        if (value.get('kind') != 'read_only_baseline_operation_status_not_admission'
                or value.get('operation') != operation
                or value.get('status') != 'service_exited_successfully_not_completed_study_audit'
                or value.get('paid_launch_ready') is not False or value.get('automatic_resume') is not False
                or counts.get('study') != 'baseline-matched-repeat-20260928'
                or counts.get('harness') != 'terminus-2'
                or any(type(counts.get(n)) is not int or counts[n] != 89 for n in ('intended','started','completed'))
                or counts.get('active_tasks') != []
                or any(type(counts.get(n)) is not int or counts[n] < 0 for n in ('passed','failed','missing_verifier'))
                or sum(counts[n] for n in ('passed','failed','missing_verifier')) != 89):
            raise ValueError('All89 actual retained Terminus outcomes and successful services required')
        results[operation] = value
    if (any(raw(root, n, files[n]) != observed for n, observed in before.items())
            or raw(root, 'source-commit.txt') != (commit_raw, commit_id)):
        raise ValueError('Actual completed Terminus sources/private identities changed')
    return results


def ancestors(harness, files):
    root = context(harness)
    # Current stdlib reader retains all failed roots and actual original-manager
    # evidence. It does not qualify a baseline or replace live archive proof.
    name = 'stage2/no_cutoff_recovery_revision.py'
    source = raw(root,name,files[name])[0]
    revision = {}; exec(compile(source,'<bound-recovery-history-reader>','exec'),revision)
    if revision['ROOT'] != RECOVERY: raise ValueError('Exact frozen recovery location required')
    revision['inspect']()
    name = 'stage2/matched_repeat_revision.py'
    source = raw(root, name, files[name])[0]
    retired = {}; exec(compile(source, '<bound-terminal-baseline-reader>', 'exec'), retired)
    if (retired['ROOT'] != RETIRED or retired['SECOND_ROOT'] != RETIRED_SECOND
            or retired['THIRD_ROOT'] != RETIRED_THIRD):
        raise ValueError('All three exact terminal baseline roots required')
    retired['native'](sys.modules[__name__])
    completed = recovery_finished()
    if harness == 'openhands': terminus_finished(files)
    bases = [root,RECOVERY,Path('/opt/uts-capstone-custom-no-cutoff-final-20260928'),
        Path('/opt/uts-capstone-corrected-20260923')]
    if harness == 'openhands': bases.append(root_for('terminus-2'))
    for base in bases:
        for name in ('operator-stop-request.json','provider-stop.json'):
            path = base/'.runtime/stage2'/name
            if path.exists() or path.is_symlink():
                raise ValueError('Persistent stop forbids baseline execution')
    return completed


def no_effects(event,args):
    global VIOLATION
    refused = False
    if event == 'open':
        path,mode,flags = args
        name = Path(os.fsdecode(path)).name if isinstance(path,(str,bytes,os.PathLike)) else ''
        refused = name == '.env' or name.startswith('.env.') or name in {'.jwt_secret','id_ed25519','id_rsa'}
        refused |= IMPORTING and (isinstance(mode,str) and any(c in mode for c in 'wax+')
            or bool(flags&(os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
    if event == 'os.putenv':
        key,value = (os.fsdecode(x) for x in args)
        refused = environment(ACTIVE_HARNESS).get(key) != value
    if event == 'os.unsetenv': refused = True
    if IMPORTING:
        if event == 'socket.__new__': raise RuntimeError('Socket capability probe denied before construction')
        refused |= event.startswith(('socket.','subprocess.','os.exec','os.spawn','os.posix_spawn')) or event in {
            'os.system','os.fork','os.forkpty','os.remove','os.rename','os.rmdir','os.mkdir',
            'os.link','os.symlink','os.truncate','os.chmod','os.chown','os.utime','shutil.copyfile'}
    if refused:
        VIOLATION = True
        raise RuntimeError('Baseline import/credential/environment effect refused')


def main(harness,nonce,files,commit,role,relay_process=None,operation='qualify-repeat'):
    global IMPORTING,ACTIVE_HARNESS
    root = root_for(harness)
    if (type(nonce) is not str or not re.fullmatch('[a-f0-9]{32}',nonce)
            or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}',commit)
            or role not in ('relay','service','status')
            or operation not in ('qualify-repeat','run-repeat')
            or (role != 'service') != (relay_process is None)
            or ACTIVE_HARNESS is not None):
        raise ValueError('One exact committed baseline bootstrap entry required')
    ACTIVE_HARNESS = harness
    sys.pycache_prefix = str(root/'.absent-baseline-execution-bytecode')
    observed = check(harness,files); ancestors(harness,files); check(harness,files,observed)
    os.chdir(root); sys.path.insert(0,str(root/'stage2'))
    sys.addaudithook(no_effects); IMPORTING=True
    try:
        import matched_repeat_execution_service as service
        if operation == 'qualify-repeat': import qualify_matched_repeat
        else: import run_matched_repeat
    finally: IMPORTING=False
    if VIOLATION: raise ValueError('Latched baseline import refusal')
    ancestors(harness,files); check(harness,files,observed); service.loaded(harness,files)
    if role == 'status':
        print(json.dumps(service.operation_status(harness,files,commit,observed,operation),
            sort_keys=True,allow_nan=False))
    elif role == 'relay': service.relay(harness,nonce,files,commit,observed,operation)
    else: service.serve(harness,nonce,files,commit,observed,relay_process,operation)


def reporting(harness, files, commit, mode):
    """Fixed completed reporting transport, never a paid service shortcut."""
    global IMPORTING, ACTIVE_HARNESS
    if (harness not in ROOTS or mode not in ('audit', 'backup')
            or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit)
            or ACTIVE_HARNESS is not None):
        raise ValueError('One fixed committed first-baseline reporting entry required')
    ACTIVE_HARNESS = harness; root = root_for(harness)
    sys.pycache_prefix = str(root / '.absent-baseline-execution-bytecode')
    identities = check(harness, files); ancestors(harness, files); check(harness, files, identities)
    os.chdir(root); sys.path.insert(0, str(root / 'stage2'))
    sys.addaudithook(no_effects); IMPORTING = True
    try:
        import asyncio
        if harness == 'openhands':
            import matched_repeat_openhands_reporting as reporter
        else:
            import matched_repeat_reporting as reporter
    finally: IMPORTING = False
    if VIOLATION: raise ValueError('Latched baseline reporting import refusal')
    ancestors(harness, files); check(harness, files, identities)
    asyncio.run(reporter.native(files, commit, mode))

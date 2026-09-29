"""Stdlib-only, committed recovery connection bootstrap; no paid operation.

The operator embeds these exact bytes in the pinned SSH command. No project
module is imported before the complete current inventory and original private
qualification have been read. Saved receipts never enter this interface.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import stat
import subprocess
import sys

ROOT = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260929')
ORIGINAL = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
QUALIFICATION = '.runtime/stage2/no-cutoff-recovery-original-qualification.json'
QUALIFICATION_SHA = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
IMPORTING = False
VIOLATION = False
WINDOW = 64 * 1024 * 1024  # Metadata/source parser, never a task/output allowance.


def environment():
    return dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
        LANG='C.UTF-8', DO_NOT_TRACK='1', LITELLM_LOCAL_MODEL_COST_MAP='True',
        LITELLM_MODE='PRODUCTION', PYTHON_DOTENV_DISABLED='1',
        TIKTOKEN_CACHE_DIR=str(ROOT / '.venv/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers'))


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


def context():
    if (platform.system() != 'Linux' or os.getuid() != 0 or os.getgid() != 0
            or not sys.flags.isolated or not sys.dont_write_bytecode
            or Path(sys.prefix).resolve() != ROOT / '.venv'
            or Path(sys.executable).absolute() != ROOT / '.venv/bin/python'
            or dict(os.environ) != environment()):
        raise ValueError('Exact isolated credential-free recovery interpreter required')
    directories(ROOT, private=True); directories(ROOT / '.runtime/stage2', private=True)
    directories(ROOT / '.venv'); directories(ROOT / 'stage2')
    cache = ROOT / '.absent-bytecode-cache'
    if cache.exists() or cache.is_symlink() or sys.pycache_prefix != str(cache):
        raise ValueError('Exact absent recovery bytecode prefix required')


def check(files, previous=None):
    context()
    if type(files) is not dict or not files:
        raise ValueError('Complete committed recovery source bindings required')
    identities = {}
    for name, digest in files.items():
        if type(digest) is not str or not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('Exact committed source hash required')
        _, identities[name] = raw(ROOT, name, digest)
    if files.get(QUALIFICATION) != QUALIFICATION_SHA:
        raise ValueError('Exact original private qualification required')
    qualification = loads(raw(ROOT, QUALIFICATION, QUALIFICATION_SHA)[0])
    source = raw(ROOT, 'stage2/no_cutoff_recovery_policy.py', files['stage2/no_cutoff_recovery_policy.py'])[0]
    nodes = [n.value for n in ast.parse(source).body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'REQUIRED_SOURCE_FILES' for t in n.targets)]
    if (len(nodes) != 1 or not isinstance(nodes[0], ast.Call) or not isinstance(nodes[0].func, ast.Name)
            or nodes[0].func.id != 'frozenset' or len(nodes[0].args) != 1 or nodes[0].keywords):
        raise ValueError('Exact bound current recovery inventory required')
    required = ast.literal_eval(nodes[0].args[0])
    names = set(qualification['sources']) | required
    if set(files) != {'stage2/' + n for n in names} | {QUALIFICATION, 'stage2/input_manifest.json'}:
        raise ValueError('Incomplete inherited/current connection inventory')
    if previous is not None and identities != previous:
        raise ValueError('Connection source/private identity replaced')
    return identities


def ancestors(files):
    """Real manager/procfs completion guard, before imports or service writes."""
    source = raw(ROOT, 'stage2/no_cutoff_final_guard.py', files['stage2/no_cutoff_final_guard.py'])[0]
    guard = {}; exec(compile(source, '<bound-original-completion-guard>', 'exec'), guard)
    if guard['ROOT'] != ORIGINAL: raise ValueError('Original completion root changed')
    guard['service']()
    completed = subprocess.check_output(['systemctl', 'show', 'uts-stage2-corrected-20260923.service',
        '--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus'], text=True, timeout=10)
    entries = [line.split('=', 1) for line in completed.splitlines() if '=' in line]
    if len(entries) != 5 or dict(entries) != dict(LoadState='loaded', ActiveState='inactive',
            SubState='dead', MainPID='0', ExecMainStatus='0'):
        raise ValueError('Successful inactive original baseline required')
    for base in (ROOT, ORIGINAL, Path('/opt/uts-capstone-corrected-20260923')):
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            path = base / '.runtime/stage2' / name
            if path.exists() or path.is_symlink(): raise ValueError('Persistent stop forbids connection')


def no_effects(event, args):
    """Import-only effect refusal, with credential reads always forbidden."""
    global VIOLATION
    refused = False
    if event == 'open':
        path, mode, flags = args
        name = Path(os.fsdecode(path)).name if isinstance(path, (str, bytes, os.PathLike)) else ''
        refused = name == '.env' or name.startswith('.env.') or name in {'.jwt_secret', 'id_ed25519', 'id_rsa'}
        refused |= IMPORTING and (isinstance(mode, str) and any(c in mode for c in 'wax+')
            or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
    if event == 'os.putenv':
        k, v = (os.fsdecode(x) for x in args); refused = environment().get(k) != v
    if event == 'os.unsetenv': refused = True
    if IMPORTING:
        if event == 'socket.__new__':
            raise RuntimeError('Import socket capability probe denied before creation')
        refused |= event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in {
            'os.system', 'os.fork', 'os.forkpty', 'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir',
            'os.link', 'os.symlink', 'os.truncate', 'os.chmod', 'os.chown', 'os.utime', 'shutil.copyfile'}
    if refused:
        VIOLATION = True
        raise RuntimeError('Recovery bootstrap refuses credential/environment/import effects')


def main(nonce, files, commit, role, relay_process=None):
    global IMPORTING
    if (type(nonce) is not str or not re.fullmatch('[a-f0-9]{32}', nonce)
            or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit)
            or role not in ('relay', 'service')
            or (role == 'relay') != (relay_process is None)):
        raise ValueError('Exact fixed recovery inspection entry required')
    sys.pycache_prefix = str(ROOT / '.absent-bytecode-cache')
    identities = check(files); ancestors(files); check(files, identities)
    os.chdir(ROOT); sys.path.insert(0, str(ROOT / 'stage2'))
    sys.addaudithook(no_effects)
    IMPORTING = True
    try:
        import no_cutoff_recovery_service as service
    finally: IMPORTING = False
    if VIOLATION: raise ValueError('Refused effect during native project import')
    ancestors(files); check(files, identities)
    service.loaded(files)
    if role == 'relay': service.relay(nonce, files, commit, identities)
    else: service.serve(nonce, files, commit, identities, relay_process)

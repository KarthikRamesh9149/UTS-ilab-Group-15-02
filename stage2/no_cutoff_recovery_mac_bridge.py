"""Separate source-bound Darwin bridge to the unchanged recovery sender.

The actual frozen 318-module capture runs in its own isolated interpreter.
The stdlib launcher is embedded from this committed file and independently
binds this entire Mac amendment before importing the original project tree.
It neither imports new project modules into that frozen tree nor changes its
loaded-source guard. No native installation, saved audit or alternate sender.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import subprocess
import sys
import time

REPO = Path('/Users/karthikramesh/.codex/.chatgpt-projects/g-p-6a789724c2d48191b80421978177d029/terminal-bench-progress-smoke')
PYTHON = REPO / '.tools/stage2-custom/bin/python'
CACHE = REPO / '.runtime/absent-mac-recovery-reporting-bytecode'
FINAL = '.runtime/netcup/custom-no-cutoff-final-20260928/qualified/.runtime/stage2/no-cutoff-final-qualification.json'
FINAL_SHA = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
FROZEN_MAP = 'bc6adb1cdd6792c1617946de5c876972016884d6a3ceb4851c7a39deae23175d'
EXTRAS = (
    'mac_operator_files.py', 'test_mac_operator_files.py',
    'no_cutoff_recovery_mac_archive.py', 'no_cutoff_recovery_mac_bridge.py',
    'no_cutoff_recovery_mac_reporting.py', 'test_no_cutoff_recovery_mac_reporting.py',
    'test_no_cutoff_recovery_mac_bridge.py',
    'protocols/custom_recovery_mac_reporting_20260930.md',
    'no_cutoff_recovery_mac_repair.py', 'test_no_cutoff_recovery_mac_repair.py',
    'no_cutoff_recovery_reporting_repair.py', 'test_no_cutoff_recovery_reporting_repair.py',
    'no_cutoff_recovery_reporting_transport.py',
    'protocols/custom_recovery_reporting_repair_20261002.md',
)
TIMEOUT = 4500  # Same original handoff window, never a task or request limit.
FAILURE_PREFIX = b'UTS_MAC_RECOVERY_CHILD_FAILURE_V1 '
CHILD_STAGES = frozenset({'entry', 'source_bootstrap', 'source_before_imports',
    'project_imports', 'original_prepare', 'prepared_identity_recheck',
    'original_audit_archive', 'original_final_recheck', 'amendment_final_recheck',
    'commitment', 'prepare_reply', 'unreported_child'})
CHILD_ERRORS = frozenset({'ValueError', 'TypeError', 'KeyError', 'IndexError',
    'AssertionError', 'RuntimeError', 'OSError', 'FileNotFoundError', 'FileExistsError',
    'PermissionError', 'TimeoutError', 'TimeoutExpired', 'CalledProcessError',
    'BrokenPipeError', 'EOFError', 'KeyboardInterrupt', 'SystemExit', 'CancelledError',
    'AuditTransportError', 'OtherError'})
TRANSPORT_STAGES = frozenset({'transport_start', 'transport_send', 'transport_read',
    'transport_timeout', 'reply_window_exceeded', 'child_exit', 'transport_finished',
    'local_client_cleanup_uncertain'})
VALIDATION_STAGES = frozenset({'operator_source_recheck', 'completed_return_validation',
    'snapshot_schema_validation', 'final_operator_source_recheck'})


def _environment():
    return dict(PATH='/usr/bin:/bin:/usr/sbin:/sbin', LANG='C.UTF-8',
        __CF_USER_TEXT_ENCODING=f'0x{os.getuid():X}:0x0:0x0',
        PYTHON_DOTENV_DISABLED='1', LITELLM_MODE='PRODUCTION', DO_NOT_TRACK='1',
        LITELLM_LOCAL_MODEL_COST_MAP='True', TIKTOKEN_CACHE_DIR=str(
            REPO/'.tools/stage2-custom/lib/python3.12/site-packages/litellm/litellm_core_utils/tokenizers'))


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _git(*args):
    result = subprocess.run(['git', '-C', str(REPO), *args], capture_output=True,
        timeout=30, env={'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8'})
    if result.returncode or result.stderr:
        raise ValueError('Committed operator source unavailable')
    return result.stdout


def _source_state(commit):
    import mac_operator_files as mac
    if (sys.platform != 'darwin' or Path(__file__).absolute() != REPO/'stage2/no_cutoff_recovery_mac_bridge.py'
            or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit)):
        raise ValueError('Fixed committed Darwin recovery operator required')
    for ref in ('HEAD', 'origin/main'):
        if _git('rev-parse', ref).decode().strip() != commit:
            raise ValueError('Actual HEAD must equal fetched main')
    final = mac.loads(mac.raw(REPO, FINAL, FINAL_SHA)[0])
    policy_raw = mac.raw(REPO, 'stage2/no_cutoff_recovery_policy.py', private=False)[0]
    node = next(n for n in ast.parse(policy_raw).body if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'REQUIRED_SOURCE_FILES' for t in n.targets))
    names = set(final['sources']) | ast.literal_eval(node.value.args[0])
    ancestry = _ancestry(['stage2/'+n for n in names | set(EXTRAS)] + [FINAL])
    bound = {}; identities = {}
    for name in sorted(names | set(EXTRAS)):
        raw, identity = mac.raw(REPO, 'stage2/'+name, private=False)
        if raw != _git('show', commit+':stage2/'+name):
            raise ValueError('Every Mac amendment and frozen source must be committed')
        bound[name] = _digest(raw); identities['stage2/'+name] = identity
    sources = {n:bound[n] for n in sorted(names)}
    if _digest(json.dumps(sources, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()) != FROZEN_MAP:
        raise ValueError('The running R6 source union must remain unchanged')
    if _ancestry(['stage2/'+n for n in names | set(EXTRAS)] + [FINAL]) != ancestry:
        raise ValueError('Operator source/private ancestry changed')
    return dict(commit=commit, bound=bound, current_sources=sources,
        source_identities=identities, source_ancestry=ancestry)


def _ancestry(names):
    import mac_operator_files as mac
    parents = {str((REPO/mac.relative(n)).parent):n.startswith('.runtime/') for n in names}
    return {n:mac.directories(Path(n),private=private) for n,private in sorted(parents.items())}


def _loaded(value):
    from no_cutoff_recovery_predecessor import loaded
    return loaded(REPO, value['bound'])


def _identities(local):
    import mac_operator_files as mac
    return {n:mac.raw(REPO, n, h, private=n.startswith('.runtime/'))[1] for n,h in local.items()}


class _CommitTail:
    """Keep only the final fixed commitment in memory until all late checks."""
    def __init__(self, stream, marker):
        self.stream = stream; self.marker = marker
        self.size = len(marker) + 64; self.tail = bytearray(); self.finished = False

    def fileno(self):
        return self.stream.fileno()

    def write(self, raw):
        if self.finished or not isinstance(raw, (bytes, bytearray, memoryview)):
            raise ValueError('Only a live byte handoff may use the commitment buffer')
        self.tail.extend(raw)
        count = len(self.tail) - self.size
        if count > 0:
            data = memoryview(bytes(self.tail[:count]))
            while data:
                n = self.stream.write(data)
                if n is None or n <= 0: raise ValueError('Incomplete actual handoff pipe write')
                data = data[n:]
            del self.tail[:count]
        return len(raw)

    def flush(self):
        self.stream.flush()

    def commit(self, archive_sha):
        if (self.finished or len(self.tail) != self.size or not self.tail.startswith(self.marker)
                or self.tail[-32:] != bytes.fromhex(archive_sha)):
            raise ValueError('Exact original final handoff commitment required')
        self.finished = True
        remaining = memoryview(bytes(self.tail))
        while remaining:
            count = self.stream.write(remaining)
            if count is None or count <= 0: raise ValueError('Incomplete final handoff commitment')
            remaining = remaining[count:]
        self.stream.flush(); self.tail.clear()


def _valid_failure(value):
    """Only fixed categories and available integer transport metadata escape."""
    if (type(value) is not dict or set(value) != {'stage', 'error_class', 'transport'}
            or type(value['stage']) is not str or value['stage'] not in CHILD_STAGES
            or type(value['error_class']) is not str or value['error_class'] not in CHILD_ERRORS):
        return False
    item = value['transport']
    if item is None: return True
    base = {'status', 'error_class', 'returncode', 'stdout_bytes'}
    extra = {'validation_stage', 'validation_error_class'}
    if (type(item) is not dict or set(item) not in (base, base | extra)
            or type(item['status']) is not str or item['status'] not in TRANSPORT_STAGES
            or item['error_class'] is not None and (type(item['error_class']) is not str
                or item['error_class'] not in CHILD_ERRORS)
            or item['returncode'] is not None and type(item['returncode']) is not int
            or type(item['stdout_bytes']) is not int or not 0 <= item['stdout_bytes'] <= 64 * 1024 * 1024):
        return False
    return not extra.issubset(item) or (
        type(item['validation_stage']) is str and item['validation_stage'] in VALIDATION_STAGES
        and type(item['validation_error_class']) is str and item['validation_error_class'] in CHILD_ERRORS)


def _child_failure(error):
    """Read one fixed local stage, never export a frame, message or payload."""
    stage = 'entry'; trace = error.__traceback__
    while trace is not None:
        if trace.tb_frame.f_code is _child.__code__:
            observed = trace.tb_frame.f_locals.get('stage')
            if type(observed) is str and observed in CHILD_STAGES: stage = observed
        trace = trace.tb_next
    name = type(error).__name__
    if name not in CHILD_ERRORS or type(error).__module__ not in (
            'builtins', 'subprocess', 'asyncio.exceptions', 'no_cutoff_final_transport'):
        name = 'OtherError'
    value = dict(stage=stage, error_class=name, transport=None)
    if name == 'AuditTransportError' and type(error).__module__ == 'no_cutoff_final_transport':
        item = getattr(error, 'metadata', None)
        if type(item) is dict:
            transport = dict(status=item.get('status'), error_class=item.get('error_type'),
                returncode=item.get('returncode'), stdout_bytes=item.get('stdout_bytes'))
            if 'operator_failure_stage' in item or 'operator_error_type' in item:
                transport.update(validation_stage=item.get('operator_failure_stage'),
                    validation_error_class=item.get('operator_error_type'))
            candidate = dict(value, transport=transport)
            if _valid_failure(candidate): value = candidate
    return value


def _child(mode, commit, expected):
    # Embedded stdlib producer, extracted from these exact committed bytes.
    # No child import of this new module or replacement of a frozen function.
    stage = 'entry'
    import ast
    import contextlib
    import hashlib
    import json
    import os
    from pathlib import Path
    import re
    import stat
    import subprocess
    import sys
    import types
    root = Path(ROOT_LITERAL)
    python = root/'.tools/stage2-custom/bin/python'
    cache = root/'.runtime/absent-mac-recovery-reporting-bytecode'
    if (mode not in ('prepare', 'send') or sys.platform != 'darwin'
            or Path.cwd() != root or Path(sys.executable).absolute() != python
            or not sys.flags.isolated or not sys.dont_write_bytecode
            or dict(os.environ) != EXPECTED_ENV or cache.exists() or cache.is_symlink()
            or type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit)):
        raise ValueError('Exact isolated credential-free Mac reporting child required')
    sys.pycache_prefix = str(cache)
    violation = False; importing = True
    environment = dict(os.environ)
    ssh_prefix = ['ssh', '-F', '/dev/null', '-i', str(root/'.runtime/netcup/id_ed25519'),
        '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
        '-o', 'UserKnownHostsFile='+str(root/'.runtime/netcup/known_hosts'),
        '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-o', 'ClearAllForwardings=yes',
        '-o', 'RequestTTY=no', '-o', 'LogLevel=ERROR', 'root@62.83.32.126']
    def guard(event, args):
        nonlocal violation
        denied = event.startswith(('socket.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in {
            'os.system', 'os.fork', 'os.forkpty', 'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir',
            'os.link', 'os.symlink', 'os.truncate', 'os.chmod', 'os.chown', 'os.utime', 'shutil.copyfile'}
        if importing and event == 'socket.__new__':
            # A caught library capability probe creates no socket. Every other
            # refused effect permanently invalidates this one-shot child.
            raise RuntimeError('Socket capability denied before creation')
        if event == 'open':
            path, access, flags = args
            name = Path(os.fsdecode(path)).name if isinstance(path, (str, bytes, os.PathLike)) else ''
            writing = (isinstance(access, str) and any(c in access for c in 'wax+')
                or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)))
            transport_pipe = False
            if writing and mode == 'send' and not importing and type(path) is int:
                # Popen wraps its already-created stdin pipe with os.fdopen
                # BEFORE the subprocess audit event. This is not a file open
                # by pathname; the later exact SSH argv check still applies.
                try: transport_pipe = stat.S_ISFIFO(os.fstat(path).st_mode)
                except OSError: pass
            denied |= (name == '.env' or name.startswith('.env.') or name in {'.jwt_secret','id_ed25519','id_rsa'}
                or mode == 'prepare' and name == 'evidence.tar.gz'
                or writing and not transport_pipe)
        if event == 'os.putenv':
            key, value = map(os.fsdecode, args); denied |= environment.get(key) != value
        if event == 'os.unsetenv': denied = True
        if event == 'subprocess.Popen':
            argv = args[1]
            git = (isinstance(argv, (tuple,list)) and len(argv) >= 4
                and list(argv[:3]) == ['git','-C',str(root)] and argv[3] in ('show','rev-parse'))
            # /bin/ls argv has exactly executable, option, absolute path.
            acl = (isinstance(argv, (tuple,list)) and len(argv) == 3
                and list(argv[:2]) == ['/bin/ls','-lde'] and Path(argv[2]).is_absolute())
            ssh = (not importing and mode == 'send' and isinstance(argv, (tuple,list))
                and list(argv[:len(ssh_prefix)]) == ssh_prefix and len(argv) == len(ssh_prefix)+1)
            denied |= not (git or acl or ssh)
        if denied:
            violation = True
            raise PermissionError('Fixed Mac reporting child effect refused')
    sys.addaudithook(guard)
    def git(*args):
        p = subprocess.run(['git','-C',str(root),*args], capture_output=True, timeout=30,
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
        if p.returncode or p.stderr: raise ValueError('Committed child source unavailable')
        return p.stdout
    for ref in ('HEAD','origin/main'):
        if git('rev-parse',ref).decode().strip() != commit: raise ValueError('Current full committed main required')
    def seed(name):
        path = root/'stage2'/name
        if path.resolve() != path: raise ValueError('Canonical bootstrap source required')
        with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as handle:
            s = os.fstat(handle.fileno())
            if (not stat.S_ISREG(s.st_mode) or s.st_uid != os.getuid() or s.st_gid != os.getgid()
                    or s.st_nlink != 1 or s.st_mode & 0o7022 or s.st_size > 64*1024*1024):
                raise ValueError('Actual protected source-bound stdlib bootstrap required')
            raw = handle.read()
            if os.fstat(handle.fileno()) != s or path.lstat() != s: raise ValueError('Bootstrap identity changed')
        if raw != git('show',commit+':stage2/'+name): raise ValueError('Exact committed bootstrap bytes required')
        return raw
    stage = 'source_bootstrap'
    mac_raw = seed('mac_operator_files.py')
    own_raw = seed('no_cutoff_recovery_mac_bridge.py')
    # This separately verified stdlib object is intentionally not a project
    # import. Its actual bytes/origin are included in every parent/child check.
    mac = types.ModuleType('private_source_bound_darwin_io')
    mac.__file__ = str(root/'stage2/mac_operator_files.py')
    exec(compile(mac_raw,mac.__file__,'exec'),mac.__dict__)
    extras_node = next(n for n in ast.parse(own_raw).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id == 'EXTRAS' for t in n.targets))
    extra_names = set(ast.literal_eval(extras_node.value))
    def current():
        observed = {}
        for ref in ('HEAD','origin/main'):
            if git('rev-parse',ref).decode().strip() != commit: raise ValueError('Committed main changed')
        final_raw, final_id = mac.raw(root, FINAL_LITERAL, FINAL_SHA_LITERAL)
        final = mac.loads(final_raw)
        policy_raw = mac.raw(root,'stage2/no_cutoff_recovery_policy.py',private=False)[0]
        policy_node = next(n for n in ast.parse(policy_raw).body if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Name) and t.id == 'REQUIRED_SOURCE_FILES' for t in n.targets))
        names = set(final['sources']) | ast.literal_eval(policy_node.value.args[0])
        if set(expected) != names | extra_names: raise ValueError('Independent complete source union required')
        parent_names = {str((root/'stage2'/n).parent):False for n in expected}
        parent_names[str((root/FINAL_LITERAL).parent)] = True
        ancestry = {n:mac.directories(Path(n),private=p) for n,p in sorted(parent_names.items())}
        for n in sorted(expected):
            raw, identity = mac.raw(root,'stage2/'+n,expected[n],private=False)
            if raw != git('show',commit+':stage2/'+n): raise ValueError('Child source not committed')
            observed['stage2/'+n] = identity
        native = {n:expected[n] for n in sorted(names)}
        digest = hashlib.sha256(json.dumps(native,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        if digest != FROZEN_MAP_LITERAL or dict(os.environ) != environment or violation:
            raise ValueError('Exact unchanged R6/source/environment bindings required')
        if cache.exists() or cache.is_symlink() or sys.pycache_prefix != str(cache):
            raise ValueError('The isolated absent bytecode prefix changed')
        observed[FINAL_LITERAL] = final_id
        if ancestry != {n:mac.directories(Path(n),private=p) for n,p in sorted(parent_names.items())}:
            raise ValueError('Source/private ancestry changed during child read')
        observed['__actual_ancestry__'] = ancestry
        return observed, native
    stage = 'source_before_imports'
    before, native = current()
    sys.path.insert(0,str(root/'stage2'))
    with contextlib.redirect_stdout(sys.stderr):
        stage = 'project_imports'
        import no_cutoff_recovery_connection as connection
        importing = False
        connection.operator.loaded(root,native)
        stage = 'original_prepare'
        value, files = connection.prepare(commit)
        stage = 'prepared_identity_recheck'
        identities = connection._local_identities(value)
        connection.operator._current(value)
        if current() != (before,native): raise ValueError('Source or private identity changed during real preparation')
        if mode == 'send':
            output = _CommitTail(sys.__stdout__.buffer,connection.handoff.wire.COMMIT)
            stage = 'original_audit_archive'
            sent = connection.handoff.send(output)  # ALWAYS fresh original audit and SAME archive.
            stage = 'original_final_recheck'
            connection.operator._current(value)
            stage = 'amendment_final_recheck'
            if connection._local_identities(value) != identities or current() != (before,native):
                raise ValueError('Late handoff source/private drift; withhold commitment')
            connection.operator.loaded(root,native)
            stage = 'commitment'
            output.commit(sent['archive_sha256'])
            return
        stage = 'prepare_reply'
        local = dict(value['bindings']['local'])
        for mapping in (value['recovery_local'],value['publication']):
            connection.handoff.report._merge(local,mapping)
        if connection._local_identities(value) != identities: raise ValueError('Late original input identity changed')
        connection.operator.loaded(root,native)
    print(json.dumps(dict(kind='current_mac_recovery_metadata_not_admission',commit=commit,
        current_sources=native,native_files=files,local_files=local,local_identities=identities,
        native_operation=False,archive_read=False,paid_launch_ready=False),sort_keys=True,allow_nan=False))


def _program(value, mode):
    import mac_operator_files as mac
    if mode not in ('prepare', 'send'): raise ValueError('Fixed Mac metadata or real sender operation required')
    raw = mac.raw(REPO, 'stage2/no_cutoff_recovery_mac_bridge.py',
        value['bound']['no_cutoff_recovery_mac_bridge.py'], private=False)[0]
    tree = ast.parse(raw)
    pieces = [ast.get_source_segment(raw.decode(),n) for n in tree.body
        if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in (
            '_CommitTail','_valid_failure','_child_failure','_child')]
    if len(pieces) != 4: raise ValueError('Fixed committed child producer required')
    constants = dict(ROOT_LITERAL=str(REPO),EXPECTED_ENV=_environment(),FINAL_LITERAL=FINAL,
        FINAL_SHA_LITERAL=FINAL_SHA,FROZEN_MAP_LITERAL=FROZEN_MAP,
        FAILURE_PREFIX=FAILURE_PREFIX,CHILD_STAGES=CHILD_STAGES,CHILD_ERRORS=CHILD_ERRORS,
        TRANSPORT_STAGES=TRANSPORT_STAGES,VALIDATION_STAGES=VALIDATION_STAGES)
    prefix = '\n'.join(k+'='+repr(v) for k,v in constants.items())
    call = '_child('+','.join(map(repr,(mode,value['commit'],value['bound'])))+')'
    return prefix+'\n'+'\n\n'.join(pieces)+'\ntry:\n '+call+(
        '\nexcept BaseException as error:\n'
        ' try:\n'
        '  import json,os\n'
        '  record=_child_failure(error)\n'
        '  raw=FAILURE_PREFIX+json.dumps(record,sort_keys=True,allow_nan=False).encode()+b"\\n"\n'
        '  if _valid_failure(record) and len(raw)<=1024:\n'
        '   while raw:\n'
        '    count=os.write(2,raw)\n'
        '    if count<=0:break\n'
        '    raw=raw[count:]\n'
        ' except BaseException:pass\n'
        ' raise SystemExit(1) from None\n')


def _child_command(value, mode):
    return [str(PYTHON), '-I', '-B', '-c', _program(value,mode)]


def prepare(commit):
    import mac_operator_files as mac
    value = _source_state(commit); _loaded(value)
    result = subprocess.run(_child_command(value,'prepare'),capture_output=True,
        cwd=REPO,env=_environment(),timeout=TIMEOUT)
    if result.returncode: raise ValueError('Actual isolated original metadata preparation refused')
    record = mac.loads(result.stdout)
    if (set(record) != {'kind','commit','current_sources','native_files','local_files','local_identities',
            'native_operation','archive_read','paid_launch_ready'}
            or record['kind'] != 'current_mac_recovery_metadata_not_admission'
            or record['commit'] != commit or record['current_sources'] != value['current_sources']
            or any(record[n] is not False for n in ('native_operation','archive_read','paid_launch_ready'))):
        raise ValueError('Exact actual original reader metadata required')
    value.update(local_files=record['local_files'],
        local_identities={n:tuple(v) for n,v in record['local_identities'].items()},
        native_files=record['native_files'], local_ancestry=_ancestry(record['local_files']))
    expected = {'stage2/'+n:h for n,h in value['current_sources'].items()}
    from no_cutoff_recovery_bootstrap import QUALIFICATION
    expected[QUALIFICATION] = FINAL_SHA
    if record['native_files'] != expected: raise ValueError('Complete exact frozen native inputs required')
    current(value)
    return value, record['native_files']


def current(value):
    _loaded(value)
    if (_source_state(value['commit']) != {k:value[k] for k in (
                'commit','bound','current_sources','source_identities','source_ancestry')}
            or _identities(value['local_files']) != value['local_identities']
            or _ancestry(value['local_files']) != value['local_ancestry']):
        raise ValueError('Mac reporting source/private/identity drift')
    _loaded(value)


class _SenderFailure(ValueError):
    def __init__(self, diagnostic, returncode):
        if not _valid_failure(diagnostic) or type(returncode) is not int:
            raise ValueError('Exact bounded child failure metadata required')
        self.diagnostic = json.loads(json.dumps(diagnostic, allow_nan=False))
        self.returncode = returncode
        super().__init__('Actual original sender failed; preserve without retry')


def _sender_result(process):
    """Drain, discard and schema-filter stderr without retaining raw output."""
    deadline = time.monotonic() + TIMEOUT
    partial = bytearray(); dropping = False; record = None; invalid = False
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('Duplicate diagnostic field')
            value[key] = item
        return value
    def accept(raw):
        nonlocal record, invalid
        if not raw.startswith(FAILURE_PREFIX): return
        try:
            item = json.loads(raw[len(FAILURE_PREFIX):], object_pairs_hook=pairs)
            if not _valid_failure(item) or record is not None: raise ValueError('Untrusted diagnostic')
            record = item
        except (ValueError, TypeError, UnicodeError): invalid = True
    with selectors.DefaultSelector() as selected:
        fd = process.stderr.fileno(); os.set_blocking(fd, False)
        selected.register(fd, selectors.EVENT_READ)
        while selected.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise subprocess.TimeoutExpired('isolated Mac sender', TIMEOUT)
            for key, _ in selected.select(min(30, remaining)):
                try: raw = os.read(key.fd, 65536)
                except BlockingIOError: continue
                if not raw:
                    selected.unregister(key.fd); break
                for byte in raw:
                    if byte == 10:
                        if not dropping: accept(bytes(partial))
                        elif partial.startswith(FAILURE_PREFIX): invalid = True
                        partial.clear(); dropping = False
                    elif not dropping:
                        if len(partial) == 1024: dropping = True
                        else: partial.append(byte)
    if partial.startswith(FAILURE_PREFIX): invalid = True
    remaining = deadline - time.monotonic()
    if remaining <= 0: raise subprocess.TimeoutExpired('isolated Mac sender', TIMEOUT)
    code = process.wait(timeout=remaining)
    if code or record is not None or invalid:
        if record is None or invalid:
            record = dict(stage='unreported_child', error_class='OtherError', transport=None)
        raise _SenderFailure(record, code)


def send(value, stream):
    current(value)
    process = subprocess.Popen(_child_command(value,'send'),stdout=stream,stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,cwd=REPO,env=_environment())
    try:
        _sender_result(process)
        current(value)
    finally:
        if process.poll() is None:
            process.kill(); process.wait(timeout=30)  # Owned isolated Mac sender only, never native.
        process.stderr.close()

"""ONE exclusive OpenHands repeat installation, never qualification or replay.

The fixed native entry copies current protected runtime bytes on the same host.
The completed recovery audit/archive/export and a real fresh execution handoff
remain separate requirements. Nothing is installed into an earlier root.
"""
import ast
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import types

ROOT = Path('/opt/uts-capstone-matched-repeat-openhands-20260928')
ORIGINAL = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
REPORTER = Path('/opt/uts-capstone-custom-no-cutoff-final-reporting-20260929-r4')
STATE = '.runtime/netcup/matched-repeat-openhands-installation-20260930'
KIND = 'exclusive_baseline_installation_not_qualification'
SNAPSHOT = '.runtime/netcup/corrected-final-20260925/snapshot.json'
SNAPSHOT_SHA = '960a119ad8a6dc009884eb2b559712e0e48f0a16711ddf9d1c57399ee0aac244'
LAUNCH = 'stage2/results/baseline-corrected-20260923/launch.json'
LAUNCH_SHA = '0c8aafa10d744095c4551ff018065e1d6d9849e1dfe11bcf30e9e4b1ffafaaaa'
BASELINE_CSV = 'stage2/results/baseline-corrected-20260923/trials.csv'
BASELINE_CSV_SHA = '8769a865d19bc81132166d67f85a5fb84725f2cda8f5b2a45f98b1d9993d5429'
WINDOW = 64 * 1024 * 1024


def _sha(raw): return hashlib.sha256(raw).hexdigest()


def _json(value): return json.dumps(value, sort_keys=True, allow_nan=False).encode()


def _module(name, raw):
    value = types.ModuleType(name)
    exec(compile(raw, '<committed-' + name + '>', 'exec'), value.__dict__)
    return value


def _public():
    return {'stage2/results/custom-no-cutoff-final-20260928/' + n for n in (
        'qualification.json', 'registration-c0-nc.json', 'lineage.json', 'credit-policy.json',
        'c0-nc/summary.json', 'c0-nc/trials.json', 'c0-nc/trials.csv')}


def _payload(value):
    if (type(value) is not dict or set(value) != {'kind', 'commit', 'files', 'hashes', 'native', 'reporter'}
            or value['kind'] != KIND or type(value['commit']) is not str
            or not re.fullmatch('[a-f0-9]{40}', value['commit'])):
        raise ValueError('Exact committed baseline installation payload required')
    for key in ('files', 'hashes', 'native', 'reporter'):
        if type(value[key]) is not dict or not value[key]: raise ValueError('Complete installation maps required')
    if set(value['files']) != set(value['hashes']): raise ValueError('Complete source/input bytes required')
    for mapping in (value['hashes'], value['native'], value['reporter']):
        for name, digest in mapping.items():
            if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
                    or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))
                    or type(digest) is not str or not re.fullmatch('[a-f0-9]{64}', digest)):
                raise ValueError('Exact protected relative binding required')
    decoded = {n: base64.b64decode(v, validate=True) for n, v in value['files'].items()}
    if any(_sha(raw) != value['hashes'][n] for n, raw in decoded.items()):
        raise ValueError('Committed payload bytes changed')
    boot = _module('matched_repeat_execution_bootstrap', decoded['stage2/matched_repeat_execution_bootstrap.py'])
    seed = _module('no_cutoff_recovery_install', decoded['stage2/no_cutoff_recovery_install.py'])
    libraries = _module('no_cutoff_recovery_libraries', decoded['stage2/no_cutoff_recovery_libraries.py'])
    guard = _module('no_cutoff_final_guard', decoded['stage2/no_cutoff_final_guard.py'])
    if (boot.ROOTS['openhands'] != ROOT or seed.ORIGINAL != ORIGINAL or guard.ROOT != ORIGINAL
            or seed.ROOT != boot.RECOVERY or libraries.ORIGINAL != ORIGINAL or libraries.RECOVERY != boot.RECOVERY
            or value['hashes'].get(boot.BASELINE_INPUT) != boot.BASELINE_SHA
            or value['hashes'].get(boot.FINAL_INPUT) != boot.FINAL_SHA
            or value['hashes'].get(SNAPSHOT) != SNAPSHOT_SHA or value['hashes'].get(LAUNCH) != LAUNCH_SHA
            or value['hashes'].get(BASELINE_CSV) != BASELINE_CSV_SHA):
        raise ValueError('Fixed original/recovery/baseline identities required')
    final = boot.loads(decoded[boot.FINAL_INPUT])
    required = set(final['sources']) | boot._required(decoded['stage2/matched_repeat_policy.py'])
    if set(decoded) != {'stage2/' + n for n in required} | _public() | {
            boot.BASELINE_INPUT, boot.FINAL_INPUT, SNAPSHOT, LAUNCH, BASELINE_CSV}:
        raise ValueError('Complete original/current baseline inventory required')
    native = {'stage2/' + n: h for n, h in final['sources'].items()}
    native.update(final['evidence_files']); native[seed.ORIGINAL_QUALIFICATION] = boot.FINAL_SHA
    if any(value['native'].get(n) != h for n, h in native.items()):
        raise ValueError('Actual original sources and producer bindings required')
    return decoded, final, boot, seed, libraries, guard


def _lock_paths(seed, boot):
    early = [Path('/opt') / r / '.runtime/stage2' / n for r in seed.EARLY
        for n in ('matrix.lock', 'scored.lock', 'gateway.lock')]
    late = [Path('/opt') / r / '.runtime/stage2' / n for r in seed.LATE
        for n in ('matrix.lock', 'scored.lock', 'gateway.lock')]
    return tuple(early + [boot.RECOVERY / '.runtime/stage2/matrix.lock'] + late +
        [boot.RECOVERY / '.runtime/stage2' / n for n in ('scored.lock', 'gateway.lock')] +
        [base / '.runtime/stage2' / n for base in (boot.RETIRED, boot.RETIRED_SECOND)
            for n in ('matrix.lock','scored.lock','gateway.lock')] +
        [boot.root_for('terminus-2') / '.runtime/stage2' / n for n in ('matrix.lock','scored.lock','gateway.lock')])


@contextmanager
def _locked(seed, boot):
    held = []
    try:
        for path in _lock_paths(seed, boot):
            parents = boot.directories(path.parent, private=True)
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            try:
                info = os.fstat(fd); boot.acl(path)
                if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid()
                        or info.st_gid != os.getgid() or stat.S_IMODE(info.st_mode) != 0o600):
                    raise ValueError('Actual existing private baseline ancestor lock required')
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BaseException:
                os.close(fd); raise
            held.append((path, fd, boot.identity(info), parents))
        def check():
            for path, fd, identity, parents in held:
                if (boot.identity(os.fstat(fd)) != identity or boot.identity(path.lstat()) != identity
                        or boot.directories(path.parent, private=True) != parents):
                    raise ValueError('Baseline installation lock identity changed')
                boot.acl(path)
                other = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                try:
                    if boot.identity(os.fstat(other)) != identity: raise ValueError('Replaced ancestor lock')
                    try: fcntl.flock(other, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError: pass
                    else: raise ValueError('Baseline installation lock no longer held')
                finally: os.close(other)
        check(); yield check; check()
    finally:
        for _, fd, _, _ in reversed(held): os.close(fd)


def _completed_units(boot, files):
    """Only actual exited recovery services may remain active in systemd."""
    completed = boot.recovery_finished(); allowed = {completed['unit']}
    relative = '.runtime/stage2/no-cutoff-recovery-qualify-connection/'
    raw, identity = boot.raw(boot.RECOVERY, relative + 'intent.json')
    intent = boot.loads(raw); nonce = intent.get('nonce')
    if (type(nonce) is not str or not re.fullmatch('[a-f0-9]{32}', nonce)
            or intent.get('unit') != 'uts-recovery-qualify-' + nonce + '.service'
            or intent.get('root') != str(boot.RECOVERY) or intent.get('operator_commit') != boot.RECOVERY_COMMIT
            or intent.get('operation') != 'qualify-recovery'):
        raise ValueError('Exact actual recovery qualifier identity required')
    # The actual paid completion already required this qualifier in its live
    # session. Independently observe its retained manager invocation and PID.
    started_raw, started_id = boot.raw(boot.RECOVERY, relative + 'service-started.json')
    started = boot.loads(started_raw); process = started.get('native_process')
    if (type(process) is not dict or set(process) != {'pid', 'start_ticks'}
            or any(type(v) is not int or v <= 0 for v in process.values())):
        raise ValueError('Actual ended recovery qualifier process required')
    names = ('LoadState', 'ActiveState', 'SubState', 'MainPID', 'ExecMainPID', 'Result', 'ExecMainCode',
        'ExecMainStatus', 'InvocationID', 'Restart', 'NRestarts', 'Type', 'RemainAfterExit', 'WorkingDirectory')
    def manager():
        response = subprocess.check_output(['systemctl', 'show', intent['unit'], '--property=' + ','.join(names)],
            text=True, timeout=10)
        pairs = [line.split('=', 1) for line in response.splitlines() if '=' in line]
        state = dict(pairs)
        expected = dict(LoadState='loaded', ActiveState='active', SubState='exited', MainPID='0',
            ExecMainPID=str(process['pid']), Result='success', ExecMainCode='1', ExecMainStatus='0',
            InvocationID=started.get('invocation_id'), Restart='no', NRestarts='0', Type='exec',
            RemainAfterExit='yes', WorkingDirectory=str(boot.RECOVERY))
        if (len(pairs) != len(names) or state != expected or type(expected['InvocationID']) is not str
                or not re.fullmatch('[a-f0-9]{32}', expected['InvocationID'])):
            raise ValueError('Actual successful recovery qualifier unit required')
        return state
    state = manager(); path = Path('/proc') / str(process['pid']) / 'stat'
    try: parts = path.read_text().rpartition(') ')[2].split()
    except FileNotFoundError: parts = None
    if parts is not None and (len(parts) < 20 or not parts[19].isdigit() or int(parts[19]) == process['start_ticks']):
        raise ValueError('Recovery qualifier process remains active or uncertain')
    if (manager() != state or boot.raw(boot.RECOVERY, relative + 'intent.json') != (raw, identity)
            or boot.raw(boot.RECOVERY, relative + 'service-started.json') != (started_raw, started_id)):
        raise ValueError('Recovery completed service identity changed')
    allowed.add(intent['unit'])
    ended = boot.terminus_finished(files)
    allowed.update(v['unit'] for v in ended.values())
    return allowed


def _quiet(boot, seed, guard, files):
    guard.service(); allowed = _completed_units(boot, files)
    response = subprocess.check_output(['systemctl', 'list-units', '--type=service', '--state=active,activating',
        '--no-legend', '--plain', 'uts-*'], text=True, timeout=15)
    for line in response.splitlines():
        if not line.strip(): continue
        fields = line.split()
        if len(fields) < 4 or fields[0] not in allowed or fields[1:4] != ['loaded', 'active', 'exited']:
            raise ValueError('Active or uncertain study operation forbids baseline installation')
    roots = [str(Path('/opt') / n) for n in (*seed.EARLY, *seed.LATE)] + [str(boot.RECOVERY), str(ROOT), str(REPORTER), str(boot.root_for('terminus-2'))]
    for process in Path('/proc').iterdir():
        if not process.name.isdigit() or int(process.name) == os.getpid(): continue
        try:
            cwd = os.readlink(process / 'cwd'); argv = (process / 'cmdline').read_bytes().split(b'\0')
        except (FileNotFoundError, ProcessLookupError): continue
        if (any(cwd == r or cwd.startswith(r + '/') for r in roots)
                or any(any(a.startswith((r + '/.venv/bin/').encode()) for r in roots) for a in argv)):
            raise ValueError('Native process remains in an execution or reporting root')
    for args in (('ps', '-aq'), ('network', 'ls', '-q'), ('volume', 'ls', '-q')):
        if subprocess.check_output(['docker', *args, '--filter', 'name=uts-scored-'], text=True, timeout=15,
                env=dict(seed._environment(), DOCKER_HOST='unix:///var/run/docker.sock', DOCKER_CONFIG='/dev/null')).strip():
            raise ValueError('Owned study resources require inspection, never automatic removal')


def _old(value, decoded, boot, seed, libraries, guard, *, absent):
    seed._context()
    final = boot.loads(decoded[boot.FINAL_INPUT])
    names = set(final['sources']) | boot._required(decoded['stage2/matched_repeat_policy.py'])
    files = {'stage2/'+n:value['hashes']['stage2/'+n] for n in names}
    files.update({boot.BASELINE_INPUT:boot.BASELINE_SHA,boot.FINAL_INPUT:boot.FINAL_SHA})
    _quiet(boot, seed, guard, files)
    boot.directories(ROOT.parent)
    if absent and (ROOT.exists() or ROOT.is_symlink()): raise ValueError('Existing or partial baseline root is terminal')
    revision = _module('no_cutoff_recovery_revision', decoded['stage2/no_cutoff_recovery_revision.py'])
    if revision.ROOT != boot.RECOVERY: raise ValueError('Exact retained recovery revision required')
    observed = {'retained': revision.inspect(), 'recovery': boot._recovery_files(),
        'terminus':{n:boot.raw(boot.root_for('terminus-2'),n,h) for n,h in files.items()}}
    retired = _module('matched_repeat_revision', decoded['stage2/matched_repeat_revision.py'])
    if retired.ROOT != boot.RETIRED or retired.SECOND_ROOT != boot.RETIRED_SECOND:
        raise ValueError('Both exact terminal baseline roots required')
    observed['retired_baseline'] = retired.native(boot)
    for base, bindings in ((ORIGINAL, value['native']), (REPORTER, value['reporter'])):
        for name, digest in bindings.items():
            libraries.read(base, name, digest); observed[(str(base), name)] = libraries.identity((base / name).lstat())
    for base in (ORIGINAL, boot.RECOVERY, ROOT, boot.root_for('terminus-2'), Path('/opt/uts-capstone-corrected-20260923')):
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            path = base / '.runtime/stage2' / name
            if path.exists() or path.is_symlink(): raise ValueError('Persistent stop forbids baseline installation')
    return observed


def _runtime(boot, seed, libraries, decoded):
    dataset, trees = seed._runtime(boot, libraries, decoded)
    # The unchanged source-reader records an absolute in-root interpreter alias
    # relative to its own fixed destination. Rebase only that validated alias.
    for tree in trees:
        for item in tree['links'].values():
            target = Path(item['target'])
            if target.is_absolute() and target.is_relative_to(seed.ROOT):
                item['target'] = str(ROOT / target.relative_to(seed.ROOT))
    return dataset, trees


def _mkdir(path, boot, seed):
    if path == ROOT: boot.directories(path, private=True); return
    if not path.is_relative_to(ROOT): raise ValueError('Only own baseline installation directory may be created')
    if path.exists(): boot.directories(path); return
    _mkdir(path.parent, boot, seed)
    path.mkdir(mode=0o700); seed._sync(path.parent); boot.directories(path, private=True)


def _write(name, raw, boot, seed, mode=0o600):
    path = ROOT / seed._parts(name); _mkdir(path.parent, boot, seed)
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode), 'wb') as out:
        out.write(raw); out.flush(); os.fsync(out.fileno()); identity = boot.identity(os.fstat(out.fileno()))
    seed._sync(path.parent)
    if boot.identity(path.lstat()) != identity: raise ValueError('Exclusive installation output replaced')
    return identity


def _copy(name, expected, boot, seed, libraries):
    seed._input_read(ORIGINAL, name, libraries, expected['sha256'])
    path = ORIGINAL / name; target = ROOT / name
    if libraries.identity(path.lstat()) != expected['identity']: raise ValueError('Original input replaced')
    _mkdir(target.parent, boot, seed)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as inp:
        if libraries.identity(os.fstat(inp.fileno())) != expected['identity']: raise ValueError('Input replaced before copy')
        if name == '.venv/.lock': fcntl.flock(inp, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, expected['mode']), 'wb') as out:
            while chunk := inp.read(1024 * 1024): out.write(chunk)
            out.flush(); os.fsync(out.fileno()); identity = libraries.identity(os.fstat(out.fileno()))
        if libraries.identity(os.fstat(inp.fileno())) != expected['identity']: raise ValueError('Input changed during copy')
    seed._sync(target.parent); libraries.read(ROOT, name, expected['sha256'])
    seed._input_read(ORIGINAL, name, libraries, expected['sha256'])
    if libraries.identity(path.lstat()) != expected['identity'] or libraries.identity(target.lstat()) != identity:
        raise ValueError('Copied input/output identity replaced')
    return identity


def _installed(decoded, trees, created, boot, libraries):
    expected = set(created); directories = {''}
    for name in expected: directories.update(p.as_posix() for p in Path(name).parents if p.as_posix() != '.')
    for tree in trees: directories.update(tree['directories'])
    actual = set(); actual_directories = set()
    for current, children, names in os.walk(ROOT, followlinks=False):
        current = Path(current); relative = current.relative_to(ROOT).as_posix()
        actual_directories.add('' if relative == '.' else relative); boot.directories(current)
        for name in children + names:
            if (current / name).is_symlink(): actual.add((current / name).relative_to(ROOT).as_posix())
        children[:] = [n for n in children if not (current / n).is_symlink()]
        actual.update((current / n).relative_to(ROOT).as_posix() for n in names)
    if actual != expected or actual_directories != directories: raise ValueError('Exact baseline installed inventory required')
    for name, identity in created.items():
        if libraries.identity((ROOT / name).lstat()) != identity: raise ValueError('Installed file replaced')
    for name, raw in decoded.items(): libraries.read(ROOT, name, _sha(raw))
    for tree in trees:
        for name, item in tree['files'].items(): libraries.read(ROOT, name, item['sha256'])
        for name, item in tree['links'].items():
            if not (ROOT / name).is_symlink() or os.readlink(ROOT / name) != item['target']:
                raise ValueError('Installed interpreter alias changed')


def _install(value):
    decoded, final, boot, seed, libraries, guard = _payload(value)
    old = _old(value, decoded, boot, seed, libraries, guard, absent=True)
    interpreter = seed._interpreter(boot); dataset, trees = _runtime(boot, seed, libraries, decoded)
    if trees[-2]['files']['.runtime/stage2/python-runtime.tar.gz']['sha256'] != final['python_runtime']['sha256']:
        raise ValueError('Exact original Python distribution required')
    with _locked(seed, boot) as locks:
        if (_old(value, decoded, boot, seed, libraries, guard, absent=True) != old
                or _runtime(boot, seed, libraries, decoded) != (dataset, trees)
                or seed._interpreter(boot) != interpreter): raise ValueError('Native installation inputs changed')
        locks(); ROOT.mkdir(mode=0o700); seed._sync(ROOT.parent)
        root_id = boot.directories(ROOT, private=True); created = {}
        try:
            created['installation-intent.json'] = _write('installation-intent.json', _json(dict(kind=KIND,
                commit=value['commit'], started_utc=datetime.now(timezone.utc).isoformat(), automatic_resume=False)), boot, seed)
            for name, raw in sorted(decoded.items()): created[name] = _write(name, raw, boot, seed)
            for tree in trees:
                for name in tree['directories']: _mkdir(ROOT / name, boot, seed)
                for name, item in tree['files'].items(): created[name] = _copy(name, item, boot, seed, libraries)
                for name, item in tree['links'].items():
                    path = ROOT / name; _mkdir(path.parent, boot, seed); os.symlink(item['target'], path)
                    seed._sync(path.parent); created[name] = libraries.identity(path.lstat())
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                created['.runtime/stage2/' + name] = _write('.runtime/stage2/' + name, b'', boot, seed)
            created['source-commit.txt'] = _write('source-commit.txt', (value['commit'] + '\n').encode(), boot, seed)
            if (_old(value, decoded, boot, seed, libraries, guard, absent=False) != old
                    or _runtime(boot, seed, libraries, decoded) != (dataset, trees)
                    or seed._interpreter(boot) != interpreter): raise ValueError('Native evidence changed during installation')
            locks(); _installed(decoded, trees, created, boot, libraries)
            if boot.directories(ROOT, private=True) != root_id: raise ValueError('Installation root replaced')
            result = dict(kind=KIND, commit=value['commit'], root=str(ROOT), harness='openhands',
                sources_and_inputs=len(decoded), copied_current_files=sum(len(t['files']) for t in trees),
                precreated_locks=3, installed_utc=datetime.now(timezone.utc).isoformat(), original_roots_unchanged=True,
                historical_installed_bytes_attested=False, paid_launch_ready=False,
                repeat_execution_qualified=False, automatic_resume=False)
            created['installation-files.json'] = _write('installation-files.json', _json(dict(files=value['hashes'], runtime=[dict(
                files={n: v['sha256'] for n, v in t['files'].items()}, links={n: v['target'] for n, v in t['links'].items()},
                directories=t['directories']) for t in trees])), boot, seed)
            _installed(decoded, trees, created, boot, libraries)
            created['installation-result.json'] = _write('installation-result.json', _json(result), boot, seed)
            _installed(decoded, trees, created, boot, libraries); locks()
            return result
        except BaseException:
            path = ROOT / 'installation-failure.json'
            if not path.exists() and not path.is_symlink():
                _write('installation-failure.json', _json(dict(status='failed_or_uncertain_preserve_root',
                    automatic_resume=False, paid_launch_ready=False)), boot, seed)
            raise


def _entry(digest):
    raw = sys.stdin.buffer.read(WINDOW + 1)
    if len(raw) > WINDOW or _sha(raw) != digest: raise ValueError('Exact committed baseline payload required')
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ValueError('Duplicate installation field')
            result[key] = value
        return result
    def constant(_): raise ValueError('Nonfinite installation value')
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    print(json.dumps(_install(value), sort_keys=True, allow_nan=False), flush=True)


def prepare(commit):
    import matched_repeat_execution_connection as connection
    import matched_repeat_locks as locks
    import matched_repeat_original as original
    value, files = connection.prepare(commit, 'openhands')
    launch = connection.handoff.original.launch; boot = connection.boot
    hashes = {n: h for n, h in files.items() if n.startswith('stage2/')}
    hashes.update(connection.handoff.original.export.PREREQUISITES)
    hashes.update({connection.handoff.original.export.DESTINATION + '/' + n: h
        for n, h in connection.handoff.operator.recovery.policy.PUBLIC_FILES.items()})
    # These are exact already retained original178 anchors, not new audits.
    hashes.update({SNAPSHOT: SNAPSHOT_SHA, LAUNCH: LAUNCH_SHA, BASELINE_CSV: BASELINE_CSV_SHA})
    decoded = {n: launch._raw(n, h) for n, h in hashes.items()}
    for target, source, digest in ((boot.BASELINE_INPUT, connection.handoff.original.operator.old.ORIGINAL, boot.BASELINE_SHA),
            (boot.FINAL_INPUT, connection.handoff.original.operator.old.PRIVATE + '/.runtime/stage2/no-cutoff-final-qualification.json', boot.FINAL_SHA)):
        decoded[target] = launch._raw(source, digest); hashes[target] = digest
    payload = dict(kind=KIND, commit=commit, files={n: base64.b64encode(raw).decode() for n, raw in decoded.items()},
        hashes=hashes, native=value['bindings']['native'], reporter=value['bindings']['reporting'])
    _, _, _, seed, _, _ = _payload(payload)
    if (locks.paths(ROOT, 'openhands')[:-1] != _lock_paths(seed, boot)
            or original.SNAPSHOT != SNAPSHOT or original.SNAPSHOT_SHA256 != SNAPSHOT_SHA
            or original.PUBLIC + '/trials.csv' != BASELINE_CSV
            or original.policy.BASELINE_CSV_SHA256 != BASELINE_CSV_SHA):
        raise ValueError('Actual original snapshot and inherited lock order required')
    extra = {n: (launch._raw(n, hashes[n]), boot.identity((connection.REPO / n).lstat()))
        for n in (SNAPSHOT, LAUNCH, BASELINE_CSV)}
    connection._current(value)
    return value, payload, extra


def deploy(commit):
    """ONE fixed installation; uncertain/partial targets are never resumed."""
    import matched_repeat_execution_connection as connection
    from scored_gateway import durable_json
    value, payload, extra = prepare(commit); operator = connection.handoff.original
    launch = operator.launch; receiver = operator.receiver; boot = connection.boot
    state = connection.REPO / STATE
    if state.exists() or state.is_symlink(): raise ValueError('Existing baseline installation state is terminal')
    def current():
        connection._current(value)
        for name, saved in extra.items():
            if (launch._raw(name, payload['hashes'][name]), boot.identity((connection.REPO / name).lstat())) != saved:
                raise ValueError('Original178 copied anchor was replaced')
    # The existing helper independently checks every SSH option. Only its
    # interpreter tail is replaced with this committed fixed installer.
    args = connection.command('openhands', '0' * 32,
        {**{n: h for n, h in payload['hashes'].items() if n.startswith('stage2/')},
            boot.BASELINE_INPUT: boot.BASELINE_SHA, boot.FINAL_INPUT: boot.FINAL_SHA}, commit, 'qualify-repeat')
    source = launch._raw('stage2/matched_repeat_openhands_install.py', payload['hashes']['stage2/matched_repeat_openhands_install.py'])
    _, _, _, seed, _, _ = _payload(payload); raw = _json(payload)
    program = ('import base64\nexec(compile(base64.b64decode(' + repr(base64.b64encode(source).decode()) +
        '),"<committed-baseline-installer>","exec"))\ntry:\n _entry(' + repr(_sha(raw)) + ')\n'
        'except BaseException:\n raise SystemExit("Baseline installation refused; preserve partial evidence") from None\n')
    ast.parse(program)
    args = args[:-1] + [shlex.join(['/usr/bin/env', '-i', *(k + '=' + v for k, v in seed._environment().items()),
        str(ORIGINAL / '.venv/bin/python'), '-I', '-B', '-c', program])]
    current(); parents = receiver._parents(); state.mkdir(mode=0o700); receiver._sync(state.parent)
    directory = (parents, receiver._directory_id(state))
    durable_json(state / 'intent.json', dict(kind=KIND, commit=commit, payload_sha256=_sha(raw), automatic_resume=False))
    intent = (launch._raw(STATE + '/intent.json'), boot.identity((state / 'intent.json').lstat()))
    try:
        current(); receiver._state(state, directory)
        result = subprocess.run(args, input=raw, capture_output=True, timeout=1800,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        if result.returncode or len(result.stdout) > 16384: raise ValueError('Uncertain installation; inspect without retry')
        observed = boot.loads(result.stdout)
        if (observed.get('kind') != KIND or observed.get('commit') != commit or observed.get('root') != str(ROOT)
                or observed.get('harness') != 'openhands' or observed.get('paid_launch_ready') is not False
                or observed.get('repeat_execution_qualified') is not False or observed.get('automatic_resume') is not False):
            raise ValueError('Exact non-admitting baseline installation result required')
        current(); receiver._state(state, directory)
        if (intent != (launch._raw(STATE + '/intent.json'), boot.identity((state / 'intent.json').lstat()))
                or {p.name for p in state.iterdir()} != {'intent.json'}): raise ValueError('Installer operator evidence changed')
        durable_json(state / 'result.json', observed); return observed
    except BaseException:
        receiver._state(state, directory)
        durable_json(state / 'failure.json', dict(status='uncertain_inspect_native_without_retry', automatic_resume=False))
        raise

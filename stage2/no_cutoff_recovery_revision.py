"""Fixed execution-location amendment after an unstarted launch refusal.

The original plan and all three keys stay unchanged. The first installation
is retained, never patched or resumed. This stdlib-only reader authenticates
the actual old baseline manager invocation and the untouched unstarted tree.
It is not qualification, an archive audit or authority to repeat an attempt.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260930-r2')
RETIRED = Path('/opt/uts-capstone-custom-no-cutoff-recovery-20260929')
BASELINE = Path('/opt/uts-capstone-corrected-20260923')
COMMIT = 'c9b357c3a4dde44b04900ec8d6bc719981124a84'
SERVICE = 'uts-stage2-corrected-20260923.service'
REFUSED_UNIT = 'uts-recovery-qualify-c1a2783fc4f2d308300adb630415aedb.service'
BOOT = '3e30b45e3cf44d3f805689699574fb73'
INVOCATION = '399b6d0034d34aafb4858fe1e41d08c1'
EVENTS = (
    ('7d4958e842da4a758f6c1cdc7b36dcc5', '1790114328574818',
     '99c0e690a376976302c0afc7cc2935013a2fe86ced44fb50e40e6e6ce63bab0c'),
    ('39f53479d3a045ac8e11786248231fbf', '1790114328618033',
     '027228985581db2e263a279d6ae87aaf58f4197e757e27a0bfd0baaecf398136'),
    ('7ad2d189f7e94e70a38c781354912448', '1790298517125110',
     'c891aced25ccfa0c3bd7e7db74a4746dd8047ffb2bf1a7ca688848367eb3c63b'),
    ('ae8f7b866b0347b9af31fe1c80b127c0', '1790298517125572',
     '5b2a629234771a9a7d59a9b7a8a68e0cc80154508684410a9f5a4799de068755'))
RECORDS = {
    'installation-intent.json': 'fa47b9124983b7ead60c6b3f921cc3e748f5a6c259bdf35e9633c3acd1ec7160',
    'installation-files.json': 'f5b66b7bf45747d59f7556c2368f344c6d56a833a7f9aa9c93290db304e5f316',
    'installation-result.json': 'c4bafa52f4ef146b6b1cb6c54e9abb00aa31c89b77da4aa6822e651eb5ab9a69',
    'source-commit.txt': '2927c7aca7991b21428dc60549ab10fb3bd9402160bd2f509914ba17654a799b'}
SOURCE_MAP = '936adc773d85fddda9e1be464e269bdd6515e171b25d4cb7d9659863a8714a0a'
OPERATOR_STATES = {
    '.runtime/netcup/custom-no-cutoff-recovery-installation-20260930-r2': {
        'intent.json': '466c4814d29b689b0139462e34537f2cc89e6f920c927f6c6cbb8f9587740b8f',
        'result.json': RECORDS['installation-result.json']},
    '.runtime/netcup/custom-no-cutoff-recovery-qualify-20260929': {
        'intent.json': '3de257fd2a19a1ed27f0a18488b31d697161be6974cfe48fc716e97a047cc768',
        'failure.json': '80c50f1549f0625058c82b2a136822a5b63e4783b0134ecb37dbeb8da227fca4'}}
OWNER = GROUP = 0
PROC = Path('/proc')
CGROUP = Path('/sys/fs/cgroup/system.slice')
WINDOW = 64 * 1024 * 1024  # Metadata framing only, not a task limit.
ENV = {'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'}


def _fail():
    raise ValueError('Actual baseline completion and unchanged unstarted installation required')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value: _fail()
        value[key] = item
    return value


def _loads(raw):
    def nonfinite(_): _fail()
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=nonfinite)
    if type(value) is not dict: _fail()
    return value


def _relative(name):
    if (type(name) is not str or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))):
        _fail()
    return name


def _acl(path):
    if not hasattr(os, 'listxattr') or any(n in {'system.posix_acl_access', 'system.posix_acl_default'}
            for n in os.listxattr(path, follow_symlinks=False)):
        _fail()


def _directories(path, private=False):
    answer = []
    for p in (*reversed(path.parents), path):
        s = p.lstat(); _acl(p)
        if (p.resolve() != p or not stat.S_ISDIR(s.st_mode) or s.st_uid not in {0, OWNER}
                or s.st_gid not in {0, GROUP} or s.st_mode & 0o7022
                or p == path and private and stat.S_IMODE(s.st_mode) != 0o700):
            _fail()
        answer.append((str(p), s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid))
    return tuple(answer)


def _read(name, expected):
    p = RETIRED / _relative(name); parents = _directories(p.parent)
    with os.fdopen(os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno()); _acl(p)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_uid != OWNER
                or before.st_gid != GROUP or before.st_mode & 0o7022
                or (name.startswith('.runtime/') or name in RECORDS) and stat.S_IMODE(before.st_mode) != 0o600
                or before.st_size > WINDOW):
            _fail()
        raw = stream.read(WINDOW + 1); after = os.fstat(stream.fileno())
    if (len(raw) > WINDOW or _sha(raw) != expected or _identity(before) != _identity(after)
            or _identity(after) != _identity(p.lstat()) or _directories(p.parent) != parents):
        _fail()
    return raw, _identity(after)


def _command(args):
    try: value = subprocess.run(args, capture_output=True, text=True, timeout=30, env=dict(ENV))
    except (OSError, subprocess.SubprocessError): _fail()
    if value.returncode or len(value.stdout.encode('utf-8')) > WINDOW: _fail()
    return value.stdout


def _state(unit):
    raw = _command(['systemctl', 'show', unit,
        '--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus'])
    if any('=' not in line for line in raw.splitlines()): _fail()
    state = _pairs(line.split('=', 1) for line in raw.splitlines())
    if (state.get('LoadState') not in ('loaded', 'not-found') or state != dict(
            LoadState=state.get('LoadState'), ActiveState='inactive', SubState='dead',
            MainPID='0', ExecMainStatus='0')):
        _fail()
    if unit == REFUSED_UNIT and state['LoadState'] != 'not-found': _fail()
    return state


def _journal():
    fields = '__REALTIME_TIMESTAMP,_PID,_UID,_COMM,_BOOT_ID,SYSLOG_IDENTIFIER,UNIT,INVOCATION_ID,MESSAGE_ID,JOB_TYPE,JOB_RESULT,MESSAGE'
    raw = _command(['journalctl', '--no-pager', '--output=json', '--output-fields=' + fields,
        '_PID=1', '_UID=0', '_COMM=systemd', 'SYSLOG_IDENTIFIER=systemd', 'UNIT=' + SERVICE])
    rows = [_loads(line) for line in raw.splitlines()]
    if len(rows) != len(EVENTS): _fail()
    for row, (event, when, digest) in zip(rows, EVENTS):
        expected = dict(_PID='1', _UID='0', _COMM='systemd', _BOOT_ID=BOOT,
            SYSLOG_IDENTIFIER='systemd', UNIT=SERVICE, INVOCATION_ID=INVOCATION,
            MESSAGE_ID=event, __REALTIME_TIMESTAMP=when)
        if (any(row.get(k) != v for k, v in expected.items())
                or type(row.get('MESSAGE')) is not str or _sha(row['MESSAGE'].encode()) != digest):
            _fail()
    if (rows[0].get('JOB_TYPE') != 'start' or rows[1].get('JOB_TYPE') != 'start'
            or rows[1].get('JOB_RESULT') != 'done'
            or rows[2]['MESSAGE'] != SERVICE + ': Deactivated successfully.'):
        _fail()


def _processes():
    for unit in (SERVICE, REFUSED_UNIT):
        if (CGROUP / unit).exists() or (CGROUP / unit).is_symlink(): _fail()
    for path in PROC.iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid(): continue
        try:
            groups = (path / 'cgroup').read_text()
            if not groups.splitlines() or any(not re.fullmatch(r'[0-9]+:[^:\n]*:/[^\n]*', n) for n in groups.splitlines()): _fail()
            parts = [part for line in groups.splitlines() for part in line.split(':')[-1].split('/')]
            if any(unit in parts for unit in (SERVICE, REFUSED_UNIT)): _fail()
            for key in ('cwd', 'exe'):
                try: target = os.readlink(path / key).removesuffix(' (deleted)')
                except FileNotFoundError: continue
                if any(target == str(root) or target.startswith(str(root) + '/') for root in (BASELINE, RETIRED)): _fail()
        except FileNotFoundError: continue  # Process exited during observation.
        except OSError: _fail()
    for unit in (SERVICE, REFUSED_UNIT):
        if (CGROUP / unit).exists() or (CGROUP / unit).is_symlink(): _fail()


def baseline():
    """Fresh trusted manager/procfs observation; not-found defaults never suffice."""
    if sys.platform != 'linux' or os.getuid() != OWNER or os.getgid() != GROUP: _fail()
    before = _directories(BASELINE / '.runtime/stage2', True)
    if ((PROC / '1/comm').read_text().strip() != 'systemd'
            or (PROC / 'sys/kernel/random/boot_id').read_text().strip().replace('-', '') != BOOT):
        _fail()
    states = {unit: _state(unit) for unit in (SERVICE, REFUSED_UNIT)}
    _journal(); _processes()
    for name in ('operator-stop-request.json', 'provider-stop.json'):
        p = BASELINE / '.runtime/stage2' / name
        if p.exists() or p.is_symlink(): _fail()
    if (_directories(BASELINE / '.runtime/stage2', True) != before
            or {unit: _state(unit) for unit in states} != states):
        _fail()
    return states


def retained():
    """Reread original installed sources and exact unused tree, without credentials.

    Retired runtime payloads are inventoried/identity-checked, not read: they
    supply no current library or paid admission proof. The new root has its own
    full actual library comparison. No old archive or credential is opened.
    """
    root = _directories(RETIRED, True)
    _directories(RETIRED / '.runtime/stage2', True)
    records = {n: _read(n, h) for n, h in RECORDS.items()}
    inventory = _loads(records['installation-files.json'][0])
    if set(inventory) != {'files', 'runtime'} or type(inventory['files']) is not dict: _fail()
    sources = inventory['files']
    if len(sources) != 321 or _sha(json.dumps(sources, sort_keys=True, allow_nan=False).encode()) != SOURCE_MAP: _fail()
    identities = {n: _read(n, h)[1] for n, h in sources.items()}
    expected = set(sources) | set(RECORDS) | {'.runtime/stage2/' + n for n in ('matrix.lock', 'scored.lock', 'gateway.lock')}
    links = {}; directories = {''}
    if type(inventory['runtime']) is not list: _fail()
    for tree in inventory['runtime']:
        if type(tree) is not dict or set(tree) != {'files', 'links', 'directories'}: _fail()
        for name in tree['files']: expected.add(_relative(name))
        for name, target in tree['links'].items():
            name = _relative(name)
            if name in links or type(target) is not str: _fail()
            links[name] = target; expected.add(name)
        directories.update(_relative(n) for n in tree['directories'])
    for name in expected:
        directories.update(p.as_posix() for p in Path(name).parents if p.as_posix() != '.')
    actual = {}; actual_directories = {}
    for current, children, names in os.walk(RETIRED, followlinks=False):
        current = Path(current); relative = current.relative_to(RETIRED).as_posix()
        actual_directories['' if relative == '.' else relative] = _directories(current)
        for name in list(children) + names:
            p = current / name; key = p.relative_to(RETIRED).as_posix(); s = p.lstat(); _acl(p)
            if stat.S_ISDIR(s.st_mode): continue
            if key in links:
                if (not stat.S_ISLNK(s.st_mode) or os.readlink(p) != links[key]
                        or s.st_uid != OWNER or s.st_gid != GROUP or s.st_nlink != 1): _fail()
            elif (not stat.S_ISREG(s.st_mode) or s.st_uid != OWNER or s.st_gid != GROUP
                    or s.st_nlink != 1 or s.st_mode & 0o7022): _fail()
            if key == '.env' or key.startswith('.runtime/'):
                if not stat.S_ISREG(s.st_mode) or stat.S_IMODE(s.st_mode) != 0o600: _fail()
            actual[key] = _identity(s)
        children[:] = [n for n in children if not (current / n).is_symlink()]
    if set(actual) != expected or set(actual_directories) != directories: _fail()
    for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
        raw, identity = _read('.runtime/stage2/' + name, _sha(b''))
        if raw or actual['.runtime/stage2/' + name] != identity: _fail()
    if any(actual[n] != identity for n, identity in identities.items()): _fail()
    for name, record in records.items():
        if _read(name, RECORDS[name]) != record: _fail()
    for name, identity in actual.items():
        if _identity((RETIRED / name).lstat()) != identity: _fail()
    for name, identity in actual_directories.items():
        if _directories(RETIRED / name) != identity: _fail()
    if _directories(RETIRED, True) != root: _fail()
    return dict(files=actual, directories=actual_directories)


def inspect():
    before = baseline()
    first = retained()
    if baseline() != before or retained() != first: _fail()
    return dict(kind='recovery_execution_location_amendment_not_admission',
        execution_root=str(ROOT), retained_unstarted_root=str(RETIRED),
        original_plan_unchanged=True, retained_installation_attempts_started=0,
        retained_identity=first, paid_launch_ready=False)

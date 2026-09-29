"""Narrow completed-final compatibility guard, standard library only.

Fresh trusted manager/procfs evidence is required even for an unloaded unit.
Only the exact frozen root may retain its protected mode-0664 public files.
No writes, caller-selected service, saved-proof admission or permission edits.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys

ROOT = Path('/opt/uts-capstone-custom-no-cutoff-final-20260928')
SERVICE = 'uts-stage2-custom-no-cutoff-final-20260928.service'
OWNER = 0
GROUP = 0
BOOT = '3e30b45e3cf44d3f805689699574fb73'
INVOCATION = 'f3ac8546674e4a889c307b3238faa78c'
START = '1790566666855537'
END = '1790651706030353'
START_ID = '39f53479d3a045ac8e11786248231fbf'
SUCCESS_ID = '7ad2d189f7e94e70a38c781354912448'
USAGE_ID = 'ae8f7b866b0347b9af31fe1c80b127c0'
ENVIRONMENT = dict(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
    LANG='C.UTF-8', DOCKER_HOST='unix:///var/run/docker.sock', DOCKER_CONFIG='/dev/null',
    LITELLM_LOCAL_MODEL_COST_MAP='True')
PROC = Path('/proc')
CGROUP = Path('/sys/fs/cgroup/system.slice') / SERVICE
WINDOW = 1024 * 1024  # Manager metadata only; not a benchmark/request bound.


def _fail():
    raise ValueError('Exact retained final success and protected execution evidence required')


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid, s.st_nlink,
        s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def _acl(path):
    if not hasattr(os, 'listxattr'):
        _fail()
    if any(n in ('system.posix_acl_access', 'system.posix_acl_default')
            for n in os.listxattr(path, follow_symlinks=False)):
        _fail()


def protected_path(root, name):
    """Fresh protection identity for the ONE frozen root, else no exception."""
    if Path(root) != ROOT:
        return ()
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or any(p in ('', '.', '..') for p in name.split('/'))):
        _fail()
    saved = []
    for directory in (ROOT.parent, ROOT):
        s = directory.lstat()
        if (directory.is_symlink() or directory.resolve() != directory or not stat.S_ISDIR(s.st_mode)
                or s.st_uid != OWNER or s.st_gid != GROUP or s.st_mode & 0o7022
                or directory == ROOT and stat.S_IMODE(s.st_mode) != 0o700):
            _fail()
        _acl(directory); saved.append((str(directory), identity(s)))
    current = ROOT
    public = name == 'stage2' or name.startswith('stage2/')
    for part in name.split('/'):
        current /= part
        try:
            s = current.lstat()
        except FileNotFoundError:
            break  # True absence is still checked separately by each consumer.
        if stat.S_ISLNK(s.st_mode) or s.st_uid != OWNER or s.st_gid != GROUP:
            _fail()
        _acl(current)
        if stat.S_ISDIR(s.st_mode):
            if s.st_mode & (0o7002 if public else 0o7022):
                _fail()
            saved.append((str(current), identity(s)))
    return tuple(saved)


def protected_file(root, name, info, *, private=False):
    """No group-write exception for private files or for any other root."""
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or info.st_uid != os.getuid() or info.st_mode & 0o7000):
        _fail()
    private = private or name.startswith('.runtime/')
    if Path(root) == ROOT:
        protected_path(root, name)
        if info.st_uid != OWNER or info.st_gid != GROUP:
            _fail()
        mask = 0o077 if private else 0o002 if name.startswith('stage2/') else 0o022
    else:
        mask = 0o077 if private else 0o022
    if info.st_mode & mask:
        _fail()


def _pairs(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            _fail()
        value[key] = item
    return value


def _command(args):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=20, env=dict(ENVIRONMENT))
    except (OSError, subprocess.SubprocessError):
        _fail()
    if result.returncode or len(result.stdout) > WINDOW:
        _fail()
    return result.stdout


def _state():
    raw = _command(['systemctl', 'show', SERVICE,
        '--property=LoadState,ActiveState,SubState,MainPID,ExecMainStatus'])
    if any('=' not in line for line in raw.splitlines()):
        _fail()
    state = _pairs([line.split('=', 1) for line in raw.splitlines()])
    if (state.get('LoadState') not in ('loaded', 'not-found') or state != dict(
            LoadState=state.get('LoadState'), ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0')):
        _fail()
    return state


def _journal():
    fields = '__REALTIME_TIMESTAMP,_PID,_UID,_COMM,_BOOT_ID,SYSLOG_IDENTIFIER,UNIT,INVOCATION_ID,MESSAGE_ID,JOB_TYPE,JOB_RESULT,MESSAGE'
    raw = _command(['journalctl', '--no-pager', '--output=json', '--output-fields=' + fields,
        '_PID=1', '_UID=0', '_COMM=systemd', 'SYSLOG_IDENTIFIER=systemd', 'UNIT=' + SERVICE])
    records = []
    for line in raw.splitlines():
        try:
            value = json.loads(line, object_pairs_hook=_pairs)
        except (ValueError, UnicodeError):
            _fail()
        trusted = dict(_PID='1', _UID='0', _COMM='systemd', _BOOT_ID=BOOT,
            SYSLOG_IDENTIFIER='systemd', UNIT=SERVICE, INVOCATION_ID=INVOCATION)
        if not isinstance(value, dict) or any(value.get(k) != v for k, v in trusted.items()):
            _fail()
        records.append(value)
    if (len(records) != 3 or [r.get('MESSAGE_ID') for r in records] != [START_ID, SUCCESS_ID, USAGE_ID]
            or records[0].get('__REALTIME_TIMESTAMP') != START
            or records[0].get('JOB_TYPE') != 'start' or records[0].get('JOB_RESULT') != 'done'
            or records[1].get('__REALTIME_TIMESTAMP') != END
            or records[1].get('MESSAGE') != SERVICE + ': Deactivated successfully.'
            or not isinstance(records[2].get('__REALTIME_TIMESTAMP'), str)
            or not records[2]['__REALTIME_TIMESTAMP'].isdigit()
            or not int(END) <= int(records[2]['__REALTIME_TIMESTAMP']) <= int(END) + 1000000):
        _fail()


def _processes():
    # No environment, command arguments, task logs or model text is read.
    # A missing original cgroup is required, not default systemctl exit fields.
    if CGROUP.exists() or CGROUP.is_symlink():
        _fail()
    for path in PROC.iterdir():
        if not path.name.isdigit() or int(path.name) == os.getpid():
            continue
        try:
            groups = (path / 'cgroup').read_text()
            if not groups.splitlines() or any(not re.fullmatch(r'[0-9]+:[^:\n]*:/[^\n]*', line) for line in groups.splitlines()):
                _fail()
            if SERVICE in [part for line in groups.splitlines() for part in line.split(':')[-1].split('/')]:
                _fail()
            for key in ('cwd', 'exe'):
                try:
                    target = os.readlink(path / key).removesuffix(' (deleted)')
                except FileNotFoundError:
                    continue  # Kernel thread or process that has exited.
                if target == str(ROOT) or target.startswith(str(ROOT) + '/'):
                    _fail()
        except FileNotFoundError:
            continue  # The observed process exited during this read.
        except OSError:
            _fail()
    if CGROUP.exists() or CGROUP.is_symlink():
        _fail()


def completion_metadata():
    """Expected schema only. This pure value is NEVER native proof."""
    return dict(kind='trusted_manager_invocation_and_procfs_absence_v1', boot_id=BOOT,
        invocation_id=INVOCATION, started_realtime_us=START, completed_realtime_us=END,
        success_message_id=SUCCESS_ID, manager_success_message_matched=True,
        service_cgroup_absent=True, other_execution_processes=0)


def validate_service(value):
    """Schema validation only; live consumers must call service() themselves."""
    if not isinstance(value, dict):
        _fail()
    expected = dict(LoadState=value.get('LoadState'), ActiveState='inactive', SubState='dead',
        MainPID='0', ExecMainStatus='0', completion=completion_metadata())
    if (value.get('LoadState') not in ('loaded', 'not-found')
            or json.dumps(value, sort_keys=True) != json.dumps(expected, sort_keys=True)):
        _fail()


def service():
    """Fresh fixed native observation, not a collector or dispatch authority."""
    try:
        if sys.platform != 'linux' or os.getuid() != OWNER:
            _fail()
        before = protected_path(ROOT, '.runtime/stage2')
        if ((PROC / '1/comm').read_text().strip() != 'systemd'
                or (PROC / 'sys/kernel/random/boot_id').read_text().strip().replace('-', '') != BOOT):
            _fail()
        state = _state(); _journal(); _processes()
        if _state() != state or protected_path(ROOT, '.runtime/stage2') != before:
            _fail()
        for name in ('operator-stop-request.json', 'provider-stop.json'):
            path = ROOT / '.runtime/stage2' / name
            protected_path(ROOT, '.runtime/stage2/' + name)
            if path.exists() or path.is_symlink():
                _fail()
        return dict(state, completion=completion_metadata())
    except (OSError, ValueError):
        _fail()


def source(expected):
    """Byte-bound stdlib source for pre-import checks in existing interpreters."""
    path = Path(__file__)
    if path.is_symlink() or path.name != 'no_cutoff_final_guard.py':
        _fail()
    raw = path.read_bytes()
    if not isinstance(expected, str) or hashlib.sha256(raw).hexdigest() != expected:
        _fail()
    return raw

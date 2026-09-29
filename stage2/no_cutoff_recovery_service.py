"""Detached recovery prerequisite inspection, not qualification or dispatch.

Only the pinned operator relay supplies the live stream. This service opens and
consumes its own session on one main-thread async task. No saved handle crosses
the process boundary. Any existing/partial operation is terminal, not resumed.
"""
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import selectors
import socket
import stat
import struct
import subprocess
import sys
import time

import no_cutoff_recovery_bootstrap as boot
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_session as session

ROOT = handoff.ROOT
OPERATION = 'inspect-recovery-prerequisites'
STATE = '.runtime/stage2/no-cutoff-recovery-prerequisite-connection'
TIMEOUT = handoff.launch.transport.HANDOFF_SECONDS
REPLY_LIMIT = 16384
RUN_BASE = Path('/run')


def identity(nonce):
    if type(nonce) is not str or not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('Exact recovery connection nonce required')
    return 'uts-recovery-inspect-' + nonce + '.service'


def loaded(files):
    handoff.operator.loaded(ROOT, {n[7:]: h for n, h in files.items() if n.startswith('stage2/')})


def check(files, identities):
    if boot.VIOLATION: raise ValueError('Latched bootstrap effect refusal')
    boot.check(files, identities); loaded(files)
    if Path(__file__).absolute() != ROOT / 'stage2/no_cutoff_recovery_service.py':
        raise ValueError('Own fixed native recovery service required')


def folder():
    value = ROOT / STATE
    boot.directories(value, private=True)
    return value


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def save(path, value):
    before = boot.directories(path.parent, private=True)
    # Serialise before exclusive creation: no arbitrary default=str payloads.
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode('utf-8') + b'\n'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        if stream.write(raw) != len(raw): raise ValueError('Incomplete private connection record')
        stream.flush(); os.fsync(stream.fileno()); written = boot.identity(os.fstat(stream.fileno()))
    _sync(path.parent)
    if boot.directories(path.parent, private=True) != before:
        raise ValueError('Connection evidence directory replaced')
    if boot.raw(ROOT, path.relative_to(ROOT).as_posix()) != (raw, written):
        raise ValueError('Durable connection record changed before verification')
    return raw


def base(nonce, files, commit):
    if type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Full committed recovery revision required')
    return dict(operation=OPERATION, nonce=nonce, unit=identity(nonce), root=str(ROOT),
        experiment=policy.EXPERIMENT, condition=policy.CONDITION, operator_commit=commit,
        bindings_sha256=policy.fingerprint(files), automatic_resume=False,
        paid_launch_ready=False, recovery_execution_qualified=False)


def process_identity(pid):
    if type(pid) is not int or pid <= 0: raise ValueError('Actual peer PID required')
    proc = Path('/proc') / str(pid)
    def read():
        parts = (proc / 'stat').read_text().rpartition(') ')[2].split()
        status = dict(line.split(':', 1) for line in (proc / 'status').read_text().splitlines() if ':' in line)
        if (len(parts) < 20 or not parts[19].isdigit()
                or status.get('Uid', '').split() != ['0'] * 4 or status.get('Gid', '').split() != ['0'] * 4
                or os.readlink(proc / 'cwd') != str(ROOT)
                or os.readlink(proc / 'exe') != str((ROOT / '.venv/bin/python').resolve())):
            raise ValueError('Exact native recovery peer executable/owner/directory required')
        return dict(pid=pid, start_ticks=int(parts[19]))
    first = read()
    if read() != first: raise ValueError('Peer process identity changed')
    return first


def _peer(connection):
    if not hasattr(socket, 'SO_PEERCRED'): raise ValueError('Linux peer credentials required')
    pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if pid <= 0 or uid != 0 or gid != 0: raise ValueError('Private root-owned peer required')
    return process_identity(pid)


def _service_process(unit):
    def manager():
        raw = subprocess.check_output(['systemctl', 'show', unit,
            '--property=LoadState,ActiveState,SubState,MainPID,InvocationID'], text=True, timeout=10)
        entries = [line.split('=', 1) for line in raw.splitlines() if '=' in line]
        value = dict(entries)
        if (len(entries) != 5 or set(value) != {'LoadState', 'ActiveState', 'SubState', 'MainPID', 'InvocationID'}
                or value['LoadState'] != 'loaded' or value['ActiveState'] != 'active' or value['SubState'] != 'running'
                or not value['MainPID'].isdigit() or not re.fullmatch('[a-f0-9]{32}', value['InvocationID'])):
            raise ValueError('Actual running detached service required')
        return value
    state = manager(); observed = process_identity(int(state['MainPID']))
    if manager() != state: raise ValueError('Service identity changed')
    return observed


def endpoint(nonce):
    identity(nonce); boot.directories(RUN_BASE)
    return RUN_BASE / ('uts-rc-' + nonce) / 'input.sock'


def _socket_identity(path):
    parents = boot.directories(path.parent, private=True); s = path.lstat(); boot.acl(path)
    if (not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.getuid() or s.st_gid != os.getgid()
            or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) != 0o600):
        raise ValueError('Exclusive private native socket required')
    return parents, boot.identity(s)


def service_command(nonce, files, commit, relay_process):
    from no_cutoff_recovery_connection import native_program
    path = folder(); program = native_program(nonce, files, commit, role='service', relay_process=relay_process)
    return ['systemd-run', '--quiet', '--unit=' + identity(nonce), '--property=Type=exec',
        '--property=WorkingDirectory=' + str(ROOT), '--property=UMask=0077', '--property=Restart=no',
        '--property=StandardInput=null', '--property=StandardOutput=append:' + str(path / 'service.log'),
        '--property=StandardError=inherit', '/usr/bin/env', '-i',
        *(k + '=' + v for k, v in boot.environment().items()),
        str(ROOT / '.venv/bin/python'), '-I', '-B', '-c', program]


def _line(value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode() + b'\n'
    if len(raw) > REPLY_LIMIT: raise ValueError('Connection acknowledgement exceeds metadata window')
    return raw


def _reply(connection, value):
    raw = _line(value)
    try: connection.sendall(raw)
    except OSError: pass  # Durable success survives client acknowledgement loss.


def _read_reply(stream):
    raw = stream.readline(REPLY_LIMIT + 1)
    if len(raw) > REPLY_LIMIT or not raw.endswith(b'\n') or stream.read(1):
        raise ValueError('Exact single native acknowledgement and EOF required')
    return boot.loads(raw)


def _failure(path, name, expected):
    save(path / name, dict(expected, status='uncertain_preserve_evidence_inspect_without_retry'))


def relay(nonce, files, commit, identities):
    """One pinned SSH operation; never signal or retry the detached service."""
    check(files, identities); boot.ancestors(files); check(files, identities)
    handoff.wire.pipe_only(sys.stdin.buffer)
    expected = base(nonce, files, commit); path = ROOT / STATE
    boot.directories(path.parent, private=True)
    path.mkdir(mode=0o700); _sync(path.parent)  # Existing/partial state is terminal.
    folder_id = boot.directories(path, private=True)
    sock = listener = None; socket_id = None
    try:
        relay_process = process_identity(os.getpid())
        save(path / 'intent.json', dict(expected, relay_process=relay_process,
            created_utc=datetime.now(timezone.utc).isoformat()))
        fd = os.open(path / 'service.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd); _sync(path)
        sock = endpoint(nonce); sock.parent.mkdir(mode=0o700)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(sock)); sock.chmod(0o600); socket_id = _socket_identity(sock)
        listener.listen(1); listener.settimeout(TIMEOUT)
        boot.ancestors(files); check(files, identities)
        argv = service_command(nonce, files, commit, relay_process)
        check(files, identities)
        subprocess.run(argv, check=True,
            capture_output=True, timeout=30, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        with listener.accept()[0] as connection:
            listener.close(); peer = _peer(connection)
            if peer != _service_process(expected['unit']) or _socket_identity(sock) != socket_id:
                raise ValueError('Socket peer is not the exact systemd service process')
            ready = dict(expected, kind='recovery_receiver_ready_not_authenticated', native_process=peer)
            sys.stdout.buffer.write(_line(ready)); sys.stdout.buffer.flush()
            deadline = time.monotonic() + TIMEOUT
            with selectors.DefaultSelector() as selector:
                selector.register(sys.stdin.buffer, selectors.EVENT_READ)
                while True:
                    left = deadline - time.monotonic()
                    if left <= 0 or not selector.select(left): raise ValueError('Recovery transfer timed out')
                    raw = os.read(sys.stdin.buffer.fileno(), handoff.wire.CHUNK)
                    if not raw: break
                    connection.settimeout(max(0.001, deadline - time.monotonic())); connection.sendall(raw)
            connection.shutdown(socket.SHUT_WR); connection.settimeout(TIMEOUT)
            with connection.makefile('rb') as incoming: result = _read_reply(incoming)
            if boot.directories(path, private=True) != folder_id:
                raise ValueError('Native operation directory changed')
            sys.stdout.buffer.write(_line(result)); sys.stdout.buffer.flush()
    except BaseException:
        _failure(path, 'relay-failure.json', expected)
        raise
    finally:
        if listener is not None: listener.close()
        # Remove only the socket and directory whose exclusive identities are
        # still ours. Replacements/partial unknown state are retained untouched.
        if socket_id is not None and _socket_identity(sock) == socket_id:
            sock.unlink(); sock.parent.rmdir()


async def inspect_session(nonce, files, commit, identities, incoming, connection, path, intent_raw):
    expected = base(nonce, files, commit)
    state = boot.directories(path, private=True)
    retained = {n: boot.raw(ROOT, STATE + '/' + n) for n in ('intent.json', 'service-started.json', 'service.log')}
    if retained['intent.json'][0] != intent_raw: raise ValueError('Native intent changed before session')
    with session.open_session(incoming) as active:
        live = session._live(active)
        document = handoff._live(live['witness'])['header']['operator']
        policy._same(document['operator_commit'], commit)
        record = session.recheck(active)
        policy._same(record['files'], files)
        check(files, identities)
        raw = save(path / 'prerequisites.json', record)
        # A later normal-exit refusal must never leave a success result/ack.
        # This file alone is explicitly non-admitting intermediate evidence.
        prior = record['predecessor']
        result = dict(expected, kind='recovery_prerequisites_checked_not_dispatch',
            native_process=process_identity(os.getpid()), prerequisites_sha256=hashlib.sha256(raw).hexdigest(),
            operator_document_sha256=prior['operator_document_sha256'],
            archive_sha256=prior['streamed_backup']['sha256'])
    # Both handles are now invalid and the mandatory context-exit recheck passed.
    # No service/host observation occurs after that final evidence reread.
    check(files, identities)
    if (boot.directories(path, private=True) != state
            or any(boot.raw(ROOT, STATE + '/' + n) != saved for n, saved in retained.items())
            or boot.raw(ROOT, STATE + '/prerequisites.json')[0] != raw
            or {p.name for p in path.iterdir()} != {'intent.json', 'service.log', 'prerequisites.json', 'service-started.json'}):
        raise ValueError('Late retained recovery inspection evidence drift')
    save(path / 'result.json', result)
    _reply(connection, result)
    return result


def serve(nonce, files, commit, identities, relay_process):
    """The systemd process, not the relay, owns one real main-task session."""
    expected = base(nonce, files, commit); check(files, identities)
    path = folder(); intent_raw = boot.raw(ROOT, STATE + '/intent.json')[0]
    intent = boot.loads(intent_raw)
    if (set(intent) != set(expected) | {'relay_process', 'created_utc'}
            or {k: intent[k] for k in expected} != expected or intent['relay_process'] != relay_process):
        raise ValueError('Exact durable native connection intent required')
    handoff.archive._utc(intent['created_utc'])
    if {p.name for p in path.iterdir()} != {'intent.json', 'service.log'}:
        raise ValueError('Existing/partial native inspection cannot be restarted')
    # This exclusive start is the one-shot service gate; no ancestor locks are
    # acquired until actual archive authentication/audits inside open_session.
    save(path / 'service-started.json', dict(expected, native_process=process_identity(os.getpid())))
    try:
        if _service_process(expected['unit']) != process_identity(os.getpid()):
            raise ValueError('Inspection must run in the actual detached unit MainPID')
        sock = endpoint(nonce); socket_id = _socket_identity(sock)
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(TIMEOUT); connection.connect(str(sock))
            if _peer(connection) != relay_process or _socket_identity(sock) != socket_id:
                raise ValueError('Native service peer is not the original SSH relay process')
            check(files, identities)
            with connection.makefile('rb') as incoming:
                asyncio.run(inspect_session(nonce, files, commit, identities, incoming, connection, path, intent_raw))
    except BaseException:
        _failure(path, 'failure.json', expected)
        raise

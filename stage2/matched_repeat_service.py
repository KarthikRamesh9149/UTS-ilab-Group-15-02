"""One-shot detached prerequisite inspection, never a study/qualification run.

The pinned SSH relay creates a private listener before starting the systemd
service. Both ends check the local peer's PID/UID. The service, not the SSH
relay, authenticates the streamed archive and owns the locked session. Once a
complete committed transfer reaches it, loss of the SSH client cannot move or
invalidate that process-local session. No callbacks, saved-session input,
restart, paid command or generic executable interface are supported.
"""
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import struct
import subprocess
import sys

import matched_repeat_policy as policy
import matched_repeat_session as session
import matched_repeat_stream as wire
from matched_repeat_baseline_probe import check_files
from run_credit_only import hold
from scored_gateway import durable_json, private_directory

OPERATION = 'inspect-prerequisites'
TRANSPORT_SECONDS = 900  # Connection/transfer window, never a task deadline.
REPLY_LIMIT = 16384
RUN_BASE = Path('/run')


def identity(harness, nonce):
    session.handoff._first(harness)
    if not isinstance(nonce, str) or not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('Fresh exact connection identity required')
    return 'uts-matched-repeat-' + harness + '-inspect-' + nonce + '.service'


def _context(root, harness, bindings):
    root = session._context(root, harness)
    if os.getuid() != 0 or Path(__file__).resolve() != root / 'stage2/matched_repeat_service.py':
        raise ValueError('Use the root-owned native connection implementation')
    session.handoff._no_stop(root)
    if session._inputs(root)[2] != bindings:
        raise ValueError('Native connection bytes differ from the actual operator bindings')
    check_files(root, bindings)
    return root


def _control(root, nonce, *, create=False):
    parent = root / '.runtime/stage2/matched-repeat-connections'
    if parent.is_symlink() or parent.resolve() != parent:
        raise ValueError('Regular private connection directory required')
    if not create and not parent.is_dir():
        raise ValueError('Existing private connection directory required')
    private_directory(parent)
    folder = parent / nonce
    if create:
        folder.mkdir(mode=0o700)  # Exclusive intent: never replace/retry this operation.
    if folder.is_symlink() or folder.resolve() != folder or not folder.is_dir():
        raise ValueError('Existing private connection intent required')
    private_directory(folder)
    return folder


def _socket_path(nonce):
    if RUN_BASE.resolve() != RUN_BASE or RUN_BASE.is_symlink() or not RUN_BASE.is_dir():
        raise ValueError('Regular native runtime directory required')
    return RUN_BASE / ('uts-mr-' + nonce) / 'input.sock'


def _peer(connection):
    # Linux SO_PEERCRED identifies the local service/SSH-relay process. It is
    # not a substitute for the operator's pinned network SSH connection.
    if not hasattr(socket, 'SO_PEERCRED'):
        raise ValueError('Native Linux peer credentials required')
    pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if pid <= 0 or uid != 0 or gid != 0:
        raise ValueError('Expected root-owned local transport peer')
    return pid


def _reply(connection, value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode() + b'\n'
    if len(raw) > REPLY_LIMIT:
        raise ValueError('Connection reply exceeds metadata window')
    try:
        connection.sendall(raw)
    except OSError:
        # The durable local result remains authoritative after SSH disconnect.
        # Never stop or re-create a session because its acknowledgement failed.
        pass


def _read_reply(stream):
    raw = stream.readline(REPLY_LIMIT + 1)
    if not raw.endswith(b'\n') or len(raw) > REPLY_LIMIT or stream.read(1):
        raise ValueError('Exact single native acknowledgement required')
    return wire.loads(raw)


def _service_pid(unit, root):
    raw = subprocess.check_output(['systemctl', 'show', unit,
        '--property=LoadState,ActiveState,SubState,MainPID'], text=True, timeout=10)
    value = dict(line.split('=', 1) for line in raw.splitlines() if '=' in line)
    if (value.get('LoadState') != 'loaded' or value.get('ActiveState') != 'active'
            or value.get('SubState') != 'running' or not value.get('MainPID', '').isdigit()):
        raise ValueError('Detached inspection service is not running')
    pid = int(value['MainPID'])
    if pid <= 0 or os.readlink('/proc/' + str(pid) + '/cwd') != str(root):
        raise ValueError('Detached inspection service has the wrong process directory')
    return pid


def service_command(root, harness, nonce, bindings, relay_pid):
    """Fixed inspection command, with no inherited provider environment."""
    from matched_repeat_connection import native_program
    folder = _control(root, nonce)
    program = native_program(harness, nonce, bindings, role='service', relay_pid=relay_pid)
    # No --pipe/--scope/--wait, SSH parent, restart, RuntimeMaxSec or task limit.
    return ['systemd-run', '--quiet', '--unit=' + identity(harness, nonce), '--property=Type=exec',
        '--property=WorkingDirectory=' + str(root), '--property=UMask=0077', '--property=Restart=no',
        '--property=StandardInput=null', '--property=StandardOutput=append:' + str(folder / 'service.log'),
        '--property=StandardError=inherit', '/usr/bin/env', '-i', 'PATH=/usr/bin:/bin',
        'LANG=C.UTF-8', 'DO_NOT_TRACK=1', 'LITELLM_LOCAL_MODEL_COST_MAP=True',
        str(root / '.venv/bin/python'), '-I', '-B', '-c', program]


def relay(root, harness, nonce, bindings):
    """Only the source-checked command over the existing pinned SSH path."""
    unit = identity(harness, nonce); root = _context(root, harness, bindings)
    wire.pipe_only(sys.stdin.buffer)
    folder = _control(root, nonce, create=True)
    intent = dict(operation=OPERATION, nonce=nonce, unit=unit, root=str(root), harness=harness,
        bindings_sha256=policy.fingerprint(bindings), relay_pid=os.getpid(),
        created_utc=datetime.now(timezone.utc).isoformat(), paid_launch_ready=False)
    durable_json(folder / 'intent.json', intent)
    # The private log is created before systemd opens it. No transfer bytes are
    # ever written here; native failures print only a sanitised status.
    descriptor = os.open(folder / 'service.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    endpoint = _socket_path(nonce)
    endpoint.parent.mkdir(mode=0o700)  # Exclusive and shorter than AF_UNIX's path limit.
    listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        listener.bind(str(endpoint)); endpoint.chmod(0o600)
        listener.listen(1); listener.settimeout(TRANSPORT_SECONDS)
        check_files(root, bindings); session.handoff._no_stop(root)
        subprocess.run(service_command(root, harness, nonce, bindings, os.getpid()), check=True,
            capture_output=True, timeout=30, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        with listener.accept()[0] as connection:
            listener.close()
            pid = _peer(connection)
            if pid != _service_pid(unit, root):
                raise ValueError('Socket peer is not the actual detached service MainPID')
            ready = dict(kind='matched_repeat_receiver_ready_not_authenticated', operation=OPERATION,
                nonce=nonce, unit=unit, root=str(root), harness=harness, native_pid=pid,
                bindings_sha256=policy.fingerprint(bindings), paid_launch_ready=False)
            print(json.dumps(ready, sort_keys=True), flush=True)
            connection.settimeout(TRANSPORT_SECONDS)
            while True:
                raw = sys.stdin.buffer.read(wire.CHUNK)
                if not raw:
                    break
                connection.sendall(raw)
            connection.shutdown(socket.SHUT_WR)
            with connection.makefile('rb') as incoming:
                result = _read_reply(incoming)
            print(json.dumps(result, sort_keys=True), flush=True)
    finally:
        listener.close()
        # Only this operation's exclusively created ephemeral socket is removed.
        # Intent/log/result evidence is retained, including every failure.
        if not endpoint.is_symlink() and endpoint.exists() and stat.S_ISSOCK(endpoint.lstat().st_mode):
            endpoint.unlink()
        if not endpoint.parent.is_symlink():
            endpoint.parent.rmdir()


async def _inspect(root, harness, nonce, bindings, incoming, connection, folder):
    # Opening inside this coroutine keeps the session and future async consumer
    # in the same task. No asyncio.run/fork/thread handoff may occur inside it.
    with session.open_session(root, harness, incoming) as active:
        record = session.recheck(active)
        check_files(root, bindings)
        durable_json(folder / 'prerequisites.json', record)
        raw = (folder / 'prerequisites.json').read_bytes()
        predecessor = record['predecessor']
        result = dict(kind='matched_repeat_prerequisites_checked_not_dispatch', operation=OPERATION,
            nonce=nonce, unit=identity(harness, nonce), root=str(root), harness=harness, native_pid=os.getpid(),
            bindings_sha256=policy.fingerprint(bindings), prerequisites_sha256=hashlib.sha256(raw).hexdigest(),
            operator_document_sha256=predecessor['operator_document_sha256'],
            archive_sha256=predecessor['streamed_backup']['sha256'], paid_launch_ready=False)
        durable_json(folder / 'result.json', result)
        _reply(connection, result)
        # A future paid runner must be explicitly implemented inside this live
        # scope. This inspection operation never calls a fixture or dispatcher.


def serve(root, harness, nonce, bindings, relay_pid):
    """Detached systemd process owns the actual authentication/session."""
    identity(harness, nonce); root = _context(root, harness, bindings)
    if type(relay_pid) is not int or relay_pid <= 0:
        raise ValueError('Exact SSH relay process identity required')
    folder = _control(root, nonce)
    intent_path = session.regular(root, str((folder / 'intent.json').relative_to(root)))
    intent = wire.loads(intent_path.read_bytes())
    expected = dict(operation=OPERATION, nonce=nonce, unit=identity(harness, nonce), root=str(root),
        harness=harness, bindings_sha256=policy.fingerprint(bindings), relay_pid=relay_pid,
        paid_launch_ready=False)
    if any(policy.fingerprint(intent.get(k)) != policy.fingerprint(v) for k, v in expected.items()):
        raise ValueError('Actual connection intent differs from this service')
    endpoint = _socket_path(nonce)
    private_directory(endpoint.parent)
    if (endpoint.is_symlink() or not stat.S_ISSOCK(endpoint.lstat().st_mode)
            or endpoint.stat().st_uid != os.getuid() or endpoint.stat().st_mode & 0o077):
        raise ValueError('Private root-owned relay socket required')
    try:
        with ExitStack() as stack:
            # This independent connection lock is not an ancestor/matrix lock;
            # the real collectors remain free to acquire their own chain first.
            hold(stack, root / '.runtime/stage2', 'matched-repeat-connection.lock')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(TRANSPORT_SECONDS); connection.connect(str(endpoint))
                if _peer(connection) != relay_pid:
                    raise ValueError('Connected peer is not the exact SSH relay process')
                with connection.makefile('rb') as incoming:
                    asyncio.run(_inspect(root, harness, nonce, bindings, incoming, connection, folder))
    except BaseException:
        durable_json(folder / 'failure.json', dict(operation=OPERATION, nonce=nonce,
            status='inspection_failed_preserve_evidence', paid_launch_ready=False))
        raise

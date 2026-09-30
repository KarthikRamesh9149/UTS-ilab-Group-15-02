"""Fixed detached inspection, qualification and three-cell recovery operations.

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
OPERATIONS = {OPERATION: 'inspect', 'qualify-recovery': 'qualify', 'run-recovery': 'run'}
TIMEOUT = handoff.launch.transport.HANDOFF_SECONDS
REPLY_LIMIT = 16384
RUN_BASE = Path('/run')


def operation_state(operation):
    if type(operation) is not str or operation not in OPERATIONS:
        raise ValueError('Only a fixed recovery service operation is accepted')
    return STATE if operation == OPERATION else '.runtime/stage2/no-cutoff-recovery-' + OPERATIONS[operation] + '-connection'


def identity(nonce, operation=OPERATION):
    operation_state(operation)
    if type(nonce) is not str or not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('Exact recovery connection nonce required')
    return 'uts-recovery-' + OPERATIONS[operation] + '-' + nonce + '.service'


def loaded(files):
    handoff.operator.loaded(ROOT, {n[7:]: h for n, h in files.items() if n.startswith('stage2/')})


def check(files, identities):
    if boot.VIOLATION: raise ValueError('Latched bootstrap effect refusal')
    boot.check(files, identities); loaded(files)
    if Path(__file__).absolute() != ROOT / 'stage2/no_cutoff_recovery_service.py':
        raise ValueError('Own fixed native recovery service required')


def folder(operation=OPERATION):
    value = ROOT / operation_state(operation)
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


def base(nonce, files, commit, operation=OPERATION):
    if type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Full committed recovery revision required')
    return dict(operation=operation, nonce=nonce, unit=identity(nonce, operation), root=str(ROOT),
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


def _execution_manager(unit):
    names = ('LoadState', 'ActiveState', 'SubState', 'MainPID', 'InvocationID',
        'Result', 'ExecMainCode', 'ExecMainStatus', 'ExecMainPID', 'NRestarts',
        'Restart', 'Type', 'RemainAfterExit', 'WorkingDirectory')
    raw = subprocess.check_output(['systemctl', 'show', unit,
        '--property=' + ','.join(names)], text=True, timeout=10)
    entries = [line.split('=', 1) for line in raw.splitlines() if '=' in line]
    value = dict(entries)
    if (len(entries) != len(names) or set(value) != set(names)
            or value['LoadState'] != 'loaded' or value['Restart'] != 'no'
            or value['Type'] != 'exec' or value['RemainAfterExit'] != 'yes'
            or value['WorkingDirectory'] != str(ROOT) or value['NRestarts'] != '0'
            or not re.fullmatch('[a-f0-9]{32}', value['InvocationID'])):
        raise ValueError('Actual retained one-shot recovery unit required')
    return value


def _execution_start(unit, process):
    value = _execution_manager(unit)
    if (value['ActiveState'] != 'active' or value['SubState'] != 'running'
            or value['MainPID'] != str(process['pid'])
            or value['ExecMainPID'] != str(process['pid'])
            or process_identity(process['pid']) != process
            or _execution_manager(unit) != value):
        raise ValueError('Exact running recovery service invocation required')
    return value['InvocationID']


def _process_ended(process):
    path = Path('/proc') / str(process['pid']) / 'stat'
    try: parts = path.read_text().rpartition(') ')[2].split()
    except FileNotFoundError: return
    if len(parts) < 20 or not parts[19].isdigit() or int(parts[19]) == process['start_ticks']:
        raise ValueError('Recovery service process has not verifiably ended')


def _transport_failure(path, expected):
    """A late lost SSH acknowledgement cannot invalidate committed native work."""
    marker = path / 'relay-failure.json'
    if not marker.exists() and not marker.is_symlink(): return {}
    raw, item = boot.raw(ROOT, marker.relative_to(ROOT).as_posix())
    policy._same(boot.loads(raw), dict(expected, status='uncertain_preserve_evidence_inspect_without_retry'))
    return {'relay-failure.json': (raw, item)}


def _completed_operation(files, commit, operation):
    """Actual manager/process completion plus durable bytes in the live scope.

    RemainAfterExit retains metadata, not a running job. A missing unit, an
    accepted handoff alone or producer completion before service exit refuses.
    """
    if operation not in ('qualify-recovery', 'run-recovery'):
        raise ValueError('Fixed completed execution operation required')
    import no_cutoff_recovery_files as evidence
    path = folder(operation); relative = operation_state(operation)
    directory_id = boot.directories(path, private=True)
    names = {'intent.json', 'service-started.json', 'service.log', 'prerequisites.json', 'accepted.json', 'result.json'}
    raw, _ = boot.raw(ROOT, relative + '/intent.json'); intent = boot.loads(raw)
    # A later documentation/export commit may leave all installed source bytes
    # identical. Preserve the actual earlier operation revision, while requiring
    # its complete source/private binding map to equal this current live reader.
    # Startup itself still requires live handoff revision == operation revision.
    expected = base(intent.get('nonce'), files, intent.get('operator_commit'), operation)
    retained = {name: boot.raw(ROOT, relative + '/' + name) for name in names if name != 'service.log'}
    if retained['intent.json'][0] != raw: raise ValueError('Completion intent changed')
    records = {name: boot.loads(value[0]) for name, value in retained.items()}
    if set(intent) != set(expected) | {'relay_process', 'created_utc'}:
        raise ValueError('Exact operation intent required')
    for key, value in expected.items(): policy._same(intent[key], value)
    handoff.archive._utc(intent['created_utc'])
    started = records['service-started.json']; process = started.get('native_process')
    if (type(process) is not dict or set(process) != {'pid', 'start_ticks'}
            or any(type(v) is not int or v <= 0 for v in process.values())):
        raise ValueError('Retained native process identity required')
    invocation = started.get('invocation_id')
    if type(invocation) is not str or not re.fullmatch('[a-f0-9]{32}', invocation):
        raise ValueError('Actual start invocation identity required')
    policy._same(started, dict(expected, native_process=process, invocation_id=invocation))
    prerequisites = records['prerequisites.json']; policy._same(prerequisites['files'], files)
    prior = prerequisites['predecessor']
    accepted = dict(expected, kind='recovery_handoff_committed_operation_accepted_not_completed',
        native_process=process, prerequisites_sha256=hashlib.sha256(retained['prerequisites.json'][0]).hexdigest(),
        operator_document_sha256=prior['operator_document_sha256'], archive_sha256=prior['streamed_backup']['sha256'])
    policy._same(records['accepted.json'], accepted)
    terminal = policy.QUALIFIER_RESULT_FILE
    if operation == 'run-recovery':
        import run_no_cutoff_recovery as runner
        terminal = runner.RESULT
    result = records['result.json']
    if set(result) != set(expected) | {'kind', 'terminal_files', 'log_files', 'completed_utc'}:
        raise ValueError('Exact completed service record required')
    for key, value in expected.items(): policy._same(result[key], value)
    policy._same(result['kind'], 'recovery_service_operation_finished_not_completed_study_audit')
    handoff.archive._utc(result['completed_utc'])
    if (set(result['terminal_files']) != {'.runtime/stage2/' + terminal}
            or set(result['log_files']) != {relative + '/service.log'}):
        raise ValueError('Exact actual service terminal and log bindings required')
    retained.update(_transport_failure(path, expected))
    names |= set(retained)
    bound, identities = evidence.capture(ROOT, {relative + '/' + n for n in names})
    for name, digest in {**result['terminal_files'], **result['log_files']}.items():
        policy._hash(digest)
        if name in bound: policy._same(bound[name], digest)
        bound[name] = digest
    identities = evidence.extend(ROOT, bound, identities)
    manager = _execution_manager(expected['unit'])
    if (manager['InvocationID'] != invocation or manager['ActiveState'] != 'active'
            or manager['SubState'] != 'exited' or manager['MainPID'] != '0'
            or manager['ExecMainPID'] != str(process['pid']) or manager['Result'] != 'success'
            or manager['ExecMainCode'] != '1' or manager['ExecMainStatus'] != '0'):
        raise ValueError('Native operation has not successfully exited')
    _process_ended(process)
    if _execution_manager(expected['unit']) != manager:
        raise ValueError('Completed unit identity changed during read')
    # No native observation after final protected evidence rereads.
    evidence.check(ROOT, files)
    evidence.check(ROOT, bound, identities)
    if (boot.directories(path, private=True) != directory_id
            or {p.name for p in path.iterdir()} != names
            or any(boot.raw(ROOT, relative + '/' + n) != value for n, value in retained.items())):
        raise ValueError('Completed operation evidence changed or contains failure/partial state')
    return dict(files=bound, identities=identities, paid_launch_ready=False)


def completed_operation(active, operation):
    live = session._live(active)
    if live['root'] != ROOT: raise ValueError('Own native recovery session required')
    commit = handoff._live(live['witness'])['header']['operator']['operator_commit']
    return _completed_operation(live['inputs']['files'], commit, operation)


def operation_status(files, commit, identities, operation):
    """Read-only fixed metadata, no archive, collector, locks or saved authority."""
    if operation not in ('qualify-recovery', 'run-recovery'):
        raise ValueError('Only fixed execution status is supported')
    check(files, identities)
    path = folder(operation); relative = operation_state(operation)
    intent_raw, intent_id = boot.raw(ROOT, relative + '/intent.json')
    intent = boot.loads(intent_raw)
    expected = base(intent.get('nonce'), files, intent.get('operator_commit'), operation)
    for key, value in expected.items(): policy._same(intent.get(key), value)
    started_raw, started_id = boot.raw(ROOT, relative + '/service-started.json')
    started = boot.loads(started_raw)
    state = _execution_manager(expected['unit'])
    if state['InvocationID'] != started.get('invocation_id'):
        raise ValueError('Observed unit is not the retained execution invocation')
    completed = None
    if state['ActiveState'] == 'active' and state['SubState'] == 'exited':
        completed = _completed_operation(files, commit, operation)
        status = 'service_exited_successfully_not_completed_study_audit'
    elif state['ActiveState'] == 'active' and state['SubState'] == 'running':
        if _service_process(expected['unit']) != started.get('native_process'):
            raise ValueError('Observed running process differs from retained start')
        status = 'running'
    else:
        status = 'uncertain_or_failed_preserve_evidence_no_retry'
    counts = dict(study=policy.EXPERIMENT, intended=3, started=0, completed=0,
        passed=0, failed=0, missing_verifier=0, active_tasks=[])
    retained = {}
    for ordinal, task, _ in policy.plan.TARGETS:
        trial_id = f'customrecovery1-c0-nc-{ordinal:02d}-{task}'
        records = {}
        for name in ('started.json', 'result.json'):
            relative_name = '.runtime/stage2/scored-trials/' + trial_id + '/' + name
            item = ROOT / relative_name
            if item.exists() or item.is_symlink():
                raw, file_id = boot.raw(ROOT, relative_name); record = boot.loads(raw)
                for key, value in dict(trial_id=trial_id, task_id=task, recovery_experiment=policy.EXPERIMENT,
                        harness=policy.CONDITION, stage='final').items(): policy._same(record.get(key), value)
                records[name] = record; retained[relative_name] = (raw, file_id)
        if 'result.json' in records and 'started.json' not in records:
            raise ValueError('A retained result requires its actual start')
        if 'started.json' in records:
            counts['started'] += 1
            if 'result.json' not in records: counts['active_tasks'].append(ordinal)
        if 'result.json' in records:
            counts['completed'] += 1
            reward = ((records['result.json'].get('verifier_result') or {}).get('rewards') or {}).get('reward')
            if reward is None: counts['missing_verifier'] += 1
            elif type(reward) in (int, float) and reward in (0, 1): counts['passed' if reward == 1 else 'failed'] += 1
            else: raise ValueError('Unexpected recovery verifier outcome')
    check(files, identities)
    if (boot.raw(ROOT, relative + '/intent.json') != (intent_raw, intent_id)
            or boot.raw(ROOT, relative + '/service-started.json') != (started_raw, started_id)
            or any(boot.raw(ROOT, name) != value for name, value in retained.items())):
        raise ValueError('Status evidence changed during observation')
    if completed:
        import no_cutoff_recovery_files as evidence
        evidence.check(ROOT, completed['files'], completed['identities'])
    return dict(kind='read_only_recovery_operation_status_not_admission', operation=operation,
        status=status, unit=expected['unit'], counts=counts, observed_utc=datetime.now(timezone.utc).isoformat(),
        paid_launch_ready=False, automatic_resume=False)


def endpoint(nonce):
    identity(nonce); boot.directories(RUN_BASE)
    return RUN_BASE / ('uts-rc-' + nonce) / 'input.sock'


def _socket_identity(path):
    parents = boot.directories(path.parent, private=True); s = path.lstat(); boot.acl(path)
    if (not stat.S_ISSOCK(s.st_mode) or s.st_uid != os.getuid() or s.st_gid != os.getgid()
            or s.st_nlink != 1 or stat.S_IMODE(s.st_mode) != 0o600):
        raise ValueError('Exclusive private native socket required')
    return parents, boot.identity(s)


def service_command(nonce, files, commit, relay_process, operation=OPERATION):
    from no_cutoff_recovery_connection import native_program
    path = folder(operation)
    program = native_program(nonce, files, commit, role='service', relay_process=relay_process, operation=operation)
    return ['systemd-run', '--quiet', '--unit=' + identity(nonce, operation), '--property=Type=exec',
        *([] if operation == OPERATION else ['--property=RemainAfterExit=yes']),
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


def relay(nonce, files, commit, identities, operation=OPERATION):
    """One pinned SSH operation; never signal or retry the detached service."""
    check(files, identities); boot.ancestors(files); check(files, identities)
    handoff.wire.pipe_only(sys.stdin.buffer)
    expected = base(nonce, files, commit, operation); path = ROOT / operation_state(operation)
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
        argv = service_command(nonce, files, commit, relay_process, operation)
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


async def execute_session(nonce, files, commit, identities, incoming, connection, path, intent_raw, operation):
    """Consume the live session here, never in another process or async task.

    The early durable acknowledgement confirms only a committed handoff. The
    SSH relay can then exit while this native service owns the entire operation.
    Successful completion is durable only after the normal session exit checks.
    """
    if operation not in ('qualify-recovery', 'run-recovery'):
        raise ValueError('Fixed recovery execution operation required')
    import no_cutoff_recovery_files as evidence
    expected = base(nonce, files, commit, operation)
    relative = operation_state(operation)
    directory_id = boot.directories(path, private=True)
    retained = {n: boot.raw(ROOT, relative + '/' + n) for n in ('intent.json', 'service-started.json')}
    if retained['intent.json'][0] != intent_raw: raise ValueError('Native operation intent changed')
    # The log may grow while the operation runs, but cannot be replaced or
    # change owner, type, links or privacy. Payload bytes stay private.
    log_identity = boot.identity((path / 'service.log').lstat())[:6]
    with session.open_session(incoming) as active:
        live = session._live(active)
        policy._same(handoff._live(live['witness'])['header']['operator']['operator_commit'], commit)
        record = session.recheck(active); policy._same(record['files'], files)
        check(files, identities)
        prerequisites = save(path / 'prerequisites.json', record)
        prior = record['predecessor']
        accepted = dict(expected, kind='recovery_handoff_committed_operation_accepted_not_completed',
            native_process=process_identity(os.getpid()),
            prerequisites_sha256=hashlib.sha256(prerequisites).hexdigest(),
            operator_document_sha256=prior['operator_document_sha256'],
            archive_sha256=prior['streamed_backup']['sha256'])
        save(path / 'accepted.json', accepted)
        for name in ('prerequisites.json', 'accepted.json'):
            retained[name] = boot.raw(ROOT, relative + '/' + name)
        _reply(connection, accepted)
        try: connection.shutdown(socket.SHUT_WR)
        except OSError: pass  # A lost client cannot cancel a committed native operation.
        if operation == 'qualify-recovery':
            import qualify_no_cutoff_recovery as qualifier
            await qualifier.qualify(active)
            terminal = policy.QUALIFIER_RESULT_FILE
        else:
            import run_no_cutoff_recovery as runner
            await runner.run(active)
            terminal = runner.RESULT
        # Bind the actual producer, not a coroutine return value or receipt.
        terminal_name = '.runtime/stage2/' + terminal
        terminal_files, terminal_ids = evidence.capture(ROOT, [terminal_name])
        session.recheck(active); check(files, identities)
        evidence.check(ROOT, terminal_files, terminal_ids)
    # Both live handles are invalidated before any durable success is written.
    check(files, identities); evidence.check(ROOT, terminal_files, terminal_ids)
    # A late relay marker can arrive concurrently after committed handoff. It
    # is transport evidence, not a native failure or authority to start work.
    required = {'intent.json', 'service-started.json', 'service.log', 'prerequisites.json', 'accepted.json'}
    present = {p.name for p in path.iterdir()}
    _transport_failure(path, expected)
    if (boot.directories(path, private=True) != directory_id
            or any(boot.raw(ROOT, relative + '/' + n) != saved for n, saved in retained.items())
            or boot.identity((path / 'service.log').lstat())[:6] != log_identity
            or not required <= present or present - required - {'relay-failure.json'}):
        raise ValueError('Retained recovery operation evidence drift')
    log_files, log_ids = evidence.capture(ROOT, [relative + '/service.log'])
    result = dict(expected, kind='recovery_service_operation_finished_not_completed_study_audit',
        terminal_files=terminal_files, log_files=log_files,
        completed_utc=datetime.now(timezone.utc).isoformat())
    evidence.check(ROOT, log_files, log_ids)
    save(path / 'result.json', result)
    return result


def serve(nonce, files, commit, identities, relay_process, operation=OPERATION):
    """The systemd process, not the relay, owns one real main-task session."""
    expected = base(nonce, files, commit, operation); check(files, identities)
    path = folder(operation); intent_raw = boot.raw(ROOT, operation_state(operation) + '/intent.json')[0]
    intent = boot.loads(intent_raw)
    if (set(intent) != set(expected) | {'relay_process', 'created_utc'}
            or {k: intent[k] for k in expected} != expected or intent['relay_process'] != relay_process):
        raise ValueError('Exact durable native connection intent required')
    handoff.archive._utc(intent['created_utc'])
    if {p.name for p in path.iterdir()} != {'intent.json', 'service.log'}:
        raise ValueError('Existing/partial native inspection cannot be restarted')
    # This exclusive start is the one-shot service gate; no ancestor locks are
    # acquired until actual archive authentication/audits inside open_session.
    process = process_identity(os.getpid())
    started = dict(expected, native_process=process)
    if operation != OPERATION:
        started['invocation_id'] = _execution_start(expected['unit'], process)
    save(path / 'service-started.json', started)
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
                if operation == OPERATION:
                    asyncio.run(inspect_session(nonce, files, commit, identities, incoming, connection, path, intent_raw))
                else:
                    asyncio.run(execute_session(nonce, files, commit, identities, incoming,
                        connection, path, intent_raw, operation))
    except BaseException:
        _failure(path, 'failure.json', expected)
        raise

"""Fixed detached baseline qualification/dispatch; no generic program or retry.

The service owns the real composite archive session on its main async task.
An acknowledgement means handoff acceptance, never qualification or a score.
"""
import asyncio
import base64
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

import matched_repeat_completion as completion
import matched_repeat_execution_bootstrap as boot
import matched_repeat_execution_transport as transport
import matched_repeat_policy as policy
import matched_repeat_recovery_handoff as handoff
import matched_repeat_runtime as runtime
import matched_repeat_session as session
import matched_repeat_stream as wire
import no_cutoff_recovery_files as evidence

TIMEOUT = handoff.original.launch.transport.HANDOFF_SECONDS
REPLY_LIMIT = 16384
RUN_BASE = Path('/run')


def loaded(harness, files):
    runtime.loaded_sources(boot.root_for(harness), {n[7:]: h for n, h in files.items() if n.startswith('stage2/')})


def check(harness, files, identities):
    root = boot.root_for(harness)
    if boot.VIOLATION or Path(__file__).absolute() != root / 'stage2/matched_repeat_execution_service.py':
        raise ValueError('Own source-bound baseline service without a latched effect refusal required')
    boot.check(harness, files, identities); loaded(harness, files)
    return root


def folder(harness, operation):
    path = boot.root_for(harness) / completion.operation_state(operation)
    boot.directories(path, private=True)
    return path


def _sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def save(path, value):
    evidence.save(path, value)
    return evidence.read(path.parent, path.name)[0]


def native_program(harness, nonce, files, commit, *, role, relay_process=None, operation='qualify-repeat'):
    root = boot.root_for(harness); completion.base(harness, nonce, files, commit, operation)
    if (role not in ('relay', 'service', 'status') or (role != 'service') != (relay_process is None)
            or role == 'service' and (type(relay_process) is not dict or set(relay_process) != {'pid', 'start_ticks'}
                or any(type(v) is not int or v <= 0 for v in relay_process.values()))):
        raise ValueError('Exact fixed baseline bootstrap role required')
    if (files.get(boot.BASELINE_INPUT) != boot.BASELINE_SHA or files.get(boot.FINAL_INPUT) != boot.FINAL_SHA
            or not {'stage2/' + n for n in policy.REQUIRED_SOURCE_FILES}.issubset(files)
            or any(not n.startswith('stage2/') and n not in {boot.BASELINE_INPUT, boot.FINAL_INPUT} for n in files)):
        raise ValueError('Complete actual baseline source/private binding map required')
    name = 'stage2/matched_repeat_execution_bootstrap.py'; location = Path(__file__).absolute().parent.parent
    if location == root: raw = boot.raw(root, name, files[name])[0]
    elif location == handoff.operator.REPO:
        handoff.original.receiver._parents()
        raw = handoff.original.launch._raw(name, files[name])
    else: raise ValueError('Only the fixed Mac operator or native baseline root may bind the bootstrap')
    return ("import base64,types,sys,json\n"
        "m=types.ModuleType('matched_repeat_execution_bootstrap')\n"
        "m.__file__=" + repr(str(root / name)) + "\n"
        "sys.modules[m.__name__]=m\n"
        "exec(compile(base64.b64decode(" + repr(base64.b64encode(raw).decode()) + "),m.__file__,'exec'),m.__dict__)\n"
        "try:\n m.main(" + ','.join(map(repr, (harness, nonce, files, commit, role, relay_process, operation))) + ")\n"
        "except BaseException:\n print(json.dumps(dict(status='baseline_connection_failed_preserve_evidence',"
        "paid_launch_ready=False)),file=sys.stderr)\n raise SystemExit(1) from None\n")


def _peer(harness, connection):
    if not hasattr(socket, 'SO_PEERCRED'): raise ValueError('Actual Linux peer credentials required')
    pid, uid, gid = struct.unpack('3i', connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))
    if pid <= 0 or uid != 0 or gid != 0: raise ValueError('Private root-owned baseline peer required')
    return completion.process_identity(boot.root_for(harness), pid)


def _service_process(harness, unit):
    root = boot.root_for(harness); state = completion.manager(root, unit)
    if state['ActiveState'] != 'active' or state['SubState'] != 'running' or not state['MainPID'].isdigit():
        raise ValueError('Actual running retained baseline service required')
    process = completion.process_identity(root, int(state['MainPID']))
    if completion.manager(root, unit) != state: raise ValueError('Baseline service invocation changed')
    return process


def endpoint(harness, nonce):
    completion.identity(harness, nonce, 'qualify-repeat'); boot.directories(RUN_BASE)
    return RUN_BASE / ('uts-br-' + nonce) / 'input.sock'


def _socket_identity(path):
    parents = boot.directories(path.parent, private=True); item = path.lstat(); boot.acl(path)
    if (not stat.S_ISSOCK(item.st_mode) or item.st_uid != os.getuid() or item.st_gid != os.getgid()
            or item.st_nlink != 1 or stat.S_IMODE(item.st_mode) != 0o600):
        raise ValueError('Exclusive private baseline Unix socket required')
    return parents, boot.identity(item)


def service_command(harness, nonce, files, commit, relay_process, operation):
    root = boot.root_for(harness); path = folder(harness, operation)
    program = native_program(harness, nonce, files, commit, role='service',
        relay_process=relay_process, operation=operation)
    return ['systemd-run', '--quiet', '--unit=' + completion.identity(harness, nonce, operation),
        '--property=Type=exec', '--property=RemainAfterExit=yes', '--property=WorkingDirectory=' + str(root),
        '--property=UMask=0077', '--property=Restart=no', '--property=StandardInput=null',
        '--property=StandardOutput=append:' + str(path / 'service.log'), '--property=StandardError=inherit',
        '/usr/bin/env', '-i', *(k + '=' + v for k, v in boot.environment(harness).items()),
        str(root / '.venv/bin/python'), '-I', '-B', '-c', program]


def _line(value):
    raw = json.dumps(value, sort_keys=True, allow_nan=False).encode() + b'\n'
    if len(raw) > REPLY_LIMIT: raise ValueError('Baseline acknowledgement exceeds metadata parser window')
    return raw


def _reply(connection, value):
    try: connection.sendall(_line(value))
    except OSError: pass  # Durable committed native work survives a lost Mac acknowledgement.


def _read_reply(stream):
    raw = stream.readline(REPLY_LIMIT + 1)
    if len(raw) > REPLY_LIMIT or not raw.endswith(b'\n') or stream.read(1):
        raise ValueError('One exact baseline acknowledgement and EOF required')
    return boot.loads(raw)


def _failure(path, name, expected):
    save(path / name, dict(expected, status='uncertain_preserve_evidence_inspect_without_retry'))


def relay(harness, nonce, files, commit, identities, operation):
    root = check(harness, files, identities); boot.ancestors(harness, files); check(harness, files, identities)
    wire.pipe_only(sys.stdin.buffer)
    expected = completion.base(harness, nonce, files, commit, operation)
    path = root / completion.operation_state(operation); boot.directories(path.parent, private=True)
    path.mkdir(mode=0o700); _sync(path.parent); directory_id = boot.directories(path, private=True)
    listener = sock = socket_id = None
    try:
        process = completion.process_identity(root, os.getpid())
        save(path / 'intent.json', dict(expected, relay_process=process, created_utc=datetime.now(timezone.utc).isoformat()))
        fd = os.open(path / 'service.log', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd); _sync(path)
        sock = endpoint(harness, nonce); sock.parent.mkdir(mode=0o700)
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(str(sock)); sock.chmod(0o600); socket_id = _socket_identity(sock)
        listener.listen(1); listener.settimeout(TIMEOUT)
        boot.ancestors(harness, files); check(harness, files, identities)
        argv = service_command(harness, nonce, files, commit, process, operation)
        subprocess.run(argv, check=True, capture_output=True, timeout=30, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        with listener.accept()[0] as connection:
            listener.close(); peer = _peer(harness, connection)
            if peer != _service_process(harness, expected['unit']) or _socket_identity(sock) != socket_id:
                raise ValueError('Actual peer is not the retained systemd MainPID')
            sys.stdout.buffer.write(_line(dict(expected, kind='baseline_receiver_ready_not_authenticated', native_process=peer)))
            sys.stdout.buffer.flush()
            transport.relay(sys.stdin.buffer, sys.stdout.buffer, connection)
            if boot.directories(path, private=True) != directory_id: raise ValueError('Baseline connection directory replaced')
    except BaseException:
        _failure(path, 'relay-failure.json', expected); raise
    finally:
        if listener is not None: listener.close()
        if socket_id is not None and _socket_identity(sock) == socket_id:
            sock.unlink(); sock.parent.rmdir()


async def execute(harness, nonce, files, commit, identities, incoming, connection, path, intent_raw, operation):
    root = boot.root_for(harness); relative = completion.operation_state(operation)
    expected = completion.base(harness, nonce, files, commit, operation)
    directory_id = boot.directories(path, private=True)
    retained = {n: evidence.read(root, relative + '/' + n) for n in ('intent.json', 'service-started.json')}
    if retained['intent.json'][0] != intent_raw: raise ValueError('Baseline operation intent changed')
    log_identity = boot.identity((path / 'service.log').lstat())[:6]
    with session.open_execution_session(root, harness, incoming) as active:
        recovered = session.require_execution(active)
        if recovered['operator_commit'] != commit: raise ValueError('Actual handoff and detached operation revision differ')
        if operation == 'run-repeat':
            completion.read(active, 'qualify-repeat')  # Actual successful qualifier SERVICE exit, not a proof flag.
            session.verify_qualification(active)
        record = session.recheck(active)
        completion.same(record['inputs'], files); check(harness, files, identities)
        prerequisites = save(path / 'prerequisites.json', record); prior = record['predecessor']
        accepted = dict(expected, kind='baseline_handoff_committed_operation_accepted_not_completed',
            native_process=completion.process_identity(root, os.getpid()),
            prerequisites_sha256=hashlib.sha256(prerequisites).hexdigest(),
            operator_document_sha256=prior['operator_document_sha256'], archive_sha256=prior['streamed_backup']['sha256'],
            recovery_document_sha256=recovered['recovery_document_sha256'], recovery_archive_sha256=recovered['archive_sha256'])
        if harness == 'openhands':
            earlier = record['completed_terminus']
            accepted.update(terminus_document_sha256=earlier['terminus_document_sha256'],
                terminus_archive_sha256=earlier['archive_sha256'])
        save(path / 'accepted.json', accepted)
        for n in ('prerequisites.json', 'accepted.json'): retained[n] = evidence.read(root, relative + '/' + n)
        _reply(connection, accepted)
        try: connection.shutdown(socket.SHUT_WR)
        except OSError: pass
        if operation == 'qualify-repeat':
            import qualify_matched_repeat as qualifier
            await qualifier.qualify(active); terminal = policy.QUALIFIER_RESULT_FILE
        elif operation == 'run-repeat':
            import run_matched_repeat as runner
            await runner.run(active); terminal = runner.RESULT
        else: raise ValueError('Only the fixed qualification and sequential baseline operation exist')
        terminal_files, terminal_ids = evidence.capture(root, [completion.RT + terminal])
        session.recheck(active); check(harness, files, identities); evidence.check(root, terminal_files, terminal_ids)
    # Normal session exit and BOTH witness invalidations precede durable success.
    check(harness, files, identities); evidence.check(root, terminal_files, terminal_ids)
    required = {'intent.json', 'service-started.json', 'service.log', 'prerequisites.json', 'accepted.json'}
    completion.transport_failure(root, operation, expected); names = {p.name for p in path.iterdir()}
    if (boot.directories(path, private=True) != directory_id
            or any(evidence.read(root, relative + '/' + n) != value for n, value in retained.items())
            or boot.identity((path / 'service.log').lstat())[:6] != log_identity
            or not required <= names or names - required - {'relay-failure.json'}):
        raise ValueError('Baseline service evidence changed or contains partial/failure state')
    log_files, log_ids = evidence.capture(root, [relative + '/service.log'])
    result = dict(expected, kind='baseline_service_operation_finished_not_completed_study_audit',
        terminal_files=terminal_files, log_files=log_files, completed_utc=datetime.now(timezone.utc).isoformat())
    evidence.check(root, log_files, log_ids); save(path / 'result.json', result)
    return result


def serve(harness, nonce, files, commit, identities, relay_process, operation):
    root = check(harness, files, identities); expected = completion.base(harness, nonce, files, commit, operation)
    path = folder(harness, operation); intent_raw = evidence.read(root, completion.operation_state(operation) + '/intent.json')[0]
    intent = boot.loads(intent_raw)
    if (intent.get('relay_process') != relay_process or any(intent.get(k) != v for k, v in expected.items())
            or {p.name for p in path.iterdir()} != {'intent.json', 'service.log'}):
        raise ValueError('Existing, partial or mismatched baseline operation cannot be restarted')
    process = completion.process_identity(root, os.getpid())
    invocation = completion.started(root, expected['unit'], process)
    save(path / 'service-started.json', dict(expected, native_process=process, invocation_id=invocation))
    stage = 'service_identity'
    try:
        if _service_process(harness, expected['unit']) != process: raise ValueError('Actual detached MainPID required')
        sock = endpoint(harness, nonce); socket_id = _socket_identity(sock); stage = 'socket_connect'
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(TIMEOUT); connection.connect(str(sock)); stage = 'peer_identity'
            if _peer(harness, connection) != relay_process or _socket_identity(sock) != socket_id:
                raise ValueError('Baseline service peer is not its pinned relay process')
            with connection.makefile('rb', buffering=0) as incoming, connection.makefile('wb', buffering=0) as outgoing:
                with transport.Writer(outgoing) as writer:
                    check(harness, files, identities); stage = 'live_execution_session'
                    asyncio.run(execute(harness, nonce, files, commit, identities,
                        transport.Reader(incoming), transport.Acknowledgement(writer, connection), path, intent_raw, operation))
    except BaseException as error:
        _failure(path, 'failure.json', expected)
        allowed = {ValueError, OSError, TimeoutError, BrokenPipeError, RuntimeError, asyncio.CancelledError, SystemExit, KeyboardInterrupt}
        save(path / 'failure-diagnostic.json', dict(stage=stage,
            error_class=type(error).__name__ if type(error) in allowed else 'OtherException',
            automatic_resume=False, paid_launch_ready=False))
        raise


def operation_status(harness, files, commit, identities, operation):
    """Fresh fixed metadata only; no collector, archive, signal or resume."""
    root = check(harness, files, identities); relative = completion.operation_state(operation)
    path = folder(harness, operation)
    retained = {n: evidence.read(root, relative + '/' + n) for n in ('intent.json', 'service-started.json')}
    intent = boot.loads(retained['intent.json'][0]); started = boot.loads(retained['service-started.json'][0])
    expected = completion.base(harness, intent.get('nonce'), files, intent.get('operator_commit'), operation)
    if any(intent.get(k) != v for k, v in expected.items()): raise ValueError('Actual baseline status identity required')
    state = completion.manager(root, expected['unit'])
    if state['InvocationID'] != started.get('invocation_id'): raise ValueError('Actual retained invocation required')
    complete = None
    if state['ActiveState'] == 'active' and state['SubState'] == 'exited':
        complete = completion._read(root, harness, files, operation)
        status = 'service_exited_successfully_not_completed_study_audit'
    elif state['ActiveState'] == 'active' and state['SubState'] == 'running':
        if _service_process(harness, expected['unit']) != started.get('native_process'):
            raise ValueError('Actual running process differs from retained baseline start')
        status = 'running'
    else: status = 'uncertain_or_failed_preserve_evidence_no_retry'
    manifest = boot.loads(evidence.read(root, 'stage2/input_manifest.json')[0])
    counts = dict(study=policy.EXPERIMENT, harness=harness, intended=89, started=0, completed=0,
        passed=0, failed=0, missing_verifier=0, active_tasks=[])
    records = {}
    for ordinal, cell in enumerate(policy.cells(manifest, harness), 1):
        values = {}
        for name in ('started.json', 'result.json'):
            item = completion.RT + 'scored-trials/' + cell['trial_id'] + '/' + name
            if (root / item).exists() or (root / item).is_symlink():
                records[item] = evidence.read(root, item); value = boot.loads(records[item][0])
                for key, expected_value in dict(trial_id=cell['trial_id'], task_id=cell['task_id'],
                        matched_repeat_experiment=policy.EXPERIMENT, harness=harness, stage='final').items():
                    completion.same(value.get(key), expected_value)
                values[name] = value
        if 'result.json' in values and 'started.json' not in values: raise ValueError('Actual start required for retained result')
        if 'started.json' in values:
            counts['started'] += 1
            if 'result.json' not in values: counts['active_tasks'].append(ordinal)
        if 'result.json' in values:
            counts['completed'] += 1
            reward = ((values['result.json'].get('verifier_result') or {}).get('rewards') or {}).get('reward')
            if reward is None: counts['missing_verifier'] += 1
            elif type(reward) in (int, float) and reward in (0, 1): counts['passed' if reward == 1 else 'failed'] += 1
            else: raise ValueError('Unexpected retained baseline verifier outcome')
    # Final actual source/evidence reads follow the final manager/process observation.
    check(harness, files, identities)
    if (any(evidence.read(root, relative + '/' + n) != value for n, value in retained.items())
            or any(evidence.read(root, n) != value for n, value in records.items())):
        raise ValueError('Baseline status evidence changed during observation')
    if complete is not None: evidence.check(root, complete['files'], complete['identities'])
    return dict(kind='read_only_baseline_operation_status_not_admission', operation=operation,
        status=status, unit=expected['unit'], counts=counts, observed_utc=datetime.now(timezone.utc).isoformat(),
        automatic_resume=False, paid_launch_ready=False)

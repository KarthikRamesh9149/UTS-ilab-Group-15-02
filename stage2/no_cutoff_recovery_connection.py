"""Fixed Mac/pinned-SSH recovery inspection and detached execution entries.

This is not deployment or an archive writer. The real sender always captures a fresh original audit and
reads the SAME retained archive. Partial/uncertain operations are not retried.
"""
import base64
import os
from pathlib import Path
import secrets
import selectors
import shlex
import subprocess
import time

import no_cutoff_recovery_bootstrap as boot
import no_cutoff_recovery_handoff as handoff
import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_predecessor as operator
import no_cutoff_recovery_service as service
from progress_dashboard import ssh_command, REMOTE_HOST
from scored_gateway import durable_json

STATE = '.runtime/netcup/custom-no-cutoff-recovery-prerequisites-20260930-r4'
TIMEOUT = handoff.launch.transport.HANDOFF_SECONDS
REPLY_LIMIT = 16384


def prepare(commit):
    value = operator._prepare(commit)  # Full committed HEAD/fetched main, actual metadata.
    if Path(__file__).absolute() != handoff.launch.REPO / 'stage2/no_cutoff_recovery_connection.py':
        raise ValueError('Fixed Mac recovery connection required')
    files = {'stage2/' + n: h for n, h in value['current_sources'].items()}
    files['stage2/input_manifest.json'] = policy.INPUT_SHA256
    files[boot.QUALIFICATION] = policy.ORIGINAL_QUALIFICATION_FILE_SHA256
    operator._current(value)
    return value, files


def _local_identities(value):
    bindings = dict(value['bindings']['local'])
    for mapping in (value['recovery_local'], value['publication']):
        handoff.report._merge(bindings, mapping)
    result = {}
    for name, digest in bindings.items():
        path = handoff.launch.REPO / name; before = boot.identity(path.lstat())
        handoff.launch._raw(name, digest)
        if boot.identity(path.lstat()) != before: raise ValueError('Operator input identity changed during read')
        result[name] = before
    return result


def native_program(nonce, files, commit, *, role, relay_process=None, operation=service.OPERATION):
    service.base(nonce, files, commit, operation)
    if (role not in ('relay', 'service', 'status') or (role != 'service') != (relay_process is None)
            or role == 'status' and operation == service.OPERATION
            or role == 'service' and (type(relay_process) is not dict or set(relay_process) != {'pid', 'start_ticks'}
                or any(type(v) is not int or v <= 0 for v in relay_process.values()))):
        raise ValueError('Exact recovery inspection role and process identity required')
    handoff.archive._map(files)
    if (not {'stage2/' + n for n in policy.REQUIRED_SOURCE_FILES}.issubset(files)
            or files.get(boot.QUALIFICATION) != policy.ORIGINAL_QUALIFICATION_FILE_SHA256
            or files.get('stage2/input_manifest.json') != policy.INPUT_SHA256
            or any(not n.startswith('stage2/') and n != boot.QUALIFICATION for n in files)):
        raise ValueError('Full current recovery source/private bindings required')
    name = 'stage2/no_cutoff_recovery_bootstrap.py'
    root = Path(__file__).absolute().parent.parent
    # This helper also runs inside the native relay: only its actual bound
    # stdlib bootstrap bytes are embedded, never a caller-supplied program.
    if root == boot.ROOT:
        raw = boot.raw(root, name, files[name])[0]
    elif root == handoff.launch.REPO:
        handoff.receiver._parents()
        raw = handoff.launch._raw(name, files[name])
    else: raise ValueError('Only fixed native relay or Mac bootstrap source allowed')
    encoded = base64.b64encode(raw).decode()
    return ("import base64,types,sys,json\n"
        "m=types.ModuleType('no_cutoff_recovery_bootstrap')\n"
        "m.__file__=" + repr(str(boot.ROOT / name)) + "\n"
        "sys.modules[m.__name__]=m\n"
        "exec(compile(base64.b64decode(" + repr(encoded) + "),m.__file__,'exec'),m.__dict__)\n"
        "try:\n m.main(" + ','.join(map(repr, (nonce, files, commit, role, relay_process, operation))) + ")\n"
        "except BaseException:\n print(json.dumps(dict(status='recovery_connection_failed_preserve_evidence',"
        "paid_launch_ready=False)),file=sys.stderr)\n raise SystemExit(1) from None\n")


def command(nonce, files, commit, operation=service.OPERATION):
    repo = handoff.launch.REPO
    # Independently check the unchanged inherited SSH helper bytes before use.
    handoff.receiver._parents()
    handoff.launch._raw('stage2/progress_dashboard.py', files['stage2/progress_dashboard.py'])
    args = ssh_command(repo)
    expected = ['ssh', '-F', '/dev/null', '-i', str(repo / '.runtime/netcup/id_ed25519'),
        '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
        '-o', 'UserKnownHostsFile=' + str(repo / '.runtime/netcup/known_hosts'),
        '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-o', 'ClearAllForwardings=yes',
        '-o', 'RequestTTY=no', '-o', 'LogLevel=ERROR', 'root@62.83.32.126', 'python3', '-']
    if args != expected or REMOTE_HOST != 'root@62.83.32.126':
        raise ValueError('Exact unchanged pinned SSH route required')
    remote = ['/usr/bin/env', '-i', *(k + '=' + v for k, v in boot.environment().items()),
        str(boot.ROOT / '.venv/bin/python'), '-I', '-B', '-c',
        native_program(nonce, files, commit, role='relay', operation=operation)]
    return args[:-2] + [shlex.join(remote)]


def read_reply(stream):
    data = bytearray(); deadline = time.monotonic() + TIMEOUT
    with selectors.DefaultSelector() as selector:
        selector.register(stream, selectors.EVENT_READ)
        while b'\n' not in data:
            left = deadline - time.monotonic()
            if left <= 0 or not selector.select(left): raise ValueError('Connection timeout; inspect without retry')
            raw = os.read(stream.fileno(), min(4096, REPLY_LIMIT + 1 - len(data)))
            if not raw or len(data) + len(raw) > REPLY_LIMIT: raise ValueError('Incomplete native acknowledgement')
            data.extend(raw)
    line, extra = bytes(data).split(b'\n', 1)
    if extra: raise ValueError('Extra native acknowledgement bytes')
    return boot.loads(line)


def reply(value, nonce, files, commit, *, sent=None, peer=None, operation=service.OPERATION):
    expected = service.base(nonce, files, commit, operation)
    process = value.get('native_process') if type(value) is dict else None
    if (type(process) is not dict or set(process) != {'pid', 'start_ticks'}
            or any(type(v) is not int or v <= 0 for v in process.values())):
        raise ValueError('Actual native process acknowledgement required')
    expected.update(kind='recovery_receiver_ready_not_authenticated', native_process=process)
    if sent is not None:
        expected.update(kind='recovery_prerequisites_checked_not_dispatch', native_process=peer,
            operator_document_sha256=sent['operator_document_sha256'], archive_sha256=sent['archive_sha256'],
            prerequisites_sha256=value.get('prerequisites_sha256'))
        policy._hash(expected['prerequisites_sha256'])
        if operation != service.OPERATION:
            expected['kind'] = 'recovery_handoff_committed_operation_accepted_not_completed'
    policy._same(value, expected)
    return value


def _operate(commit, operation):
    """One explicit actual connection; never auto-retry or stop native work."""
    value, files = prepare(commit)
    from no_cutoff_recovery_install import _retained_operator_states
    retained_operator = _retained_operator_states()
    original_identities = _local_identities(value)
    parents = handoff.receiver._parents(); root = handoff.launch.REPO
    service.operation_state(operation)
    state_name = STATE if operation == service.OPERATION else '.runtime/netcup/custom-no-cutoff-recovery-' + service.OPERATIONS[operation] + '-20260930-r4'
    path = root / state_name
    if path.exists() or path.is_symlink():
        raise ValueError('Existing or partial recovery connection is terminal; inspect without retry')
    nonce = secrets.token_hex(16); expected = service.base(nonce, files, commit, operation)
    argv = command(nonce, files, commit, operation)
    operator._current(value)
    if handoff.receiver._parents() != parents: raise ValueError('Operator parents changed')
    path.mkdir(mode=0o700); handoff.receiver._sync(path.parent)
    state = (parents, handoff.receiver._directory_id(path)); process = None
    def save(name, data):
        handoff.receiver._state(path, state); durable_json(path / name, data)
        handoff.receiver._state(path, state)
        raw = handoff.launch._raw(state_name + '/' + name)
        policy._same(boot.loads(raw), data)
        return raw, boot.identity((path / name).lstat())
    def current():
        operator._current(value)
        if _retained_operator_states() != retained_operator:
            raise ValueError('Earlier operator evidence replaced')
        if _local_identities(value) != original_identities:
            raise ValueError('Operator source/private identity replaced')
    def retained(name):
        raw = handoff.launch._raw(state_name + '/' + name)
        return raw, boot.identity((path / name).lstat())
    try:
        intent_raw = save('intent.json', expected)
        current()
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        ready = reply(read_reply(process.stdout), nonce, files, commit, operation=operation)
        ready_raw = save('receiver.json', ready)
        current()
        sent = handoff.send(process.stdin)  # ALWAYS real fresh audit/same-archive capture.
        process.stdin.close()
        result = reply(read_reply(process.stdout), nonce, files, commit,
            sent=sent, peer=ready['native_process'], operation=operation)
        if process.wait(timeout=10) != 0 or process.stdout.read(1):
            raise ValueError('Ambiguous SSH exit; inspect retained native state')
        current()
        if (retained('intent.json') != intent_raw
                or retained('receiver.json') != ready_raw
                or {p.name for p in path.iterdir()} != {'intent.json', 'receiver.json'}):
            raise ValueError('Operator connection evidence changed')
        save('result.json', result)
        return result
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.kill(); process.wait(timeout=10)  # Owned Mac SSH client ONLY.
        save('failure.json', dict(expected, status='uncertain_inspect_native_evidence_without_retry'))
        error.add_note('Retain native unit ' + expected['unit'] + ' and operator evidence ' + str(path))
        raise
    finally:
        if process is not None:
            process.stdin.close(); process.stdout.close()


def inspect_native(commit):
    return _operate(commit, service.OPERATION)


def qualify_native(commit):
    """Return committed handoff acknowledgement, never qualification success."""
    return _operate(commit, 'qualify-recovery')


def run_native(commit):
    """Start the fixed qualified sequential route; acknowledgement is not a score."""
    return _operate(commit, 'run-recovery')


def status_native(commit, operation):
    """Fresh read-only metadata for an existing fixed operation, never replay."""
    if operation not in ('qualify-recovery', 'run-recovery'):
        raise ValueError('Fixed recovery execution status required')
    value, files = prepare(commit); identities = _local_identities(value)
    # Validate the inherited route independently, then replace only its fixed
    # remote program tail with the equally source-bound read-only entry.
    argv = command('0' * 32, files, commit, operation)
    remote = ['/usr/bin/env', '-i', *(k + '=' + v for k, v in boot.environment().items()),
        str(boot.ROOT / '.venv/bin/python'), '-I', '-B', '-c',
        native_program('0' * 32, files, commit, role='status', operation=operation)]
    result = subprocess.run(argv[:-1] + [shlex.join(remote)], input=b'', capture_output=True,
        timeout=120, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    if result.returncode or len(result.stdout) > REPLY_LIMIT:
        raise ValueError('Read-only status refused; preserve native evidence without retrying execution')
    observed = boot.loads(result.stdout)
    if (observed.get('kind') != 'read_only_recovery_operation_status_not_admission'
            or observed.get('operation') != operation or observed.get('paid_launch_ready') is not False
            or observed.get('automatic_resume') is not False):
        raise ValueError('Exact source-bound non-admitting status required')
    operator._current(value)
    if _local_identities(value) != identities: raise ValueError('Local status inputs changed')
    return observed

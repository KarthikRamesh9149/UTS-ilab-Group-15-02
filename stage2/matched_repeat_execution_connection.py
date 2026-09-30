"""Fixed Mac entries for real baseline qualification and sequential dispatch.

The unchanged inspection route is not reused as authority. Every operation
performs the actual composite recovery/original handoff inside its own native
service session. Existing or uncertain operations are terminal, never replayed.
"""
import os
from pathlib import Path
import secrets
import shlex
import subprocess

import matched_repeat_completion as completion
import matched_repeat_execution_bootstrap as boot
import matched_repeat_execution_service as service
import matched_repeat_policy as policy
import matched_repeat_recovery_handoff as handoff
from no_cutoff_recovery_connection import read_reply
from progress_dashboard import ssh_command, REMOTE_HOST
from scored_gateway import durable_json

REPO = handoff.operator.REPO


def _first(harness):
    policy._harness(harness)


def state_name(harness, operation):
    _first(harness); completion.operation_state(operation)
    return '.runtime/netcup/matched-repeat-' + harness + '-' + completion.OPERATIONS[operation] + '-20260930'


def _identities(bindings):
    result = {}
    for name, digest in bindings['local'].items():
        path = REPO / name; before = boot.identity(path.lstat())
        handoff.original.launch._raw(name, digest)
        if boot.identity(path.lstat()) != before: raise ValueError('Operator input replaced while reading')
        result[name] = before
    return result


def _current(value):
    handoff.original.launch._recheck(value['bindings'])
    if _identities(value['bindings']) != value['identities']:
        raise ValueError('Committed baseline operator source/private identity changed')
    handoff.operator._current(value['recovery'])
    if value.get('harness') == 'openhands':
        import matched_repeat_terminus_predecessor as terminus
        terminus.current(value['terminus'])
    handoff.operator._loaded(value['bindings'])


def prepare(commit, harness):
    value, files = _source_inputs(commit, harness)
    bindings = value['bindings']
    sources = handoff.operator._sources(bindings)
    # Preliminary actual existing archive/export check, NOT a fresh audit or
    # saved admission. send() independently performs both real fresh captures.
    value['recovery'] = dict(bindings=bindings, sources=sources,
        retained=handoff.operator._retained(bindings, sources))
    if harness == 'openhands':
        import matched_repeat_terminus_predecessor as terminus
        value['terminus'] = terminus.prepare(commit)
    _current(value)
    return value, files


def _source_inputs(commit, harness):
    _first(harness)
    if Path(__file__).absolute() != REPO / 'stage2/matched_repeat_execution_connection.py':
        raise ValueError('Fixed Mac baseline execution connection required')
    # This immutable reader supplies the ORIGINAL custom-final dependency,
    # not the new harness's execution identity. OpenHands additionally needs
    # the actual completed-Terminus reader in prepare/send and its live scope.
    bindings, anchors = handoff.operator.original._prepare(commit, 'terminus-2')
    names = set(anchors['proof']['sources']) | policy.REQUIRED_SOURCE_FILES
    files = {'stage2/' + n: bindings['local']['stage2/' + n] for n in names}
    files.update({boot.BASELINE_INPUT: boot.BASELINE_SHA, boot.FINAL_INPUT: boot.FINAL_SHA})
    value = dict(bindings=bindings, identities=_identities(bindings), harness=harness,
        sources={n[7:]: h for n, h in files.items() if n.startswith('stage2/')})
    handoff.operator._loaded(bindings)
    return value, files


def command(harness, nonce, files, commit, operation, *, role='relay'):
    _first(harness); completion.operation_state(operation)
    if role not in ('relay', 'status'): raise ValueError('Fixed Mac relay or read-only status entry required')
    handoff.original.receiver._parents()
    handoff.original.launch._raw('stage2/progress_dashboard.py', files['stage2/progress_dashboard.py'])
    args = ssh_command(REPO)
    expected = ['ssh', '-F', '/dev/null', '-i', str(REPO / '.runtime/netcup/id_ed25519'),
        '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'BatchMode=yes',
        '-o', 'UserKnownHostsFile=' + str(REPO / '.runtime/netcup/known_hosts'),
        '-o', 'ConnectTimeout=10', '-o', 'ConnectionAttempts=1', '-o', 'ClearAllForwardings=yes',
        '-o', 'RequestTTY=no', '-o', 'LogLevel=ERROR', 'root@62.83.32.126', 'python3', '-']
    if args != expected or REMOTE_HOST != 'root@62.83.32.126':
        raise ValueError('Every original pinned SSH option must be preserved')
    program = service.native_program(harness, nonce, files, commit, role=role, operation=operation)
    remote = ['/usr/bin/env', '-i', *(k + '=' + v for k, v in boot.environment(harness).items()),
        str(boot.root_for(harness) / '.venv/bin/python'), '-I', '-B', '-c', program]
    return args[:-2] + [shlex.join(remote)]


def reply(value, harness, nonce, files, commit, operation, *, sent=None, peer=None):
    process = value.get('native_process') if type(value) is dict else None
    if (type(process) is not dict or set(process) != {'pid', 'start_ticks'}
            or any(type(v) is not int or v <= 0 for v in process.values())):
        raise ValueError('Actual native baseline process identity required')
    expected = dict(completion.base(harness, nonce, files, commit, operation),
        kind='baseline_receiver_ready_not_authenticated', native_process=process)
    if sent is not None:
        expected.update(kind='baseline_handoff_committed_operation_accepted_not_completed',
            native_process=peer, prerequisites_sha256=value.get('prerequisites_sha256'),
            operator_document_sha256=sent['original']['operator_document_sha256'],
            archive_sha256=sent['original']['archive_sha256'],
            recovery_document_sha256=sent['recovery_document_sha256'],
            recovery_archive_sha256=sent['recovery_archive_sha256'])
        policy._hash(expected['prerequisites_sha256'])
        if harness == 'openhands':
            for key in ('terminus_document_sha256', 'terminus_archive_sha256'):
                expected[key] = sent[key]; policy._hash(expected[key])
    completion.same(value, expected)
    return value


def send(harness, destination):
    _first(harness)
    if harness == 'openhands':
        import matched_repeat_terminus_handoff as terminus
        return terminus.send(destination)
    return handoff.send(destination)


def _operate(commit, harness, operation):
    state = state_name(harness, operation)
    value, files = prepare(commit, harness)
    parents = handoff.original.receiver._parents(); path = REPO / state
    if path.exists() or path.is_symlink():
        raise ValueError('Existing or partial baseline connection is terminal; inspect without retry')
    nonce = secrets.token_hex(16); expected = completion.base(harness, nonce, files, commit, operation)
    argv = command(harness, nonce, files, commit, operation)
    _current(value)
    if handoff.original.receiver._parents() != parents: raise ValueError('Operator ancestry changed')
    path.mkdir(mode=0o700); handoff.original.receiver._sync(path.parent)
    directory = (parents, handoff.original.receiver._directory_id(path)); process = None
    def retained(name):
        raw = handoff.original.launch._raw(state + '/' + name)
        return raw, boot.identity((path / name).lstat())
    def save(name, data):
        handoff.original.receiver._state(path, directory); durable_json(path / name, data)
        handoff.original.receiver._state(path, directory)
        result = retained(name); completion.same(boot.loads(result[0]), data)
        return result
    try:
        intent = save('intent.json', expected); _current(value)
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0, env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        ready = reply(read_reply(process.stdout), harness, nonce, files, commit, operation)
        receiver = save('receiver.json', ready); _current(value)
        sent = send(harness, process.stdin)  # Actual fresh captures of EVERY required predecessor.
        process.stdin.close()
        accepted = reply(read_reply(process.stdout), harness, nonce, files, commit, operation,
            sent=sent, peer=ready['native_process'])
        if process.wait(timeout=10) != 0 or process.stdout.read(1):
            raise ValueError('Ambiguous baseline SSH exit; inspect retained native operation')
        _current(value)
        if (retained('intent.json') != intent or retained('receiver.json') != receiver
                or {p.name for p in path.iterdir()} != {'intent.json', 'receiver.json'}):
            raise ValueError('Operator baseline evidence changed')
        save('result.json', accepted)
        return accepted
    except BaseException as error:
        if process is not None and process.poll() is None:
            process.kill(); process.wait(timeout=10)  # Only this owned Mac SSH client.
        save('failure.json', dict(expected, status='uncertain_inspect_native_evidence_without_retry'))
        error.add_note('Retain baseline unit ' + expected['unit'] + ' and operator state ' + str(path))
        raise
    finally:
        if process is not None:
            process.stdin.close(); process.stdout.close()


def qualify_native(commit, harness='terminus-2'):
    return _operate(commit, harness, 'qualify-repeat')


def run_native(commit, harness='terminus-2'):
    return _operate(commit, harness, 'run-repeat')


def status_native(commit, operation, harness='terminus-2'):
    """Actual fixed metadata only: no handoff, archive, collector or writer."""
    completion.operation_state(operation)
    value, files = _source_inputs(commit, harness)
    args = command(harness, '0' * 32, files, commit, operation, role='status')
    result = subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True, timeout=300,
        env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
    if result.returncode or len(result.stdout) > service.REPLY_LIMIT:
        raise ValueError('Read-only baseline status refused; no retry or signal')
    observed = boot.loads(result.stdout)
    if (observed.get('kind') != 'read_only_baseline_operation_status_not_admission'
            or observed.get('operation') != operation or observed.get('paid_launch_ready') is not False
            or observed.get('automatic_resume') is not False
            or observed.get('status') not in ('running', 'service_exited_successfully_not_completed_study_audit',
                'uncertain_or_failed_preserve_evidence_no_retry')
            or observed.get('counts', {}).get('harness') != harness):
        raise ValueError('Exact non-admitting baseline status required')
    handoff.original.launch._recheck(value['bindings'])
    if _identities(value['bindings']) != value['identities']:
        raise ValueError('Operator status inputs replaced')
    handoff.operator._loaded(value['bindings'])
    return observed

"""Actual retained service completion, never admission from a saved receipt.

The execution service must retain these exact identities. The reader observes
the real manager and procfs before final protected byte/identity rereads. It
cannot launch, signal, restart, register, qualify or dispatch a baseline.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess

import matched_repeat_execution_bootstrap as bootstrap
import matched_repeat_policy as policy
import matched_repeat_runtime as runtime
import matched_repeat_session as session
import no_cutoff_recovery_files as evidence
from no_cutoff_final_archive import _same as same, _utc

OPERATIONS = {'qualify-repeat': 'qualify', 'run-repeat': 'run'}
RT = '.runtime/stage2/'


def operation_state(operation):
    if operation not in OPERATIONS:
        raise ValueError('Fixed baseline execution operation required')
    return RT + 'matched-repeat-' + OPERATIONS[operation] + '-connection'


def identity(harness, nonce, operation):
    if harness not in runtime.DEPLOYMENTS or type(nonce) is not str or not re.fullmatch('[a-f0-9]{32}', nonce):
        raise ValueError('Exact baseline and fresh connection identity required')
    operation_state(operation)
    return 'uts-matched-repeat-' + harness + '-' + OPERATIONS[operation] + '-' + nonce + '.service'


def base(harness, nonce, files, commit, operation):
    if type(commit) is not str or not re.fullmatch('[a-f0-9]{40}', commit):
        raise ValueError('Full committed baseline revision required')
    private = {bootstrap.BASELINE_INPUT: bootstrap.BASELINE_SHA,
        bootstrap.FINAL_INPUT: bootstrap.FINAL_SHA}
    if (type(files) is not dict or any(type(name) is not str for name in files)
            or {name: sha for name, sha in files.items() if not name.startswith('stage2/')} != private):
        raise ValueError('Only bound stage2 sources and both exact private qualifications are allowed')
    policy._bindings({name: sha for name, sha in files.items() if name.startswith('stage2/')})
    policy._bindings(private, private=True)
    return dict(operation=operation, nonce=nonce, unit=identity(harness, nonce, operation),
        root=str(runtime.DEPLOYMENTS[harness]), experiment=policy.EXPERIMENT, harness=harness,
        operator_commit=commit, bindings_sha256=policy.fingerprint(files),
        automatic_resume=False, paid_launch_ready=False, repeat_execution_qualified=False)


def process_identity(root, pid):
    if root not in runtime.DEPLOYMENTS.values() or type(pid) is not int or pid <= 0:
        raise ValueError('Exact baseline root and actual process required')
    proc = Path('/proc') / str(pid)
    def read():
        parts = (proc / 'stat').read_text().rpartition(') ')[2].split()
        entries = [line.split(':', 1) for line in (proc / 'status').read_text().splitlines() if ':' in line]
        status = dict(entries)
        if (len(status) != len(entries) or len(parts) < 20 or not parts[19].isdigit()
                or status.get('Uid', '').split() != ['0'] * 4 or status.get('Gid', '').split() != ['0'] * 4
                or os.readlink(proc / 'cwd') != str(root)
                or os.readlink(proc / 'exe') != str((root / '.venv/bin/python').resolve())):
            raise ValueError('Exact baseline process owner, executable and directory required')
        return dict(pid=pid, start_ticks=int(parts[19]))
    first = read()
    if read() != first: raise ValueError('Baseline process identity changed')
    return first


def manager(root, unit):
    if root not in runtime.DEPLOYMENTS.values(): raise ValueError('Fixed baseline root required')
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
            or value['WorkingDirectory'] != str(root) or value['NRestarts'] != '0'
            or not re.fullmatch('[a-f0-9]{32}', value['InvocationID'])):
        raise ValueError('Actual retained one-shot baseline unit required')
    return value


def started(root, unit, process):
    value = manager(root, unit)
    if (value['ActiveState'] != 'active' or value['SubState'] != 'running'
            or value['MainPID'] != str(process['pid']) or value['ExecMainPID'] != str(process['pid'])
            or process_identity(root, process['pid']) != process or manager(root, unit) != value):
        raise ValueError('Actual running baseline invocation required')
    return value['InvocationID']


def process_ended(process):
    path = Path('/proc') / str(process['pid']) / 'stat'
    try: parts = path.read_text().rpartition(') ')[2].split()
    except FileNotFoundError: return
    if len(parts) < 20 or not parts[19].isdigit() or int(parts[19]) == process['start_ticks']:
        raise ValueError('Baseline service process has not verifiably ended')


def transport_failure(root, operation, expected):
    relative = operation_state(operation) + '/relay-failure.json'; path = root / relative
    if not path.exists() and not path.is_symlink(): return {}
    raw, item = evidence.read(root, relative)
    same(evidence.bootstrap.loads(raw), dict(expected, status='uncertain_preserve_evidence_inspect_without_retry'))
    return {relative: (raw, item)}


def read(active, operation):
    """Live same-task session plus real successful exit, never caller metadata."""
    live = session._live(active); root = live['root']; harness = live['harness']
    return _read(root, harness, live['files'], operation)


def _read(root, harness, files, operation):
    """Fixed service-status reader also uses these actual bytes/manager reads."""
    if (root != runtime.DEPLOYMENTS[harness]
            or Path(__file__).absolute() != root / 'stage2/matched_repeat_completion.py'):
        raise ValueError('Own fixed native baseline completion reader required')
    relative = operation_state(operation); folder = root / relative
    directory_id = evidence.bootstrap.directories(folder, private=True)
    names = {'intent.json', 'service-started.json', 'service.log', 'prerequisites.json', 'accepted.json', 'result.json'}
    retained = {relative + '/' + n: evidence.read(root, relative + '/' + n)
        for n in names if n != 'service.log'}
    records = {Path(n).name: evidence.bootstrap.loads(v[0]) for n, v in retained.items()}
    intent = records['intent.json']
    expected = base(harness, intent.get('nonce'), files, intent.get('operator_commit'), operation)
    if set(intent) != set(expected) | {'relay_process', 'created_utc'}:
        raise ValueError('Exact baseline operation intent required')
    for key, value in expected.items(): same(intent[key], value)
    _utc(intent['created_utc'])
    for process in (intent['relay_process'], records['service-started.json'].get('native_process')):
        if (type(process) is not dict or set(process) != {'pid', 'start_ticks'}
                or any(type(v) is not int or v <= 0 for v in process.values())):
            raise ValueError('Exact retained process identity required')
    process = records['service-started.json']['native_process']
    invocation = records['service-started.json'].get('invocation_id')
    if type(invocation) is not str or not re.fullmatch('[a-f0-9]{32}', invocation):
        raise ValueError('Actual baseline start invocation required')
    same(records['service-started.json'], dict(expected, native_process=process, invocation_id=invocation))
    prerequisites = records['prerequisites.json']; same(prerequisites['inputs'], files)
    same(prerequisites['harness'], harness)
    prior = prerequisites['predecessor']
    recovered = prerequisites['completed_recovery']
    if (recovered.get('kind') != 'live_completed_recovery_for_baseline_not_admission'
            or recovered.get('harness') != harness or recovered.get('operator_commit') != expected['operator_commit']
            or recovered.get('paid_launch_ready') is not False):
        raise ValueError('Actual completed recovery was not bound into the baseline operation')
    for name in ('recovery_document_sha256', 'archive_sha256'): policy._hash(recovered.get(name))
    same(records['accepted.json'], dict(expected,
        kind='baseline_handoff_committed_operation_accepted_not_completed', native_process=process,
        prerequisites_sha256=hashlib.sha256(retained[relative + '/prerequisites.json'][0]).hexdigest(),
        operator_document_sha256=prior['operator_document_sha256'], archive_sha256=prior['streamed_backup']['sha256'],
        recovery_document_sha256=recovered['recovery_document_sha256'], recovery_archive_sha256=recovered['archive_sha256']))
    terminal = policy.QUALIFIER_RESULT_FILE
    if operation == 'run-repeat':
        from run_matched_repeat import RESULT
        terminal = RESULT
    result = records['result.json']
    if set(result) != set(expected) | {'kind', 'terminal_files', 'log_files', 'completed_utc'}:
        raise ValueError('Exact completed baseline service record required')
    for key, value in expected.items(): same(result[key], value)
    same(result['kind'], 'baseline_service_operation_finished_not_completed_study_audit')
    _utc(result['completed_utc'])
    if (set(result['terminal_files']) != {RT + terminal}
            or set(result['log_files']) != {relative + '/service.log'}):
        raise ValueError('Actual terminal and log bindings required')
    retained.update(transport_failure(root, operation, expected))
    names |= {Path(n).name for n in retained}
    bound, identities = evidence.capture(root, [relative + '/' + n for n in names])
    for name, digest in {**result['terminal_files'], **result['log_files']}.items():
        policy._hash(digest)
        if name in bound: same(bound[name], digest)
        bound[name] = digest
    identities = evidence.extend(root, bound, identities)
    state = manager(root, expected['unit'])
    if (state['InvocationID'] != invocation or state['ActiveState'] != 'active'
            or state['SubState'] != 'exited' or state['MainPID'] != '0'
            or state['ExecMainPID'] != str(process['pid']) or state['Result'] != 'success'
            or state['ExecMainCode'] != '1' or state['ExecMainStatus'] != '0'):
        raise ValueError('Native baseline operation has not successfully exited')
    process_ended(process)
    if manager(root, expected['unit']) != state:
        raise ValueError('Completed baseline unit identity changed')
    evidence.check(root, files); evidence.check(root, bound, identities)
    if (evidence.bootstrap.directories(folder, private=True) != directory_id
            or {p.name for p in folder.iterdir()} != names
            or any(evidence.read(root, n) != value for n, value in retained.items())):
        raise ValueError('Completed baseline evidence changed or contains partial/failure state')
    return dict(files=bound, identities=identities, paid_launch_ready=False)

"""Separate read-only phase evidence for the frozen C0-NC final89.

This is NOT a completed-block collector, native qualification, archive or
dispatch witness. A future completed audit must authenticate the original
lineage, require an inactive service and hold all ancestor locks before using
this reader, then recheck these bytes and absences before returning. Nothing
here changes the frozen collector, execution sources or retained results.
"""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat

import local_trace

KIND = 'no_cutoff_final_phase_evidence_not_completed_audit'
AMENDMENT = 'c0-nc-final-setup-only-reporting-v1'
MODEL = '75718eac81a70390e879743b3c760e942281ac205f577960beec845d50057238'
SOURCE_SET = '4f73ab4083b76f555ff3bf695d7fed87ddbf4e5982551473418b8005eaf24d05'
QUALIFICATION = 'b3e05d9c216463b044e3b264aa449cecb92d8b9bd8cbc33b77189e434107087e'
REGISTRATION = '17a4139c4f68b2e6d8e5b62db910242e3562662192c13da51e62f53441f764b2'
QUALIFICATION_FILE = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
REGISTRATION_FILE = '01545d5d91cd45f7faa1f0a6a903b363774adf2c44a20add5624ec8bd55b809f'
RUNTIME_FILE = '4f52ed95689408f5407df8c0b612eac81af8da39d9f5c1933d87d972e8b5d26c'
FROZEN_HELPERS = {
    'export_no_cutoff_final.py': 'c82731f7b5a70b11612fccd3c555deee54368d98c6087ced53d26526252b9f3e',
    'local_trace.py': 'c40f85dc6a7479531d1b818b89e72934dc571f28d2fa56746911d3e522d6d0e1',
    'trial_execution.py': 'ea3bbc63513db0a0a1b47c054d81b47a50a7b90fc479f4218653f1582339b924'}
RT = '.runtime/stage2/'
PHASES = ('setup', 'agent', 'verifier')
ROW_FIELDS = frozenset({'trial_id', 'task_id', 'harness', 'status', 'reward',
    'agent_error_type', 'verifier_error_type', 'setup_seconds', 'agent_seconds',
    'verifier_seconds', 'phase_observation', 'official_agent_timeout_seconds',
    'official_verifier_timeout_seconds', 'setup_timeout_seconds', 'completed_utc',
    'model_requests', 'generation_timings', 'missing_generation_timings', 'result_sha256'})
REPORT_FIELDS = frozenset({'kind', 'amendment_sha256', 'reporting_source_files', 'row',
    'file_sha256', 'absent_paths', 'directory_entries', 'paid_launch_ready', 'completed_final_audit'})


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def contract():
    return dict(amendment=AMENDMENT, execution_source_set_sha256=SOURCE_SET,
        qualification_sha256=QUALIFICATION, registration_sha256=REGISTRATION,
        qualification_file_sha256=QUALIFICATION_FILE, registration_file_sha256=REGISTRATION_FILE,
        runtime_file_sha256=RUNTIME_FILE,
        unchanged_helpers=dict(FROZEN_HELPERS), setup_timeout_seconds=900,
        permitted_absence='agent_and_verifier_not_run_after_proven_setup_failure',
        unexecuted_phase_seconds=None, missing_verifier_reward=None,
        missing_required_evidence='reject_not_zero', results_rewritten=False,
        task_replay=False, historical_scores_changed=False, paid_launch_ready=False)


def _number(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0 or positive and value == 0:
        raise ValueError('Finite phase measurement or official allowance required')
    return value


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{64}', value):
        raise ValueError('Exact file hash required')
    return value


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate phase evidence field')
        value[key] = item
    return value


def _loads(raw):
    def invalid(_):
        raise ValueError('Non-finite JSON evidence refused')
    try:
        value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=invalid)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError('Valid private JSON evidence required') from error
    if not isinstance(value, dict):
        raise ValueError('Object phase evidence required')
    return value


def _path(root, name):
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.\-/]+', name)
            or PurePosixPath(name).is_absolute() or str(PurePosixPath(name)) != name
            or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ValueError('Normalised relative evidence path required')
    if not root.is_absolute() or root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise ValueError('Regular canonical evidence root required')
    current = root
    for part in name.split('/'):
        current /= part
        if current.is_symlink():
            raise ValueError('Symlinked phase evidence refused')
    return current


def _file(root, name, files, *, parse=False, expected=None):
    path = _path(root, name)
    try:
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1
                    or name.startswith('.runtime/') and (before.st_uid != os.getuid() or before.st_mode & 0o077)):
                raise ValueError('Owned private single-link phase evidence required')
            raw = stream.read() if parse else None
            sha = hashlib.sha256(raw).hexdigest() if parse else hashlib.file_digest(stream, 'sha256').hexdigest()
            after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError('Phase evidence changed while reading')
    except OSError as error:
        raise ValueError('Required phase evidence unavailable') from error
    if expected is not None and sha != _hash(expected) or name in files and files[name] != sha:
        raise ValueError('Bound phase evidence changed')
    files[name] = sha
    return _loads(raw) if parse else sha


def _inventory(root, name, absent, directories, *, optional=False):
    path = _path(root, name)
    if not path.exists() and optional:
        absent.append(name)
        return []
    if not path.is_dir():
        raise ValueError('Actual phase evidence directory required')
    names = sorted(p.name for p in path.iterdir())
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]+\.json', n) or not _path(root, name + '/' + n).is_file() for n in names):
        raise ValueError('Only regular retained JSON producers allowed')
    directories[name] = names
    return [name + '/' + n for n in names]


def _reporting_sources():
    paths = {'no_cutoff_final_phase_audit.py': Path(__file__), 'local_trace.py': Path(local_trace.__file__),
        'protocols/custom_final_phase_reporting_20260928.md': Path(__file__).parent / 'protocols/custom_final_phase_reporting_20260928.md'}
    result = {}
    for name, path in paths.items():
        if path.is_symlink() or not path.is_file():
            raise ValueError('Regular reporting source required')
        result[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    if result['local_trace.py'] != FROZEN_HELPERS['local_trace.py']:
        raise ValueError('Use the unchanged qualified trace validator')
    return result


def _error(value):
    if value is not None and (not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Za-z0-9_]*', value)):
        raise ValueError('Only retained exception class names allowed')
    return value or ''


def _phase_row(result, events, lifecycle, timings, requests, limits):
    """Evidence semantics, never authority to collect, back up or dispatch."""
    identity = {k: result[k] for k in ('trial_id', 'task_id', 'harness', 'model_protocol_sha256')}
    for event in events:
        local_trace.validate(event)
        _number(event['metrics'].get('duration_seconds'))
        if (event['trial_id'] != identity['trial_id'] or event['task_id'] != identity['task_id']
                or event['harness'] != 'C0-NC' or event['protocol_sha256'] != MODEL):
            raise ValueError('Trace identity differs from retained final result')
    if sorted(e['sequence'] for e in events) != list(range(len(events))):
        raise ValueError('Complete unique phase event sequence required')
    phase = {k: [e for e in events if e['kind'] == k] for k in ('trial', 'cleanup', *PHASES)}
    if any(len(phase[k]) != 1 for k in ('trial', 'cleanup', 'setup')):
        raise ValueError('Required trial, setup or cleanup event missing or duplicated')
    trial = phase['trial'][0]
    if any(not trial['started_ns'] <= e['started_ns'] <= e['ended_ns'] <= trial['ended_ns'] for e in events):
        raise ValueError('Phase event outside actual trial lifetime')
    if phase['cleanup'][0]['status'] != 'ok' or any(result.get(k) is not True for k in
            ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
        raise ValueError('Retained revocation and cleanup required')
    if result.get('cleanup_errors') != [] or result.get('trace_errors'):
        raise ValueError('Incomplete cleanup or trace cannot be reported as complete')
    for k in ('error_type', 'revocation_error_type', 'teardown_error_type', 'bridge_error_type'):
        if result.get(k) is not None:
            raise ValueError('Unexpected outer lifecycle failure requires separate review')
    seconds = result.get('phase_seconds')
    if not isinstance(seconds, dict):
        raise ValueError('Actual measured phase durations required')
    error = _error(result.get('agent_error_type')); verifier_error = _error(result.get('verifier_error_type'))
    setup_only = result.get('status') == 'setup_failed'
    if setup_only:
        if (not error or verifier_error or result.get('verifier_result') is not None or set(seconds) != {'setup'}
                or len(events) != 3 or phase['agent'] or phase['verifier'] or requests or timings or lifecycle is not None):
            raise ValueError('Setup-only absence must be proven by actual phase, request and deadline evidence')
        reward = None
        expected_status = 'timeout' if error == 'TimeoutError' else 'error'
        if phase['setup'][0]['status'] != expected_status or trial['status'] != 'error':
            raise ValueError('Setup failure status differs from its trace')
        if error == 'TimeoutError' and _number(seconds['setup']) < 900 - .1:
            raise ValueError('Setup timeout did not consume its qualified allowance')
    else:
        if set(seconds) != set(PHASES) or any(len(phase[k]) != 1 for k in PHASES):
            raise ValueError('Missing executed-phase evidence is not a not-run phase')
        if result.get('status') not in ('verified', 'verifier_failed') or phase['setup'][0]['status'] != 'ok':
            raise ValueError('Unsupported retained lifecycle requires separate review')
        verified = result.get('verifier_result')
        if verified is not None and (not isinstance(verified, dict)
                or verified.get('rewards') is not None and not isinstance(verified['rewards'], dict)):
            raise ValueError('Actual verifier result object required')
        reward = ((verified or {}).get('rewards') or {}).get('reward')
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Only an actual binary verifier outcome may be reported')
        if (result['status'] == 'verified' and (verifier_error or not isinstance(verified, dict))
                or result['status'] == 'verifier_failed' and (not verifier_error or verified is not None)
                or phase['verifier'][0]['reward'] != reward
                or phase['agent'][0]['status'] != ('timeout' if error == 'TimeoutError' else 'error' if error else 'ok')
                or phase['verifier'][0]['status'] != ('timeout' if verifier_error == 'TimeoutError' else 'error' if verifier_error else 'ok')
                or trial['status'] != ('ok' if result['status'] == 'verified' else 'error')):
            raise ValueError('Retained verifier and phase statuses disagree')
        if (not isinstance(lifecycle, dict) or lifecycle.get('trial_id') != result['trial_id']
                or lifecycle.get('model_protocol_sha256') != MODEL
                or not isinstance(lifecycle.get('boot_id'), str) or not lifecycle['boot_id']):
            raise ValueError('Actual original agent deadline record required')
        _number(lifecycle.get('deadline_monotonic'), positive=True)
        deadline = _number(lifecycle.get('deadline_utc'), positive=True)
        if abs(deadline - phase['agent'][0]['started_ns'] / 1e9 - limits['agent_timeout_seconds']) >= .1:
            raise ValueError('Agent deadline differs from the official allowance')
        if error == 'TimeoutError' and _number(seconds['agent']) < limits['agent_timeout_seconds'] - .1:
            raise ValueError('Agent timeout did not consume its official allowance')
        if verifier_error == 'TimeoutError' and _number(seconds['verifier']) < limits['verifier_timeout_seconds'] - .1:
            raise ValueError('Verifier timeout did not consume its official allowance')
    for kind, value in seconds.items():
        duration = phase[kind][0]['metrics'].get('duration_seconds')
        _number(value); _number(duration)
        if type(value) is not type(duration) or value != duration:
            raise ValueError('Recorded monotonic duration differs from its phase trace')
    ordered = [phase[k][0] for k in (('setup', 'cleanup') if setup_only else (*PHASES, 'cleanup'))]
    if any(a['ended_ns'] > b['started_ns'] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Sequential native phases overlap or are out of order')
    generations = [e for e in events if e['kind'] == 'generation']
    def timing_key(value):
        return (value['started_ns'], value['ended_ns'], value['status'], value['seconds'])
    for timing in timings:
        if (any(type(timing.get(k)) is not int for k in ('started_ns', 'ended_ns'))
                or not trial['started_ns'] <= timing['started_ns'] <= timing['ended_ns'] <= trial['ended_ns']
                or timing.get('status') not in ('ok', 'error', 'timeout', 'interrupted')):
            raise ValueError('Actual model timing lies outside retained lifecycle')
        _number(timing.get('seconds'))
    traced = [dict(started_ns=e['started_ns'], ended_ns=e['ended_ns'], status=e['status'],
        seconds=e['metrics'].get('duration_seconds')) for e in generations]
    if Counter(map(timing_key, timings)) != Counter(map(timing_key, traced)) or len(timings) > requests:
        raise ValueError('Actual model timing and generation trace evidence disagree')
    summary = result.get('trace', {})
    billing = result.get('billing', {})
    if not isinstance(summary, dict) or not isinstance(billing, dict):
        raise ValueError('Actual trace and accounting summaries required')
    counts = dict(events=len(events), generations=len(generations), missing_generation_timings=requests - len(timings))
    if (summary.get('status') != 'metadata_spool_not_cloud_export'
            or any(type(summary.get(k)) is not int or summary[k] != v for k, v in counts.items())
            or type(summary.get('unknown_cost_requests')) is not int
            or not 0 <= summary['unknown_cost_requests'] <= requests
            or type(billing.get('requests')) is not int or billing['requests'] != requests
            or type(billing.get('unknown_cost_requests')) is not int
            or billing['unknown_cost_requests'] != summary['unknown_cost_requests']
            or type(trial['metrics'].get('requests')) is not int or trial['metrics']['requests'] != requests):
        raise ValueError('Actual trace and physical request counts disagree')
    row = {k: result[k] for k in ('trial_id', 'task_id', 'harness', 'status')}
    row.update(reward=int(reward) if reward is not None else None, agent_error_type=error,
        verifier_error_type=verifier_error, phase_observation={k: 'measured' if k in seconds else 'not_run_setup_failed' for k in PHASES},
        **{k + '_seconds': seconds.get(k) for k in PHASES}, setup_timeout_seconds=900,
        official_agent_timeout_seconds=limits['agent_timeout_seconds'],
        official_verifier_timeout_seconds=limits['verifier_timeout_seconds'], model_requests=requests,
        generation_timings=len(timings), missing_generation_timings=requests - len(timings),
        completed_utc=datetime.fromtimestamp(trial['ended_ns'] / 1e9, timezone.utc).isoformat())
    return row


def read_phase_evidence(root, trial_id):
    """Read actual private bytes. The caller still owes the full locked audit."""
    root = Path(root); files = {}; absent = []; directories = {}
    reporting = _reporting_sources()
    proof = _file(root, RT + 'no-cutoff-final-qualification.json', files, parse=True, expected=QUALIFICATION_FILE)
    block = _file(root, RT + 'no-cutoff-final-matrix.json', files, parse=True, expected=REGISTRATION_FILE)
    host = _file(root, RT + 'no-cutoff-final-runtime.json', files, parse=True, expected=RUNTIME_FILE)
    if (fingerprint(proof) != QUALIFICATION or fingerprint(block) != REGISTRATION
            or fingerprint(host) != proof['runtime_identity_sha256']
            or fingerprint(proof['sources']) != SOURCE_SET
            or proof['sources_sha256'] != SOURCE_SET or proof['setup_timeout_seconds'] != 900
            or block['qualification_sha256'] != QUALIFICATION or block['sources_sha256'] != SOURCE_SET):
        raise ValueError('Exact frozen final anchors required')
    if any(proof['sources'].get(k) != v for k, v in FROZEN_HELPERS.items()):
        raise ValueError('Frozen execution and original collector must stay unchanged')
    for name, sha in proof['sources'].items():
        _file(root, 'stage2/' + name, files, expected=sha)
    cells = [c for c in block['cells'] if c['trial_id'] == trial_id]
    if len(cells) != 1 or cells[0]['harness'] != 'C0-NC':
        raise ValueError('Exactly one actual registered final task required')
    cell = cells[0]; trial = RT + 'scored-trials/' + trial_id
    result = _file(root, trial + '/result.json', files, parse=True)
    started = _file(root, trial + '/started.json', files, parse=True)
    identity = dict(trial_id=trial_id, task_id=cell['task_id'], harness='C0-NC', stage='final',
        custom_study='custom-no-cutoff-final-20260928', custom_registration_sha256=REGISTRATION,
        model_protocol_sha256=MODEL, gateway_image_id=proof['gateway_image'], accounting_mode='provider-credit-only')
    if any(v.get(k) != value for v in (result, started) for k, value in identity.items()):
        raise ValueError('Actual start/result identity differs from the frozen registration')
    if (started.get('status') != 'starting' or result.get('started_utc') != started.get('started_utc')
            or result.get('project') != started.get('project')
            or not isinstance(result.get('project'), str) or not re.fullmatch(r'uts-scored-[a-f0-9]{12}', result['project'])):
        raise ValueError('Actual retained start and final result disagree')
    limits = host['task_inventory'][cell['task_id']]
    for k in ('agent_timeout_seconds', 'verifier_timeout_seconds'):
        _number(limits.get(k), positive=True)
    if result.get('task_image_id') != limits['image_id']:
        raise ValueError('Retained task image differs from its qualified identity')
    events = []
    for name in _inventory(root, trial + '/traces', absent, directories):
        event = _file(root, name, files, parse=True)
        if Path(name).stem != event.get('event_id'):
            raise ValueError('Actual trace filename differs from its event identity')
        events.append(event)
    accounting = _inventory(root, RT + 'scored-attempts/' + trial_id, absent, directories, optional=True)
    requests = {n.removesuffix('.request.json') for n in accounting if n.endswith('.request.json')}
    timings = []
    for name in accounting:
        if name.endswith('/provider-stop.json'):
            raise ValueError('Retained provider stop requires separate inspection')
        if result.get('status') == 'setup_failed' and not name.endswith('/started.json'):
            raise ValueError('Setup-only outcome contains unexpected request evidence')
        if name.endswith('.timing.json'):
            if name.removesuffix('.timing.json') not in requests:
                raise ValueError('Orphaned generation timing refused')
            timings.append(_file(root, name, files, parse=True))
        else:
            _file(root, name, files)  # Raw requests/responses are hashed, never parsed or returned.
    lifecycle_name = RT + 'retry-lifecycle/' + trial_id + '.json'
    lifecycle_path = _path(root, lifecycle_name)
    if lifecycle_path.exists():
        lifecycle = _file(root, lifecycle_name, files, parse=True)
    else:
        lifecycle = None; absent.append(lifecycle_name)
    row = _phase_row(result, events, lifecycle, timings, len(requests), limits)
    row['result_sha256'] = files[trial + '/result.json']
    report = dict(kind=KIND, amendment_sha256=fingerprint(contract()), reporting_source_files=reporting,
        row=row, file_sha256=files, absent_paths=sorted(absent), directory_entries=directories,
        paid_launch_ready=False, completed_final_audit=False)
    recheck(root, report)
    return report


def recheck(root, report):
    """File/absence reread only, never fresh lineage or completed-audit proof."""
    root = Path(root)
    if (set(report) != REPORT_FIELDS or report['kind'] != KIND or report['paid_launch_ready'] is not False
            or report['completed_final_audit'] is not False or report['amendment_sha256'] != fingerprint(contract())
            or report['reporting_source_files'] != _reporting_sources() or set(report['row']) != ROW_FIELDS):
        raise ValueError('Exact non-admitting phase evidence record required')
    for name, sha in report['file_sha256'].items():
        _file(root, name, {}, expected=sha)
    for name in report['absent_paths']:
        if _path(root, name).exists():
            raise ValueError('Previously absent phase evidence appeared')
    for name, entries in report['directory_entries'].items():
        actual = {}; _inventory(root, name, [], actual)
        if actual[name] != entries:
            raise ValueError('Actual phase evidence inventory changed')
    return dict(kind='phase_files_rechecked_not_completed_audit', paid_launch_ready=False)

"""Fixed Mac allowlisted export of the amended final, never repeat admission.

Both entries perform a fresh native completed audit and reread the ONE existing
private archive. No caller snapshot, receipt, root, callback or saved-proof mode.
Do not invoke until the complete amended handoff route is bound and final89 is
inactive. Old collectors, exports and execution sources remain unchanged.
"""
from datetime import datetime, timezone
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat

import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch

PUBLIC = 'stage2/results/custom-no-cutoff-final-20260928'
DESTINATION = PUBLIC + '/c0-nc'
STATE = '.runtime/netcup/custom-no-cutoff-final89-export-20260928'
# Existing published prerequisites, pinned now for this separate reporting
# route. These are NOT additions to historical native qualification.
PREREQUISITES = {
    PUBLIC + '/qualification.json': 'cdf5adc4d784047c9d8a470cc417c10e89280ca0dbed6b54ba5a5a4ed9221657',
    PUBLIC + '/registration-c0-nc.json': '668a06beeb3ee3727687b46f05dbc1cb83faf98326430ea05a07137ce0eb40a9',
    PUBLIC + '/lineage.json': '0b4f1f90b8bd265c7695382a6fd9fd586ddf04460978ecbf3c09eb21411fc77e',
    PUBLIC + '/credit-policy.json': 'c8fed210aba93336b16d5248bfb030f6c7539ad4d001dc8094218f714ff3a167'}
OUTPUTS = frozenset({'summary.json', 'trials.json', 'trials.csv'})
BACKUP_FILES = frozenset({'intent.json', 'snapshot.json', 'evidence.tar.gz', 'backup.json'})
CSV_FIELDS = ('trial_id', 'task_id', 'harness', 'reward', 'status', 'started_utc', 'completed_utc',
    'agent_error_type', 'verifier_error_type', 'setup_seconds', 'agent_seconds', 'verifier_seconds',
    'setup_observation', 'agent_observation', 'verifier_observation', 'setup_timeout_seconds',
    'official_agent_timeout_seconds', 'official_verifier_timeout_seconds', 'official_cpus', 'official_memory_mb',
    'model_requests', 'accepted_model_responses', 'interrupted_requests', 'error_requests',
    'other_unaccepted_requests', 'http_429_requests', 'transport_error_requests', 'retry_records',
    'known_cost_usd', 'total_cost_usd', 'unknown_cost_requests', 'known_input_tokens', 'input_tokens',
    'known_output_tokens', 'output_tokens', 'generation_timings', 'missing_generation_timings',
    'cleanup_complete', 'model_revoked', 'result_sha256')


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def _operator(commit):
    bindings = launch._prepare(commit)
    for module in (producer, receiver):
        if Path(module.__file__).absolute() != launch.REPO / 'stage2' / (module.__name__ + '.py'):
            raise ValueError('Use the bound Mac export helpers')
    if Path(__file__).absolute() != launch.REPO / 'stage2/no_cutoff_final_export.py':
        raise ValueError('Use the fixed Mac exporter')
    for name, sha in PREREQUISITES.items():
        launch._raw(name, sha)
        if _hash(launch._git('show', commit + ':' + name)) != sha:
            raise ValueError('Public prerequisites must match the current committed revision')
    return {**bindings, 'local': {**bindings['local'], **PREREQUISITES}}


def _private_folder(name, entries=None):
    path = phase._path(launch.REPO, name)
    receiver._parents(); receiver._directory(path)
    if entries is not None and {p.name for p in path.iterdir()} != set(entries):
        raise ValueError('Exact completed private inventory required; partial evidence is not success')
    return path


def _public_folder(existing):
    folder = phase._path(launch.REPO, DESTINATION)
    current = folder.parent
    while current != launch.REPO:
        s = current.lstat()
        if (not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o022):
            raise ValueError('Protected owned public parent required')
        current = current.parent
    if existing:
        s = folder.lstat()
        if (not stat.S_ISDIR(s.st_mode) or s.st_uid != os.getuid() or s.st_mode & 0o022
                or {p.name for p in folder.iterdir()} != OUTPUTS):
            raise ValueError('Exact completed public export inventory required')
    elif folder.exists():
        raise ValueError('Existing or partial public export must not be overwritten or retried')
    return folder


def _revision(commit, bindings):
    if not isinstance(commit, str) or not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('Exact retained operator revision required')
    # Later result/documentation commits may advance HEAD without changing the
    # already archived reporting bundle. Read the old commit, not a saved flag.
    sources = {n: h for n, h in bindings['local'].items() if n.startswith('stage2/')}
    for name, sha in {**sources, **PREREQUISITES}.items():
        if _hash(launch._git('show', commit + ':' + name)) != sha:
            raise ValueError('Retained operator revision does not bind current reporting bytes')


def _read_backup(bindings):
    folder = _private_folder(receiver.DESTINATION, BACKUP_FILES)
    identity = (receiver._parents(), receiver._directory_id(folder))
    raw = {n: launch._raw(receiver.DESTINATION + '/' + n) for n in BACKUP_FILES if n != 'evidence.tar.gz'}
    intent, data, backup = (phase._loads(raw[n]) for n in ('intent.json', 'snapshot.json', 'backup.json'))
    if set(intent) != {'kind', 'operator_commit', 'created_utc', 'reporting_source_files', 'automatic_resume', 'paid_launch_ready'}:
        raise ValueError('Exact original backup intent required')
    archive._same({k: v for k, v in intent.items() if k not in ('operator_commit', 'created_utc')},
        dict(kind='exclusive_amended_final_backup_operator_intent', reporting_source_files=bindings['reporting'],
            automatic_resume=False, paid_launch_ready=False))
    archive._utc(intent['created_utc']); _revision(intent['operator_commit'], bindings)
    archive.validate_snapshot(data, bindings['anchors'])
    archive._same(data['reporting_source_files'], bindings['reporting'])
    expected = dict(kind='verified_mac_amended_final_backup_not_admission', operator_commit=intent['operator_commit'],
        snapshot_file_sha256=_hash(raw['snapshot.json']), receipt=backup.get('receipt'), verification=backup.get('verification'),
        off_server_backup_verified=True, archive_export_and_handoff_integrated=False,
        full_runtime_restore_exercised=False, automatic_resume=False, paid_launch_ready=False)
    archive._same(backup, expected)
    # Strict receipt verification happens before any native request. Actual
    # archive members are read again below, after the fresh native audit.
    archive._receipt(data, backup['receipt'])
    hashes = {receiver.DESTINATION + '/' + n: _hash(value) for n, value in raw.items()}
    for name, sha in PREREQUISITES.items(): launch._raw(name, sha)
    hashes.update(PREREQUISITES)
    receiver._state(folder, identity)
    return dict(bindings=bindings, folder=folder, data=data, backup=backup, hashes=hashes, identity=identity)


def _recheck(capture):
    receiver._state(capture['folder'], capture['identity'])
    launch._recheck(capture['bindings'])
    _private_folder(receiver.DESTINATION, BACKUP_FILES)
    receiver._state(capture['folder'], capture['identity'])
    for name, sha in capture['hashes'].items(): launch._raw(name, sha)
    producer._digest(capture['folder'], 'evidence.tar.gz', capture['backup']['receipt']['sha256'])
    _private_folder(receiver.DESTINATION, BACKUP_FILES)
    receiver._state(capture['folder'], capture['identity'])
    launch._recheck(capture['bindings'])


def _capture(bindings):
    value = _read_backup(bindings)
    fresh = launch.collect(bindings['commit'])  # Actual audit, never a leaf/saved report.
    archive.validate_snapshot(fresh, bindings['anchors'])
    archive._same({k: v for k, v in fresh.items() if k != 'collected_utc'},
        {k: v for k, v in value['data'].items() if k != 'collected_utc'})
    if archive._utc(fresh['collected_utc']) < archive._utc(value['data']['collected_utc']):
        raise ValueError('Native audit predates the retained completed snapshot')
    checked = archive.verify_archive(value['folder'] / 'evidence.tar.gz', value['data'], value['backup']['receipt'])
    archive._same(checked, value['backup']['verification'])
    _recheck(value)
    return value


def _projection(capture):
    """Deterministic allowlist from already checked bytes; not an audit entry."""
    data = capture['data']; backup = capture['backup']
    # No raw result, exception text, trace, request, solution or private path
    # inventory is projected. JSON retains nulls; CSV uses empty cells plus
    # explicit phase-observation labels, never fabricated phase/cost zeroes.
    rows = [{k: row[k] for k in sorted(report.ROW_FIELDS)} for row in data['rows']]
    csv_rows = [{**{k: v for k, v in row.items() if k != 'phase_observation'},
        **{k + '_observation': v for k, v in row['phase_observation'].items()}} for row in rows]
    stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS, lineterminator='\n')
    writer.writeheader(); writer.writerows(csv_rows)
    summary = dict(kind='c0_nc_final89_reporting_environment_public_summary_v3', condition='C0-NC',
        candidate_version='stage2-candidate-0.5.0', intended=89, attempts_per_task=1, recovery_attempts_included=False,
        execution_source_set_sha256=phase.SOURCE_SET, qualification_sha256=phase.QUALIFICATION,
        qualification_file_sha256=phase.QUALIFICATION_FILE, registration_sha256=phase.REGISTRATION,
        registration_file_sha256=phase.REGISTRATION_FILE, runtime_file_sha256=phase.RUNTIME_FILE,
        archive_snapshot_collected_utc=data['collected_utc'], snapshot_sha256=phase.fingerprint(data),
        snapshot_file_sha256=backup['snapshot_file_sha256'],
        backup_record_sha256=capture['hashes'][receiver.DESTINATION + '/backup.json'],
        reporting_source_files=data['reporting_source_files'], amendment_sha256=data['amendment_sha256'],
        reporting_dependencies=data['reporting_dependencies'],
        reporting_environment=data['reporting_environment'],
        public_prerequisite_files=PREREQUISITES, results=data['aggregates']['full89'],
        development_subset=data['aggregates']['development20'], outside_development_subset=data['aggregates']['remaining69'],
        original_baselines=dict(primary=dict(harness='terminus-2', passed=52, intended=89),
            secondary=dict(harness='openhands', passed=44, intended=89), result_file_sha256=report.HISTORICAL_INPUTS[report.BASELINE_CSV],
            original_outcomes_retained=178, stopped_outcomes_retained=4,
            stopped_metadata_sha256=report.HISTORICAL_INPUTS[report.STOPPED_JSON],
            preserved_result_map_sha256=phase.fingerprint(data['preserved_result_files'])),
        private_backup=dict(verification=backup['verification'], operator_location='fixed_mac_checkout',
            existing_archive_reread=True, full_runtime_restore_exercised=False),
        completed_final_audit=True, off_server_backup_verified=True, paid_launch_ready=False,
        archive_export_and_handoff_integrated=False, full_benchmark_win_claimed=False,
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run',
        interpretation=['One registered attempt per task; missing verifier outcomes remain missing.',
            'Setup-only agent/verifier durations are null/not_run_setup_failed, not measured zero.',
            'Phase totals are measured subtotals with measured/not-run denominators.',
            'Known response-reported costs are not independent receipts; unknown totals remain null.',
            'Development20 was used during development; remaining69 and full89 are reported separately.',
            'No inherited validation score, best-of recovery selection or causal improvement claim.',
            'Five helpers are bound for current reporting, not added to historical qualification.',
            'This export is not a live predecessor witness or repeat admission.'])
    return {'summary.json': _json(summary), 'trials.json': _json(rows), 'trials.csv': stream.getvalue().encode()}


def _unused():
    folder = phase._path(launch.REPO, STATE)
    receiver._parents()
    if folder.exists(): raise ValueError('Retained export state forbids automatic repetition')
    return folder


def export(commit):
    """Fresh audit, existing archive read, then one exclusive public projection."""
    bindings = _operator(commit); _unused(); _public_folder(False)
    captured = _capture(bindings); files = _projection(captured)
    state = _unused(); target = _public_folder(False)
    state.mkdir(mode=0o700); receiver._sync(state.parent)
    identity = (receiver._parents(), receiver._directory_id(state))
    try:
        producer._save(state, 'intent.json', dict(kind='amended_final_export_intent', operator_commit=commit,
            reporting_source_files=bindings['reporting'], created_utc=datetime.now(timezone.utc).isoformat(),
            automatic_resume=False, paid_launch_ready=False))
        intent_sha, _ = producer._digest(state, 'intent.json')
        _recheck(captured)
        receiver._state(state, identity)
        target.mkdir(mode=0o755); receiver._sync(target.parent)
        for name, raw in files.items(): receiver._raw_save(target, name, raw)
        _recheck(captured)
        for name, raw in files.items(): launch._raw(DESTINATION + '/' + name, _hash(raw))
        _private_folder(STATE, {'intent.json'}); producer._digest(state, 'intent.json', intent_sha)
        receiver._state(state, identity)
        _public_folder(True)
        result = dict(kind='amended_final_public_export_not_admission', operator_commit=commit,
            snapshot_file_sha256=captured['backup']['snapshot_file_sha256'],
            public_files={DESTINATION + '/' + n: _hash(raw) for n, raw in files.items()},
            automatic_resume=False, paid_launch_ready=False, archive_export_and_handoff_integrated=False)
        producer._save(state, 'result.json', result)
        receiver._state(state, identity); _recheck(captured)
        return result
    except BaseException as error:
        try:
            receiver._state(state, identity)
            producer._save(state, 'failure.json', dict(kind='amended_export_inspection_required',
                error_type=type(error).__name__, automatic_resume=False, paid_launch_ready=False))
        except (OSError, ValueError): pass
        raise ValueError('Export incomplete or uncertain; inspect retained partial state without retry') from None


def _verified_capture(commit):
    """Internal actual audit/archive capture for the source-bound live sender."""
    bindings = _operator(commit); _public_folder(True)
    _private_folder(STATE, {'intent.json', 'result.json'})
    state = launch.REPO / STATE
    identity = (receiver._parents(), receiver._directory_id(state))
    raw = {n: launch._raw(STATE + '/' + n) for n in ('intent.json', 'result.json')}
    intent, result = (phase._loads(raw[n]) for n in ('intent.json', 'result.json'))
    if set(intent) != {'kind', 'operator_commit', 'reporting_source_files', 'created_utc', 'automatic_resume', 'paid_launch_ready'}:
        raise ValueError('Exact retained export intent required')
    archive._same({k: v for k, v in intent.items() if k not in ('operator_commit', 'created_utc')},
        dict(kind='amended_final_export_intent', reporting_source_files=bindings['reporting'],
            automatic_resume=False, paid_launch_ready=False))
    archive._utc(intent['created_utc']); _revision(intent['operator_commit'], bindings)
    captured = _capture(bindings); files = _projection(captured)
    expected = dict(kind='amended_final_public_export_not_admission', operator_commit=intent['operator_commit'],
        snapshot_file_sha256=captured['backup']['snapshot_file_sha256'],
        public_files={DESTINATION + '/' + n: _hash(value) for n, value in files.items()},
        automatic_resume=False, paid_launch_ready=False, archive_export_and_handoff_integrated=False)
    archive._same(result, expected)
    _recheck(captured); _private_folder(STATE, {'intent.json', 'result.json'}); _public_folder(True)
    for name, value in files.items(): launch._raw(DESTINATION + '/' + name, _hash(value))
    for name, value in raw.items(): launch._raw(STATE + '/' + name, _hash(value))
    _private_folder(STATE, {'intent.json', 'result.json'}); _public_folder(True)
    receiver._state(state, identity)
    captured['export_files'] = {**expected['public_files'],
        **{STATE + '/' + n: _hash(value) for n, value in raw.items()}}
    return captured, expected


def verify_export(commit):
    """Repeat actual audit/archive reads; saved export state is never authority."""
    return _verified_capture(commit)[1]

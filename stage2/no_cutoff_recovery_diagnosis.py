"""Read only the fixed retained final archive for setup-recovery diagnosis.

No collector, SSH, native operation, extraction, archive writer or paid entry.
Only three result records are parsed and three original sources are byte-bound;
model exchanges, instructions, solutions and verifier payloads are never parsed.
The output is historical diagnosis and a plan, not a fresh native witness.
"""
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import tarfile

import no_cutoff_recovery_plan as plan
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_reporting as launch

SOURCE_FILES = ('no_cutoff_recovery_plan.py', 'no_cutoff_recovery_diagnosis.py',
    'test_no_cutoff_recovery_plan.py', 'test_no_cutoff_recovery_diagnosis.py',
    'protocols/custom_setup_recovery_20260929.md',
    'matched_repeat_schedule.py', 'model_protocol.py')
ARCHIVE_SHA256 = '7e53dd3eb45bec457f81d59b694fd171a949fbf123f02baa14f4158d9634a400'
SNAPSHOT_SHA256 = '1e0855681c4a900d251ef44b6104876e246a71fe5cf502cb9a447e817afc7553'
BACKUP_SHA256 = 'e89db8545f072a44ab590df75ddce40e5f88e7ff6e8782607a247934cc1708f1'
PUBLIC_FILES = {
    'summary.json': '468043e2a2e375e3f15f4e6683b89121e0ee38beab235fa3d02926219c177881',
    'trials.json': '53b0da52330102e17aebc928cbc3b19466fc3125e8be9ec218862eeb46ca4fe0',
    'trials.csv': 'ecc5cf3e7a4220688a8bf87e97ed104f74dc810baa3ad8fc432e0d07c3ac9a72'}
EXPORT_STATE = {
    'intent.json': 'd9688ed924f0ad65a0726e111c714c03930f8d8ab1a303d332d83aa1ff528540',
    'result.json': '4cc52c1e1e4e6af7b5be6dad6b7aa2611c9dcf18c129e94990fc105335431555'}
EXECUTION_SOURCES = {
    'stage2/scored_trial.py': 'f645548a0b028121c02b020c4716c2190e5c860f871a8e503dc154207845ff5a',
    'stage2/trial_execution.py': 'ea3bbc63513db0a0a1b47c054d81b47a50a7b90fc479f4218653f1582339b924',
    'stage2/task_preparation.py': 'fb1cf6c9e3a6ee79579de2ebcbfd0f97cac39e989000bbb77b20a00f114b6815'}
MANIFEST_FILE = 'stage2/input_manifest.json'
MANIFEST_FILE_SHA256 = 'a33de38d1794617b2acc7c50b1f997da49c34b7df5032b481f023184e4aacbc7'


def _hash(raw):
    return hashlib.sha256(raw).hexdigest()


def _loaded(bindings):
    """Bind actual current project import origins/bytes, including late imports."""
    allowed = {**bindings['native'], **bindings['reporting'], **bindings['diagnosis_local']}
    root = launch.REPO / 'stage2'
    names = {p.stem for p in root.glob('*.py')}
    checked = set()
    for label, module in tuple(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if not filename:
            if label in names: raise ValueError('Project import has no source origin')
            continue
        path = Path(filename).absolute()
        if label not in names and not path.is_relative_to(root): continue
        if (path.parent != root or path.resolve() != path or path.suffix != '.py'
                or 'stage2/' + path.name not in allowed):
            raise ValueError('Unbound or other-checkout project import')
        name = 'stage2/' + path.name
        launch._raw(name, allowed[name]); checked.add(name)
    return checked


def _prepare(commit):
    bindings = export._operator(commit)
    if Path(__file__).absolute() != launch.REPO / 'stage2/no_cutoff_recovery_diagnosis.py':
        raise ValueError('Use the fixed source-bound Mac diagnosis reader')
    if Path(plan.__file__).absolute() != launch.REPO / 'stage2/no_cutoff_recovery_plan.py':
        raise ValueError('Use the same source-bound recovery plan')
    # These are CURRENT diagnosis controls, not members of the historical
    # archived reporter. Its retained revision must not be redefined by them.
    local = {}
    for name in SOURCE_FILES:
        name = 'stage2/' + name
        raw = launch._raw(name)
        if raw != launch._git('show', commit + ':' + name):
            raise ValueError('Recovery diagnosis and plan must be committed')
        local[name] = _hash(raw)
        if name in bindings['native'] and local[name] != bindings['native'][name]:
            raise ValueError('Inherited diagnosis dependency differs from original source')
    manifest = launch._raw(MANIFEST_FILE, MANIFEST_FILE_SHA256)
    if manifest != launch._git('show', commit + ':' + MANIFEST_FILE):
        raise ValueError('Current committed original manifest required')
    local[MANIFEST_FILE] = MANIFEST_FILE_SHA256
    result = {**bindings, 'diagnosis_local': local}
    _loaded(result)
    return result, plan.schedule(phase._loads(manifest))


def _publication(commit):
    export._public_folder(True)
    state = export._private_folder(export.STATE, EXPORT_STATE)
    identity = (receiver._parents(), receiver._directory_id(state))
    hashes = {export.STATE + '/' + n: h for n, h in EXPORT_STATE.items()}
    for name, expected in PUBLIC_FILES.items():
        name = export.DESTINATION + '/' + name
        raw = launch._raw(name, expected)
        if raw != launch._git('show', commit + ':' + name):
            raise ValueError('Original public results must already be committed')
        hashes[name] = expected
    for name, expected in hashes.items(): launch._raw(name, expected)
    receiver._state(state, identity)
    return hashes, identity


def _selected(capture):
    """Hash all archive bytes; parse only the six fixed infrastructure members."""
    wanted = dict(EXECUTION_SOURCES)
    for ordinal, task, sha in plan.TARGETS:
        trial = plan.original_id(ordinal, task)
        wanted[phase.RT + 'scored-trials/' + trial + '/result.json'] = sha
    for name, sha in wanted.items():
        if capture['data']['supporting_file_sha256'].get(name) != sha:
            raise ValueError('Original infrastructure/result byte anchor differs')
    found = {}; trial_files = {plan.original_id(i, t): set() for i, t, _ in plan.TARGETS}
    with producer._open(capture['folder'], 'evidence.tar.gz') as (handle, _):
        if hashlib.file_digest(handle, 'sha256').hexdigest() != ARCHIVE_SHA256:
            raise ValueError('Retained original archive changed')
        handle.seek(0)
        with tarfile.open(fileobj=handle, mode='r|gz') as packed:
            for member in packed:
                # This read follows the unchanged strict full archive verifier.
                # Even here, retain no unexpected member contents or raw names.
                for trial, names in trial_files.items():
                    prefix = phase.RT + 'scored-trials/' + trial + '/'
                    if member.isfile() and member.name.startswith(prefix):
                        names.add(member.name[len(prefix):])
                if member.name not in wanted: continue
                if member.name in found or not member.isfile() or not 0 < member.size <= 256 * 1024:
                    raise ValueError('Exact bounded original diagnostic member required')
                raw = packed.extractfile(member).read()
                if _hash(raw) != wanted[member.name]:
                    raise ValueError('Original diagnostic member changed')
                found[member.name] = raw
        handle.seek(0)
        if hashlib.file_digest(handle, 'sha256').hexdigest() != ARCHIVE_SHA256:
            raise ValueError('Archive changed across selected metadata reads')
    if set(found) != set(wanted):
        raise ValueError('Original diagnostic member missing')
    return found, trial_files


def _rows(capture, selected, trial_files):
    """Infer only the stage supported by exact original source/result bytes."""
    rows = {row['trial_id']: row for row in capture['data']['rows']}
    output = []
    for ordinal, task, sha in plan.TARGETS:
        trial = plan.original_id(ordinal, task)
        name = phase.RT + 'scored-trials/' + trial + '/result.json'
        result = phase._loads(selected[name]); row = rows[trial]
        expected = dict(trial_id=trial, task_id=task, harness='C0-NC', status='setup_failed',
            agent_error_type='RuntimeError', verifier_error_type=None, verifier_result=None,
            model_revoked=True, cleanup_errors=[], containers_removed=True,
            networks_removed=True, volumes_removed=True)
        if (any(result.get(k) != v or type(result.get(k)) is not type(v) for k, v in expected.items())
                or 'environment_preparation' in result
                or type(result.get('phase_seconds')) is not dict
                or set(result['phase_seconds']) != {'setup'}):
            raise ValueError('Retained result no longer proves failed pre-agent preparation')
        if (row['result_sha256'] != sha or row['status'] != 'setup_failed'
                or row['model_requests'] != 0 or row['reward'] is not None
                or row['agent_seconds'] is not None or row['verifier_seconds'] is not None
                or row['phase_observation'] != dict(setup='measured', agent='not_run_setup_failed',
                    verifier='not_run_setup_failed')
                or phase.fingerprint(result['phase_seconds']['setup']) != phase.fingerprint(row['setup_seconds'])):
            raise ValueError('Original result and audited setup-only evidence disagree')
        names = trial_files[trial]
        # No setup stdout/stderr or agent/verifier log survived in these trials.
        # Do not claim that a generic RuntimeError identifies its lower cause.
        if (not {'started.json', 'result.json', 'compose.json'}.issubset(names)
                or len(names) != 6
                or sum(n.startswith('traces/') and n.endswith('.json') for n in names) != 3):
            raise ValueError('Unexpected retained trial evidence needs separate inspection')
        output.append(dict(original_ordinal=ordinal, original_trial_id=trial, task_id=task,
            original_result_sha256=sha, original_status='setup_failed', original_reward=None,
            observed_error_type='RuntimeError', setup_seconds=row['setup_seconds'],
            measured_phases=['setup'], model_requests=0, agent_setup_entered=False,
            agent_run_entered=False, verifier_run_entered=False,
            established_failure_stage='prepare_environment_before_return',
            preparation_callback='task_preparation.refresh_package_metadata',
            lower_level_cause_established=False, command_exit_code_retained=False,
            command_output_retained=False, exception_message_or_stack_retained=False,
            original_model_revoked=True, original_owned_cleanup_complete=True))
    return output


def inspect(commit):
    """Read existing evidence; no fresh native audit, writes or admission."""
    bindings, schedule = _prepare(commit)
    publication, state_identity = _publication(commit)
    captured = export._read_backup(bindings)
    if (captured['backup']['snapshot_file_sha256'] != SNAPSHOT_SHA256
            or captured['hashes'][receiver.DESTINATION + '/backup.json'] != BACKUP_SHA256
            or captured['backup']['receipt']['sha256'] != ARCHIVE_SHA256):
        raise ValueError('Only the one completed original archive may be diagnosed')
    verified = archive.verify_archive(captured['folder'] / 'evidence.tar.gz',
        captured['data'], captured['backup']['receipt'])
    archive._same(verified, captured['backup']['verification'])
    selected, trial_files = _selected(captured)
    rows = _rows(captured, selected, trial_files)
    result = dict(kind='retained_original_setup_diagnosis_not_native_admission', schema_version=1,
        observed_utc=datetime.now(timezone.utc).isoformat(), operator_commit=commit,
        diagnosis_sources={n: bindings['diagnosis_local']['stage2/' + n] for n in SOURCE_FILES},
        original_execution_sources=EXECUTION_SOURCES.copy(), archive_sha256=ARCHIVE_SHA256,
        snapshot_file_sha256=SNAPSHOT_SHA256, backup_record_sha256=BACKUP_SHA256,
        original_public_files=PUBLIC_FILES.copy(), original_rows=rows,
        recovery_plan_sha256=plan.fingerprint(schedule), recovery_plan=schedule,
        current_archive_verified=True, fresh_native_audit_performed=False,
        historical_runtime_restore_exercised=False, task_solution_or_model_exchange_parsed=False,
        native_operation_performed=False, archive_created=False, original_evidence_changed=False,
        recovery_attempts_started=0, paid_launch_ready=False)
    # Reread actual source, private/public state and archive after all parsing.
    export._recheck(captured)
    export._public_folder(True); export._private_folder(export.STATE, EXPORT_STATE)
    for name, sha in publication.items(): launch._raw(name, sha)
    receiver._state(launch.REPO / export.STATE, state_identity)
    for name, sha in bindings['diagnosis_local'].items(): launch._raw(name, sha)
    _loaded(bindings)
    launch._recheck(bindings)
    return result

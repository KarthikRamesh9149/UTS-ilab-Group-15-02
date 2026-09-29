"""Fixed recovery capture: fresh original audit and the SAME existing archive.

No saved-proof input, archive writer, exporter, registration or paid entry.
Current recovery bindings stay separate from the immutable archived reporter.
"""
from copy import deepcopy
from pathlib import Path
import sys

import no_cutoff_recovery_policy as policy
import no_cutoff_final_archive as archive
import no_cutoff_final_backup as producer
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch

KIND = 'recovery_original_off_server_capture_not_admission'
FIELDS = frozenset({'kind', 'schema_version', 'operator_commit', 'successor_experiment',
    'predecessor', 'current_sources', 'local_files', 'native_files',
    'reporting_source_files', 'absent_paths', 'directory_entries',
    'preserved_result_files', 'paid_launch_ready'})
EXPORT_STATE = {
    'intent.json': 'd9688ed924f0ad65a0726e111c714c03930f8d8ab1a303d332d83aa1ff528540',
    'result.json': '4cc52c1e1e4e6af7b5be6dad6b7aa2611c9dcf18c129e94990fc105335431555'}


def audit_hash(data):
    return phase.fingerprint({k: v for k, v in data.items() if k != 'collected_utc'})


def _same_anchored(actual, expected):
    # Anchor values are exact byte strings; all other fields are JSON metadata.
    if actual['anchors'] != expected['anchors']:
        raise ValueError('Original anchor bytes changed across fresh capture')
    archive._same({k: v for k, v in actual.items() if k != 'anchors'},
        {k: v for k, v in expected.items() if k != 'anchors'})


def sources(root, final):
    """Read actual current bytes. This does not attest historical installation."""
    root = Path(root)
    names = set(policy.original_final(final)) | policy.REQUIRED_SOURCE_FILES
    bound = {n: phase._file(root, 'stage2/' + n, {}) for n in sorted(names)}
    policy.source_transition(final, bound)
    for name, sha in report.dependencies.FILES.items():
        if bound.get(name.removeprefix('stage2/')) != sha:
            raise ValueError('Current original reporting dependency changed')
    return bound


def loaded(root, bound):
    """Check all loaded project origins and actual bytes, including late imports."""
    stage = Path(root) / 'stage2'
    names = {p.stem for p in stage.glob('*.py')}
    checked = set()
    for label, module in tuple(sys.modules.items()):
        filename = getattr(module, '__file__', None)
        if not filename:
            if label in names:
                raise ValueError('Loaded project module has no source origin')
            continue
        path = Path(filename).absolute()
        if label not in names and path.name not in bound and not path.is_relative_to(stage):
            continue
        if (path.parent != stage or path.resolve() != path or path.suffix != '.py'
                or path.name not in bound):
            raise ValueError('Unbound or other-deployment recovery import')
        phase._file(Path(root), 'stage2/' + path.name, {}, expected=bound[path.name])
        checked.add(path.name)
    return checked


def predecessor(data, backup, manifest, snapshot_sha, backup_sha):
    """Projection is accepted only after real audit/archive calls by consumers."""
    value = dict(kind='recovery_original_final_evidence_not_admission', schema_version=1,
        successor_experiment=policy.EXPERIMENT, plan_sha256=policy.PLAN_SHA256,
        original_experiment=policy.plan.ORIGINAL_EXPERIMENT, harness=data['condition'],
        qualification_sha256=data['qualification_sha256'],
        registration_sha256=phase.fingerprint(data['registration']),
        sources_sha256=phase.fingerprint(data['sources']),
        retained_snapshot_sha256=snapshot_sha, audit_sha256=audit_hash(data),
        archive_sha256=backup['receipt']['sha256'], backup_record_sha256=backup_sha,
        reporter_commit=backup['operator_commit'], public_files=deepcopy(policy.PUBLIC_FILES),
        results_sha256={row['trial_id']: row['result_sha256'] for row in data['rows']},
        paid_launch_ready=False)
    return policy.validate_predecessor(value, manifest)


def _publication(commit):
    export._public_folder(True)
    state = export._private_folder(export.STATE, EXPORT_STATE)
    identity = (receiver._parents(), receiver._directory_id(state))
    files = {export.STATE + '/' + n: h for n, h in EXPORT_STATE.items()}
    files.update({export.DESTINATION + '/' + n: h for n, h in policy.PUBLIC_FILES.items()})
    for name, sha in files.items():
        raw = launch._raw(name, sha)
        if name.startswith('stage2/') and raw != launch._git('show', commit + ':' + name):
            raise ValueError('Original published results must be committed')
    receiver._state(state, identity)
    return files, identity


def _prepare(commit):
    bindings = export._operator(commit)
    if Path(__file__).absolute() != launch.REPO / 'stage2/no_cutoff_recovery_predecessor.py':
        raise ValueError('Use the fixed Mac recovery capture')
    final = archive._anchors(bindings['anchors'])[0]
    policy.original_final(final)
    manifest_raw = launch._raw('stage2/input_manifest.json', policy.INPUT_SHA256)
    manifest = phase._loads(manifest_raw); policy.cells(manifest)
    current = sources(launch.REPO, final)
    local = {'stage2/' + n: h for n, h in current.items()}
    local['stage2/input_manifest.json'] = policy.INPUT_SHA256
    for name, sha in local.items():
        raw = launch._raw(name, sha)
        if raw != launch._git('show', commit + ':' + name):
            raise ValueError('All current recovery sources must be committed')
        if name in bindings['local'] and bindings['local'][name] != sha:
            raise ValueError('Archived reporting and current source disagree')
    # Never merge these new sources into bindings['local'] before the old
    # archive/revision reader. New controls did not exist in a74e0dd.
    loaded(launch.REPO, current)
    receiver._previous_failure()
    publication, state = _publication(commit)
    retained = export._read_backup(bindings)  # Metadata only, before SSH.
    predecessor(retained['data'], retained['backup'], manifest,
        retained['hashes'][receiver.DESTINATION + '/snapshot.json'],
        retained['hashes'][receiver.DESTINATION + '/backup.json'])
    launch._recheck(bindings)
    return dict(bindings=bindings, current_sources=current, recovery_local=local,
        final=final, manifest=manifest, publication=publication, export_identity=state)


def _current(value):
    commit = value['bindings']['commit']
    launch._recheck(value['bindings'])
    if launch._git('rev-parse', 'origin/main').decode().strip() != commit:
        raise ValueError('Fetched main changed during recovery capture')
    for name, sha in value['recovery_local'].items():
        launch._raw(name, sha)
    if sources(launch.REPO, value['final']) != value['current_sources']:
        raise ValueError('Current recovery source inventory changed')
    receiver._previous_failure()
    files, identity = _publication(commit)
    if files != value['publication'] or identity != value['export_identity']:
        raise ValueError('Original export state changed during recovery capture')
    loaded(launch.REPO, value['current_sources'])


def _recheck(value):
    _current(value)
    # Actual same-archive byte reread, exact private inventories and all inputs.
    # The original verifier's historical revision bindings remain unchanged.
    export._recheck(value)
    for name, sha in value['export_files'].items():
        launch._raw(name, sha)
    _current(value)  # Source/input drift during the long archive read also refuses.


def _capture(commit):
    prepared = _prepare(commit)
    captured, _ = export._verified_capture(commit)  # ALWAYS actual fresh audit/archive.
    _same_anchored(captured['bindings'], prepared['bindings'])
    value = {**captured, **{k: v for k, v in prepared.items() if k != 'bindings'}}
    archive._same(value['data']['sources'], value['final']['sources'])
    for name, sha in value['bindings']['native'].items():
        if value['data']['supporting_file_sha256'].get(name) != sha:
            raise ValueError('Fresh audit lacks the exact original native binding')
    block = predecessor(value['data'], value['backup'], value['manifest'],
        value['hashes'][receiver.DESTINATION + '/snapshot.json'],
        value['hashes'][receiver.DESTINATION + '/backup.json'])
    local = {}
    for mapping in (value['bindings']['local'], value['recovery_local'],
            value['hashes'], value['export_files'],
            {receiver.DESTINATION + '/evidence.tar.gz': block['archive_sha256']}):
        report._merge(local, mapping)
    document = dict(kind=KIND, schema_version=1, operator_commit=commit,
        successor_experiment=policy.EXPERIMENT, predecessor=block,
        current_sources=value['current_sources'], local_files=local,
        native_files=value['data']['supporting_file_sha256'],
        reporting_source_files=value['data']['reporting_source_files'],
        absent_paths=value['data']['absent_paths'], directory_entries=value['data']['directory_entries'],
        preserved_result_files=value['data']['preserved_result_files'], paid_launch_ready=False)
    _recheck(value)
    return value, document


def capture(commit):
    """Fresh real audit/archive capture; result is not a durable admission token."""
    return deepcopy(_capture(commit)[1])

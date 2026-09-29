"""Fixed Mac capture for the explicitly amended final89 predecessor.

This route calls the actual export verifier's fresh audit and actual existing
archive read. A public verification return, saved document or receipt cannot
replace capture. No archive writer, saved-proof input, CLI or paid entry exists.
The old predecessor reader and frozen execution remain unchanged.
"""
from copy import deepcopy
from pathlib import Path

import matched_repeat_policy as policy
import matched_repeat_predecessor as old
import no_cutoff_final_archive as archive
import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_export as export
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_reporting as launch

KIND = 'amended_off_server_custom_final_predecessor_not_admission'
FIELDS = frozenset({'kind', 'schema_version', 'operator_commit', 'successor_harness', 'predecessors',
    'original_qualification_sha256', 'local_files', 'native_files', 'reporting_source_files',
    'absent_paths', 'directory_entries', 'preserved_result_files', 'paid_launch_ready'})


def _first(harness):
    if harness != 'terminus-2':
        raise ValueError('OpenHands requires its additional completed-Terminus audit/archive reader')


def _audit_hash(data):
    return phase.fingerprint({k: v for k, v in data.items() if k != 'collected_utc'})


def _predecessors(data, backup, manifest, backup_sha, harness):
    _first(harness)
    block = dict(experiment=policy.CUSTOM_FINAL_EXPERIMENT, harness='C0-NC',
        qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256,
        registration_sha256=policy.CUSTOM_FINAL_REGISTRATION_SHA256,
        sources_sha256=policy.CUSTOM_FINAL_SOURCES_SHA256,
        results_sha256={row['trial_id']: row['result_sha256'] for row in data['rows']},
        audit_sha256=_audit_hash(data), archive_sha256=backup['receipt']['sha256'],
        backup_record_sha256=backup_sha)
    value = dict(kind='authenticated_matched_repeat_predecessors_not_paid_admission',
        successor_harness=harness, schedule_sha256=policy.fingerprint(policy.schedule(manifest)),
        blocks=[block], paid_launch_ready=False)
    policy.validate_predecessors(value, manifest, harness)
    return value


def _prepare(commit, harness):
    _first(harness)
    bindings = export._operator(commit)
    if Path(__file__).absolute() != launch.REPO / 'stage2/matched_repeat_amended_predecessor.py':
        raise ValueError('Use the fixed source-bound Mac amended predecessor reader')
    # The old helper only reads original anchors/current sources. Neither its
    # old capture nor its old collector/backup assumptions are invoked.
    original = old._anchors(launch.REPO)
    for name, sha in original['native'].items():
        if bindings['native'].get(name) != sha:
            raise ValueError('Original anchors differ from the amended native bindings')
    local = dict(bindings['local'])
    for name, sha in original['local'].items():
        if name in local and local[name] != sha:
            raise ValueError('Reporting and repeat source bindings disagree')
        launch._raw(name, sha); local[name] = sha
    # Bind every current consumer, not just this new leaf/reporting module.
    for name, sha in local.items():
        if name.startswith('stage2/') and export._hash(launch._git('show', commit + ':' + name)) != sha:
            raise ValueError('Current repeat/handoff source must be committed on main')
    bindings = {**bindings, 'local': local}
    launch._recheck(bindings)
    return bindings, original


def _recheck(value):
    export._recheck(value)
    export._public_folder(True); export._private_folder(export.STATE, {'intent.json', 'result.json'})
    for name, sha in value['export_files'].items(): launch._raw(name, sha)
    export._public_folder(True); export._private_folder(export.STATE, {'intent.json', 'result.json'})
    # The potentially long archive reread must not hide source/input mutation
    # after the first source check. This is the sender's last pre-commit read.
    launch._recheck(value['bindings'])


def _capture(commit, harness):
    bindings, original = _prepare(commit, harness)
    # This internal operation always executes the actual launcher collector,
    # reads the retained archive and compares deterministic public bytes.
    # Its public metadata-only return is deliberately not accepted as input.
    value, _ = export._verified_capture(commit)
    for name, sha in value['bindings']['local'].items():
        if bindings['local'].get(name) != sha:
            raise ValueError('Operator bindings changed across actual audit/archive capture')
    value['bindings'] = bindings
    data = value['data']; backup = value['backup']
    archive._same(data['sources'], original['proof']['sources'])
    archive._same(data['registration'], original['block'])
    for name, sha in bindings['native'].items():
        if data['supporting_file_sha256'].get(name) != sha:
            raise ValueError('Amended audit does not bind exact original native bytes')
    local = {**bindings['local'], **value['hashes'], **value['export_files'],
        receiver.DESTINATION + '/evidence.tar.gz': backup['receipt']['sha256']}
    # Public output must already be committed and pushed before a successor
    # handoff; current HEAD equals the fetched origin/main in _prepare.
    for name, sha in value['export_files'].items():
        if name.startswith('stage2/') and export._hash(launch._git('show', commit + ':' + name)) != sha:
            raise ValueError('Completed public export must be committed before handoff')
    document = dict(kind=KIND, schema_version=1, operator_commit=commit, successor_harness=harness,
        original_qualification_sha256=policy.ORIGINAL_QUALIFICATION_SHA256,
        predecessors=_predecessors(data, backup, original['manifest'],
            value['hashes'][receiver.DESTINATION + '/backup.json'], harness),
        local_files=local, native_files=data['supporting_file_sha256'],
        reporting_source_files=data['reporting_source_files'], absent_paths=data['absent_paths'],
        directory_entries=data['directory_entries'], preserved_result_files=data['preserved_result_files'],
        paid_launch_ready=False)
    _recheck(value)
    if old._anchors(launch.REPO) != original:
        raise ValueError('Original and current repeat anchors changed during capture')
    launch._recheck(bindings)
    return value, document


def capture(commit, harness='terminus-2'):
    """Fresh actual native audit and existing archive read; no saved input."""
    return deepcopy(_capture(commit, harness)[1])

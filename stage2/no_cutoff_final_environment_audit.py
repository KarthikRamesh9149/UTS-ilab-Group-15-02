"""One exclusive v3 audit following reviewed environment isolation and installation.

Preserves the earlier failed transport directory. No deployment, backup, export,
caller root/callback, saved report or automatic retry is provided here.
"""
from datetime import datetime, timezone
from pathlib import Path

import no_cutoff_final_backup_operator as receiver
import no_cutoff_final_phase_audit as phase
import no_cutoff_final_report as report
import no_cutoff_final_reporting as launch
import no_cutoff_final_transport as transport

DESTINATION = '.runtime/netcup/custom-no-cutoff-final89-environment-audit-20260929'
_hash = transport._hash
_json = transport._json
_parents = receiver._parents

def _destination():
    path = phase._path(launch.REPO, DESTINATION)
    _parents()
    if path.exists() or path.is_symlink():
        raise ValueError('Existing or partial audit operation forbids another attempt')
    return path


def _directory_id(folder):
    receiver._directory(folder); s = folder.lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_uid, s.st_gid)


def _state(folder, identity, hashes):
    if (phase._path(launch.REPO, DESTINATION) != folder
            or (_parents(), _directory_id(folder)) != identity):
        raise ValueError('Audit state directory changed')
    if {p.name for p in folder.iterdir()} != set(hashes):
        raise ValueError('Exact retained audit inventory required')
    for name, sha in hashes.items(): launch._raw(DESTINATION + '/' + name, sha)


def _save(folder, identity, hashes, name, raw):
    _state(folder, identity, hashes); receiver._raw_save(folder, name, raw)
    hashes[name] = _hash(raw); _state(folder, identity, hashes)



def collect(commit):
    """ONE actual audit; save only fully validated output, otherwise failure."""
    bindings = launch._prepare(commit)
    if Path(__file__).resolve() != launch.REPO / 'stage2/no_cutoff_final_environment_audit.py':
        raise ValueError('Use the fixed source-bound environment audit operator')
    folder = _destination(); parents = _parents()
    launch.inspect_deployment(commit)
    launch._recheck(bindings); _destination()
    if _parents() != parents: raise ValueError('Audit parent changed during preflight')
    folder.mkdir(mode=0o700); receiver._sync(folder.parent)
    identity = (parents, _directory_id(folder)); hashes = {}; stage = 'intent'
    metadata = dict(status='not_started', automatic_resume=False)
    try:
        intent = dict(kind='one_shot_mac_reporting_environment_audit_v3', operator_commit=commit,
            created_utc=datetime.now(timezone.utc).isoformat(), reporting_root=str(report.REPORTING),
            reporting_source_files=bindings['reporting'], native_files=bindings['native'],
            current_dependencies=report.dependencies.contract(),
            reporting_environment=report.guard.environment_contract(),
            transport_seconds=transport.TRANSPORT_SECONDS, sample_seconds=transport.SAMPLE_SECONDS,
            automatic_resume=False, paid_launch_ready=False)
        _save(folder, identity, hashes, 'intent.json', _json(intent))
        launch._recheck(bindings); _state(folder, identity, hashes)
        stage = 'native_operation'
        data, raw, metadata = launch._audit(bindings)
        stage = 'final_source_recheck'; launch._recheck(bindings)
        stage = 'retaining_verified_output'
        _save(folder, identity, hashes, 'diagnostics.json', _json(metadata))
        _save(folder, identity, hashes, 'snapshot.json', raw)
        launch._recheck(bindings); _state(folder, identity, hashes)
        result = dict(kind='verified_completed_environment_audit_not_backup_or_admission_v3',
            operator_commit=commit, observed_utc=datetime.now(timezone.utc).isoformat(),
            snapshot_file_sha256=hashes['snapshot.json'], diagnostics_file_sha256=hashes['diagnostics.json'],
            elapsed_seconds=metadata['elapsed_seconds'], completed_final_audit_verified=True,
            off_server_backup_verified=False, paid_launch_ready=False, automatic_resume=False,
            full89=data['aggregates']['full89'])
        _save(folder, identity, hashes, 'result.json', _json(result))
        launch._recheck(bindings); _state(folder, identity, hashes)
        return result
    except BaseException as error:
        if isinstance(error, transport.AuditTransportError): metadata = error.metadata
        failure = dict(kind='incomplete_reporting_environment_audit_v3', stage=stage,
            error_type=transport._error_type(error), transport=metadata, automatic_resume=False,
            completed_final_audit_verified=False, paid_launch_ready=False,
            native_state_requires_inspection=True)
        try: _save(folder, identity, hashes, 'failure.json', _json(failure))
        except (OSError, ValueError): failure['failure_state_write_verified'] = False
        raise transport.AuditTransportError(failure) from None

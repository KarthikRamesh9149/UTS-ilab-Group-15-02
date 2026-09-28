"""Fresh native authentication of the original 80 and measured C0-NC 20.

Call authenticate BEFORE taking final ancestor locks: the unchanged revision
collector takes those same locks and authenticates the original studies. Use
recheck UNDER the final locks, without recursively calling any collector.
Neither function qualifies a final runtime, writes evidence or admits a paid
trial. A saved authentication record alone cannot replace the fresh audit.
"""
import json
import os
from pathlib import Path
import subprocess

import direct_final_evidence as original
import no_cutoff_evidence_freeze as freeze
import no_cutoff_final_candidate as candidate
from no_cutoff_custom_policy import fingerprint

CURRENT = Path('/opt/uts-capstone-custom-no-cutoff-20260928')
KIND = 'authenticated_original_and_no_cutoff_finalist_files_not_paid_admission'
FIELDS = frozenset({'kind', 'candidate_sha256', 'original_candidate_sha256',
    'revision_audit_sha256', 'original_files', 'revision_files', 'operator_files',
    'paid_launch_ready'})


def _merge(*bindings):
    values = {}
    for group in bindings:
        for name, digest in group.items():
            if name in values and values[name] != digest:
                raise ValueError('Overlapping evidence bindings disagree')
            values[name] = digest
    return values


def _revision_files(document):
    values = freeze._native_bindings(document['revision_qualification'], document['anchor_files'])
    results = {'.runtime/stage2/scored-trials/' + row['trial_id'] + '/result.json': row['result_sha256']
        for row in document['validation_summary']['rows']}
    return _merge(values, results)


def _expected(root, document):
    root = Path(root)
    if root.resolve() in {CURRENT.resolve(), *(path.resolve() for path in original.ROOTS.values())}:
        raise ValueError('Use a separate final deployment, not a completed study')
    candidate.validate_document(document)
    old, proof, block, public = freeze._anchors(root)
    if any(fingerprint(actual) != fingerprint(document[key]) for actual, key in (
            (old, 'original_candidate'), (proof, 'revision_qualification'), (block, 'revision_registration'))):
        raise ValueError('Measured finalist differs from its original qualification and registration')
    anchors = original.original._anchors(root)
    operator = _merge(original._operator_files(old), document['anchor_files'], {
        'stage2/' + name: digest for name, digest in document['freeze_logic_sources'].items()})
    record = dict(kind=KIND, candidate_sha256=fingerprint(document),
        original_candidate_sha256=fingerprint(old), revision_audit_sha256=document['revision_audit_sha256'],
        original_files=original._expected_originals(old, anchors),
        revision_files=_revision_files(document), operator_files=operator, paid_launch_ready=False)
    return record, public


def _require_no_stop(root):
    original._require_no_stop()
    for native in (Path(root), CURRENT):
        marker = native / '.runtime/stage2/operator-stop-request.json'
        if marker.exists() or marker.is_symlink():
            raise ValueError('Persistent operator stop forbids finalist progression')


def _check(root, record):
    _require_no_stop(root)
    original._check_files(root, record['operator_files'])
    original._check_originals(record['original_files'])
    original._check_files(CURRENT, record['revision_files'])
    _require_no_stop(root)


def _native_audit(bindings):
    # The generated stdlib preflight refuses an active service and checks all
    # qualified sources, inputs and twenty known result bytes before imports.
    # The unchanged collector freshly authenticates the original eighty too.
    program = freeze._revision_program(bindings)
    environment = dict(os.environ, PYTHONPATH=str(CURRENT / 'stage2'), PYTHONDONTWRITEBYTECODE='1')
    environment.pop('PYTHONHOME', None)
    try:
        result = subprocess.run([str(CURRENT / '.venv/bin/python'), '-B', '-c', program],
            cwd=CURRENT, env=environment, text=True, capture_output=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Completed revision native audit could not complete') from None
    if result.returncode:
        raise ValueError('Completed revision audit failed; inspect retained metadata without replay')
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ValueError('Completed revision audit did not return metadata') from None


def authenticate(root, document):
    """Fresh read-only native audit; no locks may already be held by the caller."""
    record, public = _expected(root, document)
    _check(root, record)  # Refuse mutated native code before executing it.
    data = _native_audit(record['revision_files'])
    freeze._validate_snapshot(data, public)
    rows = [dict(trial_id=r['trial_id'], task_id=r['task_id'], harness=r['harness'], reward=r['reward'],
        agent_seconds=r['agent_seconds'], requests=r['model_requests'], unknown_cost_requests=r['unknown_cost_requests'],
        known_charged_usd=r['known_cost_usd'], charged_usd=r['total_cost_usd'], result_sha256=r['result_sha256'])
        for r in data['rows']]
    fresh = candidate.build(document['original_candidate'], document['revision_qualification'],
        document['revision_registration'], rows,
        audit_sha256=fingerprint({k: v for k, v in data.items() if k != 'collected_utc'}),
        anchors=document['anchor_files'], logic=document['freeze_logic_sources'])
    if fingerprint(fresh) != fingerprint(document):
        raise ValueError('Fresh native revision evidence differs from the measured finalist')
    _check(root, record)
    return record


def recheck(root, document, authenticated):
    """File/stop recheck under ancestor locks, not fresh-audit authentication.

The future final qualification and dispatcher must bind the returned record
and invoke authenticate themselves. Self-supplied JSON is not proof of that
call and does not grant execution permission.
"""
    expected, _ = _expected(root, document)
    if (not isinstance(authenticated, dict) or set(authenticated) != FIELDS
            or fingerprint(authenticated) != fingerprint(expected)):
        raise ValueError('Exact native-authenticated revised-finalist record required')
    _check(root, expected)
    return candidate.validate_document(document)

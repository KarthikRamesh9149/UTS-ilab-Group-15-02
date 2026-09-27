"""Authenticate the operator freeze against completed original native studies.

Run this before taking the new final matrix locks: the original collector
takes its own ancestor locks. There are no model calls, trial dispatches or
writes here. After authentication, a caller holding those same ancestor locks
can recheck the returned file bindings without recursively acquiring locks.
This module does not qualify a final runtime or authorise paid execution.
"""
import json
import os
from pathlib import Path
import subprocess

import deadline_evidence_freeze as original
from deadline_candidate_freeze import freeze
from deadline_custom_parent import PREVIOUS
from portable_candidate_freeze import _digest, _hash, _regular
from portable_custom_policy import PYTHON_SHA256, fingerprint

CURRENT = Path('/opt/uts-capstone-custom-deadline-20260927-r2')
ROOTS = {'portable': PREVIOUS, 'deadline': CURRENT}
KIND = 'authenticated_original_finalist_files_not_paid_admission'
FIELDS = {'kind', 'candidate_sha256', 'original_audit_sha256', 'original_files',
          'operator_files', 'paid_launch_ready'}


def _operator_files(document):
    return dict(document['anchor_files'], **{
        'stage2/' + name: value for name, value in document['selection_logic_sources'].items()})


def _expected_originals(document, anchors):
    """Known hashes only: do not bless whatever happens to exist on the host."""
    candidate = document['candidate']; parent = candidate['parent_evidence']
    proof = anchors['qualification.json']
    if (candidate['c3_sources'] != proof['sources']
            or candidate['c3_dependencies'] != proof['dependencies']
            or candidate['c3_qualification_sha256'] != proof['qualification_sha256']
            or candidate['c3_registration_sha256'] != anchors['registration-c3.json']['registration_sha256']
            or fingerprint(parent) != fingerprint(anchors['parent.json']['evidence'])):
        raise ValueError('Freeze differs from the original curated and private qualification anchors')
    portable = {'stage2/' + name: value for name, value in parent['sources'].items()}
    portable.update({
        '.runtime/stage2/portable-qualification.json': parent['qualification_file_sha256'],
        '.runtime/stage2/python-runtime.tar.gz': PYTHON_SHA256,
    })
    portable.update({'.runtime/stage2/portable-development-blocks/' + condition + '.json': value['file_sha256']
        for condition, value in parent['registration_bindings'].items()})
    portable.update({'.runtime/stage2/scored-trials/' + name + '/result.json': value
        for name, value in parent['results_sha256'].items()})
    deadline = {'stage2/' + name: value for name, value in candidate['c3_sources'].items()}
    deadline.update({
        '.runtime/stage2/deadline-qualification.json': proof['qualification_file_sha256'],
        '.runtime/stage2/deadline-development-blocks/C3.json': anchors['registration-c3.json']['registration_file_sha256'],
        '.runtime/stage2/deadline-parent-evidence.json': anchors['parent.json']['file_sha256'],
        '.runtime/stage2/deadline-credit-policy.json': proof['private_copies_verified']['deadline-credit-policy.json'],
        '.runtime/stage2/python-runtime.tar.gz': PYTHON_SHA256,
    })
    deadline.update({'.runtime/stage2/scored-trials/' + row['trial_id'] + '/result.json': row['result_sha256']
        for row in candidate['c3_summary']['rows']})
    return {'portable': portable, 'deadline': deadline}


def _check_files(root, bindings):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Regular original deployment directory required')
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError('Original file bindings required')
    for name, expected in bindings.items():
        _hash(expected)
        # Reject symlinks in every relative path component as well.
        _regular(root, name)
        if _digest(root, name) != expected:
            raise ValueError('Bound original or operator evidence changed')


def _check_originals(files):
    if not isinstance(files, dict) or set(files) != set(ROOTS):
        raise ValueError('Both original native development deployments required')
    for generation, bindings in files.items():
        _check_files(ROOTS[generation], bindings)


def _require_no_stop():
    for native in ROOTS.values():
        marker = native / '.runtime/stage2/operator-stop-request.json'
        if marker.exists() or marker.is_symlink():
            raise ValueError('Persistent operator stop forbids final progression')


def _native_audit():
    # Preserve the qualified original collector and interpreter. Its code
    # checks all original results, services, deadlines, traces and cleanup.
    # Never substitute a caller-provided command, original root or interpreter.
    program = original._original_program()
    environment = dict(os.environ, PYTHONPATH=str(CURRENT / 'stage2'), PYTHONDONTWRITEBYTECODE='1')
    environment.pop('PYTHONHOME', None)
    try:
        result = subprocess.run([str(CURRENT / '.venv/bin/python'), '-B', '-c', program],
            cwd=CURRENT, env=environment, text=True, capture_output=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Original native audit could not complete') from None
    if result.returncode:
        raise ValueError('Original native audit did not complete; inspect retained study metadata')
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError):
        raise ValueError('Original audit did not return metadata') from None


def authenticate(root, document):
    """Fresh native audit, never inferred from a prior checks:true record."""
    root = Path(root)
    if root.resolve() in {path.resolve() for path in ROOTS.values()}:
        raise ValueError('Use a separate final deployment, not an original study')
    original.validate_document(document)
    anchors = original._anchors(root)
    files = _expected_originals(document, anchors)
    operator = _operator_files(document)
    _check_files(root, operator)
    _check_originals(files)  # Refuse changed original code before executing it.
    _require_no_stop()
    data = _native_audit()
    original._validate_originals(data, anchors)
    candidate = freeze(anchors['parent.json']['evidence'],
        original._c3_summary(data, anchors['parent.json']['evidence']),
        registration_sha256=fingerprint(data['registration']),
        qualification_sha256=data['qualification_sha256'], sources=data['sources'],
        dependencies=anchors['qualification.json']['dependencies'])
    audit_hash = fingerprint({key: value for key, value in data.items() if key != 'collected_utc'})
    if (fingerprint(candidate) != fingerprint(document['candidate'])
            or audit_hash != document['original_audit_sha256']):
        raise ValueError('Fresh native evidence differs from the operator freeze')
    _check_originals(files)
    _check_files(root, operator)
    _require_no_stop()
    return dict(kind=KIND, candidate_sha256=fingerprint(document),
        original_audit_sha256=audit_hash, original_files=files,
        operator_files=operator, paid_launch_ready=False)


def recheck(root, document, authenticated):
    """Recheck under ancestor locks; not a substitute for authenticate().

    The final native proof must bind this authentication record. This read
    alone cannot distinguish a caller-invented record from a real audit.
    """
    original.validate_document(document)
    anchors = original._anchors(root)
    expected = dict(kind=KIND, candidate_sha256=fingerprint(document),
        original_audit_sha256=document['original_audit_sha256'],
        original_files=_expected_originals(document, anchors),
        operator_files=_operator_files(document), paid_launch_ready=False)
    if not isinstance(authenticated, dict) or set(authenticated) != FIELDS or fingerprint(authenticated) != fingerprint(expected):
        raise ValueError('Exact native-authenticated original file record required')
    _check_files(root, expected['operator_files'])
    _check_originals(expected['original_files'])
    _require_no_stop()
    return original.validate_document(document)

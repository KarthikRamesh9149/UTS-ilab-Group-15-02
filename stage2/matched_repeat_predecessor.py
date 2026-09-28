"""Operator-side authentication of the custom-final predecessor and its backup.

This Mac-side reader runs the unchanged completed-final collector, then reads
the existing off-server archive. It neither creates a backup nor qualifies,
registers or launches a repeat. Use BEFORE future native ancestor locks: that
collector acquires them itself. A saved document cannot replace fresh native
host authentication or grant a dispatch permit.

Only the first, Terminus-2 successor is implemented here. OpenHands must also
authenticate a completed Terminus-2 repeat with its future qualified exporter;
there is deliberately no caller-supplied reader or checks-only fallback.
"""
from contextlib import ExitStack
import csv
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess

import export_no_cutoff_final as exporter
import matched_repeat_policy as policy
from retry_runtime import private_read
from run_credit_only import hold
from scored_gateway import durable_json, private_directory

PUBLIC = 'stage2/results/custom-no-cutoff-final-20260928'
PRIVATE = '.runtime/netcup/custom-no-cutoff-final-20260928/qualified'
COMPLETED = '.runtime/netcup/custom-no-cutoff-final89-c0-nc-20260928'
ORIGINAL = '.runtime/netcup/corrected-20260923/corrected-qualification.json'
ORIGINAL_FILE_SHA256 = '813b8762eae8caa6b32ccf2bee9c7fa5d0c272ff0e756b07e7251bcb2cd9e433'
FINAL_FILE_SHA256 = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
REGISTRATION_FILE_SHA256 = '01545d5d91cd45f7faa1f0a6a903b363774adf2c44a20add5624ec8bd55b809f'
FINAL_INPUTS = ('no-cutoff-final-candidate.json', 'no-cutoff-final-authentication.json',
    'no-cutoff-final-runtime.json', 'no-cutoff-final-manifest.json',
    'no-cutoff-final-credit-policy.json', 'no-cutoff-final-qualification.json')
FILE = 'matched-repeat-terminus-2-predecessor.json'
KIND = 'off_server_custom_final_predecessor_not_repeat_admission'
FIELDS = {'schema_version', 'kind', 'successor_harness', 'predecessors',
    'original_qualification_sha256', 'local_files', 'native_files', 'paid_launch_ready'}


def _regular(root, name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or str(path) != name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('Normalised relative evidence path required')
    current = Path(root)
    if current.is_symlink() or not current.is_dir():
        raise ValueError('Regular operator repository required')
    for part in path.parts:
        current /= part
        if current.is_symlink():
            raise ValueError('Symlinked evidence refused')
    if not current.is_file():
        raise ValueError('Required completed predecessor evidence is missing')
    info = current.stat()
    if name.startswith('.runtime/') and (info.st_uid != os.getuid() or info.st_mode & 0o077):
        raise ValueError('Private evidence must be owned and not group/world accessible')
    return current


def _digest(root, name):
    with _regular(root, name).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _json(root, name):
    path = _regular(root, name)
    value = private_read(path) if name.startswith('.runtime/') else json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Object evidence metadata required')
    return value


def _operator(repo):
    repo = Path(repo)
    if (platform.system() != 'Darwin' or repo.is_symlink()
            or repo.resolve() != exporter.REPO.resolve()
            or exporter.OUTPUT != repo / PUBLIC):
        raise ValueError('Use the Mac operator checkout for actual off-server backup verification')
    if Path(__file__).resolve() != repo.resolve() / 'stage2/matched_repeat_predecessor.py':
        raise ValueError('Use the operator checkout evidence reader')
    return repo


def _anchors(repo):
    """Read already pinned qualification bytes, without a completed audit."""
    repo = _operator(repo)
    proof_path = PRIVATE + '/.runtime/stage2/no-cutoff-final-qualification.json'
    block_path = PRIVATE + '/no-cutoff-final-matrix.json'
    for path, digest in ((ORIGINAL, ORIGINAL_FILE_SHA256), (proof_path, FINAL_FILE_SHA256),
            (block_path, REGISTRATION_FILE_SHA256)):
        if _digest(repo, path) != digest:
            raise ValueError('Exact original and final qualification/registration bytes required')
    original, proof, block = (_json(repo, path) for path in (ORIGINAL, proof_path, block_path))
    policy.anchors(original, proof)
    if policy.fingerprint(block) != policy.CUSTOM_FINAL_REGISTRATION_SHA256:
        raise ValueError('Actual custom final89 registration required')
    manifest_path = PRIVATE + '/.runtime/stage2/no-cutoff-final-manifest.json'
    manifest = _json(repo, manifest_path)
    policy.schedule(manifest)
    public = {name: _json(repo, PUBLIC + '/' + name) for name in
        ('qualification.json', 'registration-c0-nc.json', 'lineage.json', 'credit-policy.json')}
    projection = public['qualification.json']; registration = public['registration-c0-nc.json']
    if (projection.get('qualification_sha256') != policy.CUSTOM_FINAL_QUALIFICATION_SHA256
            or projection.get('qualification_file_sha256') != FINAL_FILE_SHA256
            or any(policy.fingerprint(projection.get(k)) != policy.fingerprint(v) for k, v in proof.items())
            or registration.get('registration_sha256') != policy.fingerprint(block)
            or registration.get('registration_file_sha256') != REGISTRATION_FILE_SHA256
            or any(policy.fingerprint(registration.get(k)) != policy.fingerprint(v)
                for k, v in block.items() if k != 'kind')):
        raise ValueError('Curated final projections differ from exact qualified bytes')
    native = {'stage2/' + name: digest for name, digest in proof['sources'].items()}
    native.update(proof['evidence_files'])
    native.update({'.runtime/stage2/no-cutoff-final-qualification.json': FINAL_FILE_SHA256,
        '.runtime/stage2/no-cutoff-final-matrix.json': REGISTRATION_FILE_SHA256,
        '.runtime/stage2/python-runtime.tar.gz': proof['python_runtime_sha256'],
        '.runtime/stage2/no-cutoff-final-candidate.json': public['lineage.json']['candidate_file_sha256']})
    native.update({'.runtime/stage2/' + name: projection['private_file_sha256'][name]
        for name in FINAL_INPUTS if name not in ('no-cutoff-final-candidate.json', 'no-cutoff-final-qualification.json')})
    copied = {'.runtime/stage2/' + name: PRIVATE + '/.runtime/stage2/' + name for name in FINAL_INPUTS}
    copied['.runtime/stage2/no-cutoff-final-matrix.json'] = block_path
    copied.update({name: PRIVATE + '/' + name for name in proof['evidence_files']})
    for name, path in copied.items():
        if _digest(repo, path) != native[name]:
            raise ValueError('Copied final runtime input or native producer bytes changed')
    source_names = set(proof['sources']) | policy.REQUIRED_SOURCE_FILES
    current = {name: _digest(repo, 'stage2/' + name) for name in sorted(source_names)}
    policy.source_transition(original, proof, current)
    # In particular, the imported audit/archive verifier must still be the
    # source qualified with final89, not a newly supplied capture callback.
    if Path(exporter.__file__).resolve() != repo.resolve() / 'stage2/export_no_cutoff_final.py':
        raise ValueError('Qualified final exporter imported from another checkout')
    local = {'stage2/' + name: digest for name, digest in current.items()}
    local.update({path: native[name] for name, path in copied.items()})
    for path in (ORIGINAL, *(PUBLIC + '/' + name for name in public)):
        local[path] = _digest(repo, path)
    return dict(proof=proof, block=block, manifest=manifest, native=native, local=local)


def _native_program(bindings):
    """Stdlib preflight before any project import or original collector lock."""
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError('Pinned final files required')
    for name, digest in bindings.items():
        path = PurePosixPath(name)
        if (path.is_absolute() or str(path) != name
                or any(part in ('', '.', '..') for part in name.split('/'))):
            raise ValueError('Normalised native evidence path required')
        policy._hash(digest)
    guard = '''
from pathlib import Path
import hashlib, subprocess
_predecessor_root = Path(ROOT)
_predecessor_bindings = BINDINGS
def _predecessor_check():
 if _predecessor_root.is_symlink() or not _predecessor_root.is_dir():
  raise ValueError('Regular completed final deployment required')
 marker = _predecessor_root / '.runtime/stage2/operator-stop-request.json'
 if marker.exists() or marker.is_symlink():
  raise ValueError('Persistent operator stop forbids successor progression')
 response = subprocess.check_output(['systemctl','show',
  'uts-stage2-custom-no-cutoff-final-20260928.service',
  '--property=ActiveState','--property=MainPID','--property=ExecMainStatus'],text=True,timeout=8)
 state = dict(line.split('=',1) for line in response.splitlines() if '=' in line)
 if state != {'ActiveState':'inactive','MainPID':'0','ExecMainStatus':'0'}:
  raise ValueError('Final must be inactive before any completed collector or ancestor lock')
 for name, expected in _predecessor_bindings.items():
  path = _predecessor_root
  for part in Path(name).parts:
   path /= part
   if path.is_symlink(): raise ValueError('Symlinked native evidence refused')
  if not path.is_file(): raise ValueError('Native evidence missing')
  with path.open('rb') as stream:
   if hashlib.file_digest(stream,'sha256').hexdigest() != expected:
    raise ValueError('Pinned native evidence changed before or during audit')
_predecessor_check()
'''.replace('Path(ROOT)', 'Path(' + repr(exporter.REMOTE) + ')').replace('= BINDINGS', '= ' + repr(bindings))
    return guard + exporter.program(exporter.COLLECT, 'C0-NC') + '\n_predecessor_check()\n'


def _read_native(bindings):
    try:
        response = subprocess.run(exporter.remote_command(), input=_native_program(bindings),
            capture_output=True, text=True, timeout=300)
    except (OSError, subprocess.TimeoutExpired):
        raise ValueError('Completed-final audit could not complete') from None
    if response.returncode:
        raise ValueError('Completed-final audit refused; inspect metadata without replay')
    try:
        return json.loads(response.stdout)
    except (TypeError, ValueError):
        raise ValueError('Completed-final audit did not return allowlisted metadata') from None


def _audit_hash(data):
    return policy.fingerprint({k: v for k, v in data.items() if k != 'collected_utc'})


def _check_export(repo, data, backup):
    summary_path = PUBLIC + '/c0-nc/summary.json'
    trials_path = PUBLIC + '/c0-nc/trials.csv'
    summary = _json(repo, summary_path)
    expected = {k: data[k] for k in ('condition', 'collected_utc', 'service', 'bindings', 'audit_checks', 'model_protocol')}
    expected.update(intended=89, private_backup=backup, results=exporter.aggregate(data['rows']),
        development_subset=exporter.aggregate(data['rows'][:20]),
        outside_development_subset=exporter.aggregate(data['rows'][20:]),
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run',
        baseline_comparison=dict(primary=dict(harness='terminus-2', passed=52, intended=89),
            secondary=dict(harness='openhands', passed=44, intended=89)))
    if any(policy.fingerprint(summary.get(k)) != policy.fingerprint(v) for k, v in expected.items()):
        raise ValueError('Completed final public summary differs from audited evidence')
    with _regular(repo, trials_path).open(newline='') as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(exporter.ROW_FIELDS):
            raise ValueError('Exact curated final row schema required')
        rows = list(reader)
    rendered = [{k: '' if v is None else str(v) for k, v in row.items()} for row in data['rows']]
    if rows != rendered:
        raise ValueError('All 89 curated results must match without per-task best-of')
    return {name: _digest(repo, name) for name in (summary_path, trials_path)}


def _check_local(repo, files):
    for name, digest in files.items():
        if _digest(repo, name) != digest:
            raise ValueError('Operator source, anchor, audit or backup changed during verification')


def capture(repo, harness='terminus-2'):
    """Fresh native audit plus actual existing off-server archive verification."""
    if harness != 'terminus-2':
        raise ValueError('OpenHands also needs its unimplemented completed-Terminus predecessor reader')
    repo = _operator(repo)
    anchors = _anchors(repo)
    paths = {key: COMPLETED + '/' + filename for key, filename in (
        ('audit', 'snapshot.json'), ('backup', 'backup.json'), ('archive', 'evidence.tar.gz'))}
    # Missing/incomplete backup is rejected before any remote audit; this never
    # recreates a completed archive or runs the exporter write operations.
    local = dict(anchors['local'])
    local.update({path: _digest(repo, path) for path in paths.values()})
    data = _json(repo, paths['audit']); backup = _json(repo, paths['backup'])
    exporter.validate_snapshot(data)
    if (policy.fingerprint(data['registration']) != policy.fingerprint(anchors['block'])
            or data['sources'] != anchors['proof']['sources']
            or any(data['bindings'].get(k) != v for k, v in anchors['native'].items() if not k.startswith('stage2/'))):
        raise ValueError('Saved final audit differs from pinned source/input evidence')
    native = dict(anchors['native'], **exporter.expected_archive_hashes(data))
    local.update(_check_export(repo, data, backup))
    fresh = _read_native(native)
    exporter.validate_snapshot(fresh)
    if _audit_hash(fresh) != _audit_hash(data):
        raise ValueError('Fresh completed-final audit differs from retained evidence')
    if not isinstance(backup, dict) or set(backup) != exporter.BACKUP_FIELDS:
        raise ValueError('Exact verified private backup record required')
    verified = exporter.verify_archive(_regular(repo, paths['archive']), data,
        {key: backup[key] for key in exporter.RECEIPT_FIELDS})
    if policy.fingerprint(verified) != policy.fingerprint(backup):
        raise ValueError('Backup record is not proof of the current off-server archive bytes')
    if verified['sha256'] != local[paths['archive']]:
        raise ValueError('Off-server archive changed during authentication')
    block = dict(experiment=policy.CUSTOM_FINAL_EXPERIMENT, harness='C0-NC',
        qualification_sha256=policy.CUSTOM_FINAL_QUALIFICATION_SHA256,
        registration_sha256=policy.CUSTOM_FINAL_REGISTRATION_SHA256,
        sources_sha256=policy.CUSTOM_FINAL_SOURCES_SHA256,
        results_sha256={row['trial_id']: row['result_sha256'] for row in data['rows']},
        audit_sha256=_audit_hash(data), archive_sha256=verified['sha256'],
        backup_record_sha256=local[paths['backup']])
    record = dict(kind='authenticated_matched_repeat_predecessors_not_paid_admission',
        successor_harness=harness, schedule_sha256=policy.fingerprint(policy.schedule(anchors['manifest'])),
        blocks=[block], paid_launch_ready=False)
    policy.validate_predecessors(record, anchors['manifest'], harness)
    _check_local(repo, local)
    if _anchors(repo) != anchors:
        raise ValueError('Final anchors changed during authentication')
    return dict(schema_version=1, kind=KIND, successor_harness=harness, predecessors=record,
        original_qualification_sha256=policy.ORIGINAL_QUALIFICATION_SHA256,
        local_files=local, native_files=native, paid_launch_ready=False)


def verify(document, repo):
    """Fresh native/actual-archive verification, not paid or under-lock admission."""
    if (not isinstance(document, dict) or set(document) != FIELDS
            or type(document['schema_version']) is not int or document['schema_version'] != 1
            or document['successor_harness'] != 'terminus-2'
            or document['kind'] != KIND or document['paid_launch_ready'] is not False):
        raise ValueError('Exact non-admitting operator predecessor document required')
    current = capture(repo, document['successor_harness'])
    if policy.fingerprint(document) != policy.fingerprint(current):
        raise ValueError('Predecessor document differs from fresh native and archive evidence')
    return current['predecessors']


def save(repo):
    """Exclusive private save; refuses replacement without another native audit."""
    repo = _operator(repo)
    folder = private_directory(repo / '.runtime/finalisation')
    path = folder / FILE
    with ExitStack() as stack:
        hold(stack, folder, 'matched-repeat-predecessor.lock')
        if path.exists() or path.is_symlink():
            raise ValueError('Preserve the existing predecessor document; use fresh verify')
        document = capture(repo)
        durable_json(path, document)
    return path, document

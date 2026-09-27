"""Operator-side fresh evidence capture for the completed C0-NC revision.

No trial, qualifier or model is launched. The unchanged native collector
authenticates the original eighty outcomes and acquires all ancestor locks.
Use before, not inside, a future final runner's same ancestor locks.
"""
from contextlib import ExitStack
from datetime import datetime
import json
from pathlib import Path
import subprocess

import export_no_cutoff_custom as exporter
import no_cutoff_custom_policy as revision
import no_cutoff_final_candidate as candidate
from deadline_evidence_freeze import _json
from portable_candidate_freeze import _digest, _regular
from progress_dashboard import REPO
from retry_runtime import private_read
from run_credit_only import hold
from scored_gateway import durable_json, private_directory

FREEZE_FILE = 'no-cutoff-finalist-freeze.json'
SNAPSHOT_FIELDS = frozenset({'condition', 'registration', 'qualification_sha256', 'sources',
    'bindings', 'service', 'model_protocol', 'policy', 'rows', 'collected_utc', 'audit_checks'})


def _anchors(repo):
    repo = Path(repo)
    if repo.is_symlink() or not repo.is_dir() or exporter.OUTPUT != repo / candidate.RESULTS:
        raise ValueError('Use the operator repository and its curated C0-NC evidence')
    public = {name: _json(repo, candidate.RESULTS + '/' + name) for name in candidate.PUBLIC_FILES}
    private = {name: private_read(_regular(repo, candidate.PRIVATE + '/.runtime/stage2/' + name))
               for name in candidate.PRIVATE_FILES}
    original = private_read(_regular(repo, candidate.ORIGINAL))
    if revision.fingerprint(original) != revision.fingerprint(private[revision.CANDIDATE_FILE]):
        raise ValueError('Copied original selection differs from the operator freeze')
    proof = revision.validate_qualification(original, private[revision.QUALIFICATION])
    block = private_read(_regular(repo, candidate.PRIVATE + '/C0-NC.json'))
    if (revision.fingerprint(proof) != candidate.QUALIFICATION_SHA256
            or revision.fingerprint(block) != candidate.REGISTRATION_SHA256
            or revision.fingerprint(block) != revision.fingerprint(revision.registration(
                original, proof, private[revision.RUNTIME_FILE]['development_ids']))):
        raise ValueError('Exact qualified revision and registration required')
    projected = public['qualification.json']
    registered = public['registration-c0-nc.json']
    registered_block = {k: v for k, v in registered.items()
        if k not in ('kind', 'registration_sha256', 'registration_file_sha256')}
    if (revision.fingerprint(registered_block) != revision.fingerprint(block)
            or registered['registration_sha256'] != revision.fingerprint(block)
            or registered['registration_file_sha256'] != _digest(repo, candidate.PRIVATE + '/C0-NC.json')
            or projected['qualification_sha256'] != revision.fingerprint(proof)
            or projected['qualification_file_sha256'] != _digest(repo,
                candidate.PRIVATE + '/.runtime/stage2/' + revision.QUALIFICATION)
            or any(revision.fingerprint(projected.get(k)) != revision.fingerprint(v) for k, v in proof.items())):
        raise ValueError('Curated projection must match complete original qualification bytes')
    if (revision.fingerprint(private[revision.POLICY_FILE]) != revision.fingerprint(revision.POLICY)
            or revision.fingerprint(public['credit-policy.json']) != revision.fingerprint(revision.POLICY)
            or revision.fingerprint(private[revision.AUTHENTICATION_FILE]) != proof['original_authentication_sha256']
            or revision.fingerprint(private[revision.RUNTIME_FILE]) != proof['runtime_identity_sha256']):
        raise ValueError('Original authentication, current runtime and uncapped policy must agree')
    lineage = public['lineage.json']
    if (lineage.get('original_candidate_sha256') != revision.fingerprint(original)
            or lineage.get('candidate_file_sha256') != _digest(repo,
                candidate.PRIVATE + '/.runtime/stage2/' + revision.CANDIDATE_FILE)
            or lineage.get('original_parent') != 'C0' or lineage.get('condition') != revision.CONDITION
            or lineage.get('original_score_inherited') is not False):
        raise ValueError('Original C0 cannot be relabelled or transfer its score')
    for name in (revision.POLICY_FILE, revision.RUNTIME_FILE, revision.AUTHENTICATION_FILE):
        if projected['private_file_sha256'].get(name) != _digest(repo, candidate.PRIVATE + '/.runtime/stage2/' + name):
            raise ValueError('Private input file bytes changed')
    for name, digest in proof['evidence_files'].items():
        if _digest(repo, candidate.PRIVATE + '/' + name) != digest:
            raise ValueError('Native producer evidence bytes changed')
    # The fixed collector and its structural readers must remain the qualified
    # versions. New final-run code is added separately, not substituted here.
    for name in candidate.LOGIC_FILES & proof['sources'].keys():
        if _digest(repo, 'stage2/' + name) != proof['sources'][name]:
            raise ValueError('Qualified native collector or inherited evidence reader changed')
    return original, proof, block, public


def _native_bindings(proof, anchors):
    """Use already pinned bytes, not whatever exists on the native host."""
    values = {'stage2/' + name: digest for name, digest in proof['sources'].items()}
    values.update({'.runtime/stage2/' + name:
        anchors[candidate.PRIVATE + '/.runtime/stage2/' + name] for name in candidate.PRIVATE_FILES})
    values.update(proof['evidence_files'])
    values['.runtime/stage2/no-cutoff-development-blocks/C0-NC.json'] = anchors[candidate.PRIVATE + '/C0-NC.json']
    values['.runtime/stage2/python-runtime.tar.gz'] = revision.PYTHON_SHA256
    return values


def _revision_program(bindings):
    if not isinstance(bindings, dict) or not bindings:
        raise ValueError('Pinned native source and evidence required before the audit')
    for name, digest in bindings.items():
        if (not isinstance(name, str) or not name or Path(name).is_absolute()
                or any(part in ('', '.', '..') for part in name.split('/'))):
            raise ValueError('Regular relative native binding required')
        revision._hash(digest)
    marker = str(Path(exporter.REMOTE) / '.runtime/stage2/operator-stop-request.json')
    guard = ('if _finalist_stop.exists() or _finalist_stop.is_symlink():\n'
             ' raise ValueError("Persistent operator stop forbids finalist progression")\n')
    before = ('from pathlib import Path\nimport subprocess\n_finalist_stop=Path(' + repr(marker) + ')\n'
        + guard + '_finalist_service=subprocess.check_output(["systemctl","show",'
        '"uts-stage2-custom-no-cutoff-c0-nc-20260928.service",'
        '"--property=ActiveState","--property=MainPID","--property=ExecMainStatus"],text=True,timeout=8)\n'
        '_finalist_state=dict(line.split("=",1) for line in _finalist_service.splitlines() if "=" in line)\n'
        'if _finalist_state != {"ActiveState":"inactive","MainPID":"0","ExecMainStatus":"0"}:\n'
        ' raise ValueError("Completed inactive revision required before taking its locks")\n')
    # Only stdlib executes before all native project sources are checked.
    check = ('import hashlib\n_finalist_root=Path(' + repr(exporter.REMOTE) + ')\n'
        '_finalist_bindings=' + repr(bindings) + '\n'
        'def _finalist_check_files():\n'
        ' if _finalist_root.is_symlink() or not _finalist_root.is_dir():\n'
        '  raise ValueError("Regular native deployment required")\n'
        ' for name, expected in _finalist_bindings.items():\n'
        '  path=_finalist_root\n'
        '  for part in Path(name).parts:\n'
        '   path=path/part\n'
        '   if path.is_symlink():\n'
        '    raise ValueError("Symlinked native evidence refused")\n'
        '  if not path.is_file():\n'
        '   raise ValueError("Bound native evidence missing")\n'
        '  with path.open("rb") as stream:\n'
        '   actual=hashlib.file_digest(stream,"sha256").hexdigest()\n'
        '  if actual != expected:\n'
        '   raise ValueError("Pinned native evidence changed")\n'
        '_finalist_check_files()\n')
    return (before + check + exporter.program(exporter.COLLECT, revision.CONDITION)
            + '\n_finalist_check_files()\n' + guard)


def _read_revision(bindings):
    try:
        result = subprocess.run(exporter.remote_command(), input=_revision_program(bindings),
            text=True, capture_output=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('Completed revision audit could not complete') from None
    if result.returncode:
        raise RuntimeError('Completed revision audit did not succeed; inspect metadata without replay')
    try:
        return json.loads(result.stdout)
    except (ValueError, TypeError) as error:
        raise RuntimeError('Native audit returned invalid metadata') from error


def _validate_snapshot(data, public):
    if not isinstance(data, dict) or set(data) != SNAPSHOT_FIELDS:
        raise ValueError('Only exact allowlisted revision audit metadata is accepted')
    exporter.validate_snapshot(data, public['registration-c0-nc.json'])
    observed = datetime.fromisoformat(data['collected_utc'].replace('Z', '+00:00'))
    if (observed.tzinfo is None or observed.utcoffset().total_seconds() != 0
            or data['service'] != dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0')):
        raise ValueError('Completed service and UTC audit timestamp required')


def capture(repo=REPO):
    """Fresh read-only native audit after validation, never while it is active."""
    repo = Path(repo)
    original, proof, block, public = _anchors(repo)
    names = candidate.BASE_ANCHORS | {candidate.PRIVATE + '/' + name for name in proof['evidence_files']}
    before = {name: _digest(repo, name) for name in names}
    logic = {name: _digest(repo, 'stage2/' + name) for name in candidate.LOGIC_FILES}
    data = _read_revision(_native_bindings(proof, before))
    _validate_snapshot(data, public)
    rows = [dict(trial_id=r['trial_id'], task_id=r['task_id'], harness=r['harness'], reward=r['reward'],
        agent_seconds=r['agent_seconds'], requests=r['model_requests'], unknown_cost_requests=r['unknown_cost_requests'],
        known_charged_usd=r['known_cost_usd'], charged_usd=r['total_cost_usd'], result_sha256=r['result_sha256'])
        for r in data['rows']]
    document = candidate.build(original, proof, block, rows,
        audit_sha256=revision.fingerprint({k: v for k, v in data.items() if k != 'collected_utc'}),
        anchors=before, logic=logic)
    if (any(_digest(repo, name) != digest for name, digest in before.items())
            or any(_digest(repo, 'stage2/' + name) != digest for name, digest in logic.items())):
        raise ValueError('Original anchors or finalist capture code changed during the audit')
    return document


def verify(document, repo=REPO):
    candidate.validate_document(document)
    if revision.fingerprint(capture(repo)) != revision.fingerprint(document):
        raise ValueError('Measured finalist evidence or capture code changed')
    return document['selected_execution']


def save(repo=REPO):
    """Exclusive private operator save, not a registration or paid permission."""
    repo = Path(repo)
    for path in (repo, repo / '.runtime', repo / '.runtime/finalisation'):
        if path.is_symlink():
            raise ValueError('Regular operator state directory required')
    runtime = private_directory(repo / '.runtime/finalisation')
    with ExitStack() as stack:
        hold(stack, runtime, 'no-cutoff-finalist-freeze.lock')
        document = capture(repo)
        path = runtime / FREEZE_FILE
        if path.exists() or path.is_symlink():
            current = private_read(path)
            if revision.fingerprint(current) != revision.fingerprint(document):
                raise ValueError('Existing revised-finalist evidence cannot be replaced')
            return current
        durable_json(path, document)
        return document

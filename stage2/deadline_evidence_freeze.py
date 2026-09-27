"""Bind the four-variant selection to a fresh audit of original evidence.

This is an operator-side reader, not code installed into a running study.
The frozen C3 collector takes all ancestor locks and rechecks the original
registrations, sources, results, official limits, services and cleanup. No
model call, task replay, backup recreation or paid admission occurs here.
"""
from contextlib import ExitStack
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import subprocess

import export_deadline_custom as exporter
from deadline_candidate_freeze import freeze, validate_document as validate_candidate
from deadline_custom_policy import POLICY, fingerprint, parent_selection
from portable_candidate_freeze import _digest, _hash, _regular, _source_map
from portable_custom_policy import CANDIDATE_VERSION as PORTABLE_VERSION
from progress_dashboard import REPO
from retry_runtime import private_read
from run_credit_only import hold
from scored_gateway import durable_json, private_directory

RESULTS = 'stage2/results/custom-deadline-20260927'
ANCHOR_FILES = ('qualification.json', 'registration-c3.json', 'parent.json', 'credit-policy.json')
PRIVATE_QUALIFICATION = '.runtime/netcup/custom-deadline-20260927/qualified-r2/deadline-qualification.json'
ANCHOR_PATHS = tuple(RESULTS + '/' + name for name in ANCHOR_FILES) + (PRIVATE_QUALIFICATION,)
LOGIC_FILES = (
    'deadline_evidence_freeze.py', 'test_deadline_evidence_freeze.py',
    'deadline_candidate_freeze.py', 'test_deadline_candidate_freeze.py',
    'deadline_final_selection.py', 'test_deadline_final_selection.py',
    'deadline_evaluation_schedule.py', 'deadline_custom_policy.py',
    'portable_final_selection.py', 'portable_candidate_freeze.py',
    'export_deadline_custom.py', 'test_export_deadline_custom.py',
    'portable_custom_policy.py', 'retry_policy.py', 'model_protocol.py',
    'gateway_policy.py', 'progress_dashboard.py', 'retry_runtime.py',
    'run_credit_only.py', 'scored_gateway.py',
)
SNAPSHOT_FIELDS = {'condition', 'registration', 'qualification_sha256', 'sources',
    'bindings', 'service', 'model_protocol', 'policy', 'rows', 'collected_utc', 'audit_checks'}
FIXED = dict(schema_version=1, kind='original_evidence_bound_four_variant_candidate',
    paid_launch_ready=False, full_benchmark_win_claimed=False)
VARIABLE_FIELDS = {'candidate', 'anchor_files', 'selection_logic_sources',
    'original_audit_sha256', 'selected_execution'}
FREEZE_FILE = 'four-variant-candidate-freeze.json'


def _json(root, relative):
    raw = _regular(root, relative).read_bytes()
    if len(raw) > 4 * 1024 * 1024:
        raise ValueError('Candidate metadata exceeds the read window')

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate metadata field')
            result[key] = value
        return result

    def nonfinite(value):
        raise ValueError('Nonfinite metadata number')

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise ValueError('Metadata object required')
    return value


def _anchors(repo):
    repo = Path(repo)
    if repo.is_symlink() or not repo.is_dir() or exporter.OUTPUT != repo / RESULTS:
        raise ValueError('Use the operator repository and its curated evidence')
    values = {name: _json(repo, RESULTS + '/' + name) for name in ANCHOR_FILES}
    proof, registration, parent, policy = (values[name] for name in ANCHOR_FILES)
    parent_selection(parent['evidence'])
    block = {key: value for key, value in registration.items()
             if key not in ('kind', 'registration_sha256', 'registration_file_sha256')}
    if (fingerprint(block) != registration['registration_sha256']
            or fingerprint(parent['evidence']) != block['parent_evidence_sha256']
            or fingerprint(policy) != fingerprint(POLICY)
            or fingerprint(policy) != block['policy_sha256']
            or proof['qualification_sha256'] != block['qualification_sha256']
            or proof['sources_sha256'] != block['sources_sha256']
            or fingerprint(proof['sources']) != proof['sources_sha256']):
        raise ValueError('Original C3 anchors disagree')
    _source_map(proof['sources'])
    _hash(proof['qualification_file_sha256'])
    _hash(registration['registration_file_sha256'])
    _hash(parent['file_sha256'])
    _hash(proof['private_copies_verified']['deadline-credit-policy.json'])
    original = private_read(_regular(repo, PRIVATE_QUALIFICATION))
    if (_digest(repo, PRIVATE_QUALIFICATION) != proof['qualification_file_sha256']
            or fingerprint(original) != proof['qualification_sha256']
            or any(fingerprint(original.get(key)) != fingerprint(proof.get(key))
                   for key in ('sources', 'sources_sha256', 'dependencies'))):
        raise ValueError('Projected source and dependencies must match the complete original qualification')
    # Reuse the exact collector that was qualified with C3, not an edited
    # script that can reinterpret its old results or skip checks.
    if _digest(repo, 'stage2/export_deadline_custom.py') != proof['sources']['export_deadline_custom.py']:
        raise ValueError('Qualified original-evidence collector changed')
    return values


def _original_program():
    marker = str(Path(exporter.REMOTE) / '.runtime/stage2/operator-stop-request.json')
    guard = ('if _candidate_stop.exists() or _candidate_stop.is_symlink():\n'
             ' raise ValueError("Persistent operator stop forbids candidate progression")\n')
    return ('from pathlib import Path\n_candidate_stop=Path(' + repr(marker) + ')\n'
            + guard + exporter.program(exporter.COLLECT, 'C3') + '\n' + guard)


def _read_originals():
    result = subprocess.run(exporter.remote_command(),
        input=_original_program(), text=True,
        capture_output=True, timeout=120)
    if result.returncode:
        # Do not publish arbitrary remote diagnostics or retry a study.
        raise RuntimeError('Original-evidence audit did not complete; inspect study metadata')
    return json.loads(result.stdout)


def _validate_originals(data, anchors):
    if not isinstance(data, dict) or set(data) != SNAPSHOT_FIELDS:
        raise ValueError('Only allowlisted original-audit metadata is accepted')
    exporter.validate_snapshot(data)
    observed = datetime.fromisoformat(data['collected_utc'].replace('Z', '+00:00'))
    if observed.tzinfo is None or observed.utcoffset().total_seconds() != 0:
        raise ValueError('UTC audit timestamp required')
    proof = anchors['qualification.json']
    parent = anchors['parent.json']
    expected = {
        '.runtime/stage2/deadline-development-blocks/C3.json': anchors['registration-c3.json']['registration_file_sha256'],
        '.runtime/stage2/deadline-qualification.json': proof['qualification_file_sha256'],
        '.runtime/stage2/deadline-parent-evidence.json': parent['file_sha256'],
        '.runtime/stage2/deadline-credit-policy.json': proof['private_copies_verified']['deadline-credit-policy.json'],
        '.runtime/stage2/python-runtime.tar.gz': data['registration']['python_runtime_sha256'],
    }
    if (data['bindings'] != expected or set(data['audit_checks']) != set(exporter.CHECKS)
            or data['service'] != dict(ActiveState='inactive', SubState='dead', MainPID='0', ExecMainStatus='0')):
        raise ValueError('Original files, complete audit and inactive service must agree')


def _c3_summary(data, parent):
    rows = [dict(trial_id=row['trial_id'], task_id=row['task_id'], harness=row['harness'],
        reward=row['reward'], agent_seconds=row['agent_seconds'], result_sha256=row['result_sha256'],
        requests=row['model_requests'], unknown_cost_requests=row['unknown_cost_requests'],
        known_charged_usd=row['known_cost_usd'], charged_usd=row['total_cost_usd']) for row in data['rows']]
    known = str(sum((Decimal(row['known_charged_usd']) for row in rows), Decimal(0)))
    selected = parent_selection(parent)
    return dict(condition='C3', parent=selected['selected'], base_parent=selected['custom_parent'],
        intended=20, attempted=len(rows), passes=sum(row['reward'] == 1 for row in rows),
        failures=sum(row['reward'] == 0 for row in rows),
        no_verifier_result=sum(row['reward'] is None for row in rows), started_without_result=[],
        known_charged_usd=known, charged_usd=None if any(row['charged_usd'] is None for row in rows) else known,
        unknown_cost_requests=sum(row['unknown_cost_requests'] for row in rows),
        agent_seconds=sum(row['agent_seconds'] for row in rows),
        complexity=selected['summaries'][selected['selected']]['complexity'] + 1,
        rows=rows, efficiency_win_claimed=False, full_benchmark_win_claimed=False)


def _execution(candidate):
    selected = candidate['selection']
    newer = selected['selected'] == 'C3'
    parent = candidate['parent_evidence']
    sources = candidate['c3_sources'] if newer else parent['sources']
    return dict(harness=selected['selected'], parent=selected['parent'], base_parent=selected['base_parent'],
        candidate_version=POLICY['candidate_version'] if newer else PORTABLE_VERSION,
        original_generation='deadline' if newer else 'portable', sources=sources,
        sources_sha256=fingerprint(sources),
        dependencies=candidate['c3_dependencies'] if newer else parent['dependencies'],
        qualification_sha256=candidate['c3_qualification_sha256'] if newer else parent['qualification_sha256'],
        python_runtime_sha256=candidate['python_runtime_sha256'],
        execution_contract=candidate['execution_contract'] if newer else None)


def validate_document(document):
    """Structural validation alone is not evidence authentication or admission."""
    if not isinstance(document, dict) or set(document) != set(FIXED) | VARIABLE_FIELDS:
        raise ValueError('Exact evidence-bound candidate schema required')
    if fingerprint({key: document[key] for key in FIXED}) != fingerprint(FIXED):
        raise ValueError('Candidate metadata cannot grant paid admission')
    selected = validate_candidate(document['candidate'])
    if fingerprint(document['selected_execution']) != fingerprint(_execution(document['candidate'])):
        raise ValueError('Selected execution must retain its original whole-variant source')
    for field, expected in (
        ('anchor_files', set(ANCHOR_PATHS)),
        ('selection_logic_sources', set(LOGIC_FILES)),
    ):
        if not isinstance(document[field], dict) or set(document[field]) != expected:
            raise ValueError('All original anchors and selection code must be bound')
        for value in document[field].values():
            _hash(value)
        if field == 'selection_logic_sources':
            _source_map(document[field])
    _hash(document['original_audit_sha256'])
    return selected


def capture(repo=REPO):
    """Read original completed evidence under its native no-overlap locks."""
    repo = Path(repo)
    anchors = _anchors(repo)
    before = {name: _digest(repo, name) for name in ANCHOR_PATHS}
    logic = {name: _digest(repo, 'stage2/' + name) for name in LOGIC_FILES}
    data = _read_originals()
    _validate_originals(data, anchors)
    parent = anchors['parent.json']['evidence']
    proof = anchors['qualification.json']
    candidate = freeze(parent, _c3_summary(data, parent),
        registration_sha256=fingerprint(data['registration']),
        qualification_sha256=data['qualification_sha256'], sources=data['sources'],
        dependencies=proof['dependencies'])
    document = dict(FIXED, candidate=candidate, anchor_files=before, selection_logic_sources=logic,
        original_audit_sha256=fingerprint({key: value for key, value in data.items() if key != 'collected_utc'}),
        selected_execution=_execution(candidate))
    validate_document(document)
    if (any(_digest(repo, name) != digest for name, digest in before.items())
            or any(_digest(repo, 'stage2/' + name) != digest for name, digest in logic.items())):
        raise ValueError('Operator anchors or selection code changed during capture')
    return json.loads(json.dumps(document, allow_nan=False))


def verify(document, repo=REPO):
    validate_document(document)
    if fingerprint(capture(repo)) != fingerprint(document):
        raise ValueError('Original candidate evidence or selection code changed')
    return document['candidate']['selection']


def save(repo=REPO):
    """Exclusive private operator-side save. Never modifies a study deployment."""
    repo = Path(repo)
    for path in (repo, repo / '.runtime', repo / '.runtime/finalisation'):
        if path.is_symlink():
            raise ValueError('Regular operator state directory required')
    runtime = private_directory(repo / '.runtime/finalisation')
    with ExitStack() as stack:
        hold(stack, runtime, 'candidate-freeze.lock')
        document = capture(repo)
        path = runtime / FREEZE_FILE
        if path.exists() or path.is_symlink():
            current = private_read(path)
            if fingerprint(current) != fingerprint(document):
                raise ValueError('An existing candidate freeze cannot be replaced')
            return current
        durable_json(path, document)
        return document

"""Bind a development-selected 0.3 candidate without admitting paid execution.

Capture runs only after all three registered blocks finish, under the existing
study locks. A later deployment still needs its own source-bound qualification,
registration and unchanged-candidate checks before confirmation or final trials.
No trajectories, task instructions, provider requests or responses are read.
"""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

from corrected_custom_scope import MATCHED_CSV_SHA256
from credit_only_experiment import cleanup_complete
from portable_custom_policy import (
    BLOCKS, CANDIDATE_VERSION, DEVELOPMENT_SHA256, EXPERIMENT, INPUT_SHA256,
    POLICY, POLICY_FILE, PYTHON_SHA256, QUALIFICATION, SETTINGS, fingerprint,
    require_block,
)
from portable_custom_study import audited, qualified, selected_parent, summary
from portable_final_selection import checked, select
from retry_runtime import private_read
from run_portable_custom import lock_all
from scored_gateway import durable_json
from scored_trial import docker

KIND = 'frozen_portable_candidate_not_execution_admission'
FREEZE_FILE = 'portable-candidate-freeze.json'
LOGIC_FILES = (
    'portable_final_selection.py', 'portable_candidate_freeze.py',
    'portable_evaluation_schedule.py', 'test_portable_final_selection.py',
    'test_portable_candidate_freeze.py', 'test_portable_evaluation_schedule.py',
)
SUMMARY_FIELDS = frozenset((
    'condition', 'parent', 'intended', 'attempted', 'passes', 'failures',
    'no_verifier_result', 'started_without_result', 'charged_usd',
    'known_charged_usd', 'unknown_cost_requests', 'agent_seconds', 'complexity', 'rows',
))
ROW_FIELDS = frozenset((
    'trial_id', 'task_id', 'harness', 'reward', 'agent_seconds', 'result_sha256',
    'charged_usd', 'known_charged_usd', 'unknown_cost_requests', 'requests',
))
FIXED = dict(
    schema_version=1, kind=KIND, experiment=EXPERIMENT,
    candidate_version=CANDIDATE_VERSION, policy_sha256=fingerprint(POLICY),
    model_protocol=SETTINGS.document(), model_protocol_sha256=SETTINGS.fingerprint(),
    input_manifest_sha256=INPUT_SHA256, development_ids_sha256=DEVELOPMENT_SHA256,
    matched_baseline_csv_sha256=MATCHED_CSV_SHA256, python_runtime_sha256=PYTHON_SHA256,
    paid_launch_ready=False, full_benchmark_win_claimed=False,
)
VARIABLE_FIELDS = frozenset((
    'selection_inputs', 'selection', 'development_sources', 'sources_sha256',
    'development_dependencies', 'qualification_sha256', 'qualification_file_sha256',
    'registration_bindings', 'result_bindings', 'selection_logic_sources',
))


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('SHA256 evidence binding required')
    return value


def _source_map(value):
    if not isinstance(value, dict) or not value:
        raise ValueError('Nonempty source bindings required')
    for name, digest in value.items():
        path = PurePosixPath(name) if isinstance(name, str) else None
        if (path is None or not path.parts or path.is_absolute() or '..' in path.parts
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', name)
                or str(path) != name or '\\' in name):
            raise ValueError('Relative source identity required')
        _hash(digest)


def _regular(root, relative):
    relative = PurePosixPath(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Evidence path must stay within its deployment')
    path = Path(root)
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symlinked source or evidence is not allowed')
    if not path.is_file():
        raise ValueError('Required source or evidence file is missing')
    return path


def _digest(root, relative):
    with _regular(root, relative).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def _check_root(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Regular deployment root required')
    for path in (root / '.runtime', root / '.runtime/stage2'):
        if path.is_symlink() or not path.is_dir():
            raise ValueError('Regular private runtime directory required')


def _selection_inputs(summaries):
    if not isinstance(summaries, dict) or set(summaries) != {'C0', 'C1', 'C2'}:
        raise ValueError('All three development summaries required')
    result = {}
    for condition, value in summaries.items():
        checked(value, condition)
        # Explicit allowlist: no private observations or arbitrary metadata.
        row = {key: value[key] for key in SUMMARY_FIELDS}
        row['rows'] = [{key: item[key] for key in ROW_FIELDS} for item in value['rows']]
        result[condition] = row
    return json.loads(json.dumps(result, allow_nan=False))


def validate_document(document):
    """Check internal consistency, not the authenticity of an external file.

    A registration must bind the document hash and recheck original files with
    verify(). This pure validation never grants permission to make paid calls.
    """
    if not isinstance(document, dict) or set(document) != set(FIXED) | VARIABLE_FIELDS:
        raise ValueError('Exact candidate document schema required')
    if fingerprint({key: document[key] for key in FIXED}) != fingerprint(FIXED):
        raise ValueError('Candidate model, scope or authority changed')
    inputs = _selection_inputs(document['selection_inputs'])
    if fingerprint(inputs) != fingerprint(document['selection_inputs']):
        raise ValueError('Unexpected candidate input fields')
    selection = select(inputs)
    if fingerprint(document['selection']) != fingerprint(selection):
        raise ValueError('Candidate selection differs from its retained evidence')
    _source_map(document['development_sources'])
    if document['sources_sha256'] != fingerprint(document['development_sources']):
        raise ValueError('Development source-set hash mismatch')
    _source_map(document['selection_logic_sources'])
    if set(document['selection_logic_sources']) != set(LOGIC_FILES):
        raise ValueError('Selection implementation and tests must be bound')
    for field in ('qualification_sha256', 'qualification_file_sha256'):
        _hash(document[field])
    dependencies = document['development_dependencies']
    if (not isinstance(dependencies, dict) or set(dependencies) != {'python', 'packages'}
            or not isinstance(dependencies['python'], str)
            or not re.fullmatch(r'\d+\.\d+\.\d+', dependencies['python'])
            or not isinstance(dependencies['packages'], dict)
            or not dependencies['packages']
            or any(not isinstance(name, str) or not re.fullmatch(r'[a-z0-9-]+', name)
                   or not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9.+_-]+', version)
                   for name, version in dependencies['packages'].items())):
        raise ValueError('Exact installed dependency versions required')
    registrations = document['registration_bindings']
    if not isinstance(registrations, dict) or set(registrations) != {'C0', 'C1', 'C2'}:
        raise ValueError('All original development registrations required')
    for binding in registrations.values():
        if not isinstance(binding, dict) or set(binding) != {'canonical_sha256', 'file_sha256'}:
            raise ValueError('Registration byte and canonical bindings required')
        for value in binding.values():
            _hash(value)
    expected = {row['trial_id']: row['result_sha256']
                for block in inputs.values() for row in block['rows']}
    if len(expected) != 60 or document['result_bindings'] != expected:
        raise ValueError('Every retained development result must be bound')
    return selection


def _collect(root):
    runtime = Path(root) / '.runtime/stage2'
    _check_root(root)
    if (runtime / 'operator-stop-request.json').exists() or (runtime / 'operator-stop-request.json').is_symlink():
        raise ValueError('Persistent operator stop must be resolved explicitly')
    if docker('ps', '-aq', '--filter', 'name=uts-scored-'):
        raise ValueError('Finish and clean the active study before freezing')
    proof = qualified(root)
    completed, partial = audited(root)
    if partial or len(completed) != 60:
        raise ValueError('All 60 registered development attempts must be retained')
    blocks = {condition: require_block(runtime, condition) for condition in ('C0', 'C1', 'C2')}
    inputs = _selection_inputs({condition: summary(root, condition) for condition in blocks})
    selection = select(inputs)
    if fingerprint(blocks['C2'].get('parent_selection')) != fingerprint(selected_parent(root)):
        raise ValueError('C2 parent no longer matches its original registration')
    registrations, bindings = {}, {}
    for condition, block in blocks.items():
        if (block['qualification_sha256'] != fingerprint(proof)
                or block['sources_sha256'] != proof['sources_sha256']
                or block['parent'] != inputs[condition]['parent']
                or condition != 'C2' and block.get('parent_selection') is not None):
            raise ValueError('Development qualification or condition binding changed')
        registration_relative = f'.runtime/stage2/{BLOCKS}/{condition}.json'
        if fingerprint(private_read(_regular(root, registration_relative))) != fingerprint(block):
            raise ValueError('Registration changed while assembling candidate evidence')
        registrations[condition] = dict(canonical_sha256=fingerprint(block),
            file_sha256=_digest(root, registration_relative))
        for row in inputs[condition]['rows']:
            name = row['trial_id']
            original = completed.get(name)
            if not original or not cleanup_complete(original) or original.get('model_revoked') is not True:
                raise ValueError('Every outcome needs completed revocation and cleanup')
            identity = {key: original.get(key) for key in ('trial_id', 'task_id', 'harness')}
            reward = ((original.get('verifier_result') or {}).get('rewards') or {}).get('reward')
            if (identity != {key: row[key] for key in identity}
                    or original.get('stage') != 'development'
                    or fingerprint(reward) != fingerprint(row['reward'])
                    or fingerprint(original.get('phase_seconds', {}).get('agent')) != fingerprint(row['agent_seconds'])):
                raise ValueError('Selection metadata differs from its retained result')
            result_relative = f'.runtime/stage2/scored-trials/{name}/result.json'
            if fingerprint(private_read(_regular(root, result_relative))) != fingerprint(original):
                raise ValueError('Result changed while assembling candidate evidence')
            digest = _digest(root, result_relative)
            if digest != row['result_sha256']:
                raise ValueError('Result changed while assembling candidate evidence')
            bindings[name] = digest
    if set(completed) != set(bindings):
        raise ValueError('Unexpected development results must not enter selection')
    qualification_path = _regular(root, f'.runtime/stage2/{QUALIFICATION}')
    if fingerprint(private_read(qualification_path)) != fingerprint(proof):
        raise ValueError('Qualification changed while assembling candidate evidence')
    if fingerprint(private_read(_regular(root, f'.runtime/stage2/{POLICY_FILE}'))) != fingerprint(POLICY):
        raise ValueError('Explicit uncapped policy changed')
    if any(_digest(root, 'stage2/' + name) != digest for name, digest in proof['sources'].items()):
        raise ValueError('Development source changed while assembling candidate evidence')
    document = dict(FIXED, selection_inputs=inputs, selection=selection,
        development_sources=proof['sources'], sources_sha256=proof['sources_sha256'],
        development_dependencies=proof['dependencies'], qualification_sha256=fingerprint(proof),
        qualification_file_sha256=_digest(root, f'.runtime/stage2/{QUALIFICATION}'),
        registration_bindings=registrations, result_bindings=bindings,
        selection_logic_sources={name: _digest(root, 'stage2/' + name) for name in LOGIC_FILES})
    validate_document(document)
    # Do not expose mutable aliases to policy constants or loaded proof inputs.
    return json.loads(json.dumps(document, allow_nan=False))


def capture(root):
    """Read and bind complete evidence under the existing no-overlap locks."""
    _check_root(root)
    with ExitStack() as stack:
        lock_all(stack, root)
        return _collect(root)


def verify(root, document):
    validate_document(document)
    rebuilt = capture(root)
    if fingerprint(document) != fingerprint(rebuilt):
        raise ValueError('Frozen candidate source, dependencies or evidence changed')
    return document['selection']


def save(root):
    """Idempotent exclusive save, not a freeze overwrite or paid-run launcher."""
    _check_root(root)
    with ExitStack() as stack:
        lock_all(stack, root)
        document = _collect(root)
        path = Path(root) / '.runtime/stage2' / FREEZE_FILE
        if path.exists() or path.is_symlink():
            current = private_read(path)
            if fingerprint(current) != fingerprint(document):
                raise ValueError('An existing candidate freeze cannot be replaced')
            return current
        durable_json(path, document)
        return document

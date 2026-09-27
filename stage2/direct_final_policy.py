"""Exact final89 gateway contract; host qualification and dispatch stay separate.

The host must authenticate the original candidate and the current native
qualification before saving these files. Reading self-consistent JSON alone
does not prove a deployment was qualified. No registration or task is created
by this module, and the old scored runner does not admit this experiment.
"""
import hashlib
from pathlib import Path
import re

from deadline_custom_contract import CANDIDATE_VERSION, execution_contract
from deadline_custom_policy import POLICY as DEVELOPMENT_POLICY, source_bindings, dependency_bindings
from portable_custom_policy import SETTINGS, INPUT_SHA256, PYTHON_SHA256, fingerprint
from direct_final_candidate import MANIFEST_SHA256, validate_document
from retry_runtime import private_read

EXPERIMENT = 'custom-direct-final-20260928'
POLICY_FILE = 'direct-final-credit-policy.json'
CANDIDATE_FILE = 'direct-final-candidate.json'
MANIFEST_FILE = 'direct-final-manifest.json'
QUALIFICATION_FILE = 'direct-final-qualification.json'
REGISTRATION_FILE = 'direct-final-matrix.json'
POLICY = dict(DEVELOPMENT_POLICY, experiment=EXPERIMENT,
    predecessor=DEVELOPMENT_POLICY['experiment'], authorised_date='2026-09-28',
    authority='explicit-user-best-whole-candidate-direct-final89-no-artificial-cutoffs',
    stage='final', intended_tasks=89, confirmation='deferred-not-completed',
    diagnostic='deferred-not-completed')
QUALIFICATION_CHECKS = frozenset({
    'original_candidate_authenticated', 'candidate_behaviour_sources_unchanged',
    'exact_final89_images_and_limits', 'gateway_image_sources_match',
    'native_tools_and_uncapped_execution', 'native_final_gateway_admission',
    'native_shared_retry_and_unknown_costs', 'native_cancellation_and_cleanup',
    'native_cooperative_stop_and_no_replay', 'native_tracing_and_revocation',
    'synthetic_provider_network_isolated',
})
# This trusted orchestration file needs the new explicit final-study branch.
# No agent, prompt, tool, model, retry or lifecycle behaviour file is exempt.
ORCHESTRATION_FILES = frozenset({'scored_trial.py'})
REQUIRED_SOURCE_FILES = frozenset({
    'direct_final_candidate.py', 'direct_final_policy.py', 'direct_final_gateway.py',
    'test_direct_final_policy.py',
})


def candidate_execution(document):
    selected = validate_document(document)
    execution = document['selected_execution']
    expected = dict(harness='C3', candidate_version=CANDIDATE_VERSION,
        original_generation='deadline', execution_contract=execution_contract())
    if (selected['selected'] != 'C3'
            or any(fingerprint(execution.get(k)) != fingerprint(v) for k, v in expected.items())):
        raise ValueError('An older winner needs a separately validated no-cutoff revision, not relabelling')
    return execution


def cells(document, manifest):
    execution = candidate_execution(document)
    # INPUT_SHA256 identifies the original file bytes. Private copies may use
    # different whitespace; validate their canonical content with the pinned
    # schedule hash, retaining both identities in the final registration.
    if fingerprint(manifest) != MANIFEST_SHA256:
        raise ValueError('Original full benchmark manifest required')
    development = manifest['development_ids']
    outside = sorted(manifest['outside_development_ids'], key=lambda task: (
        hashlib.sha256(('uts-stage2-dev20-v1:42:' + task).encode()).hexdigest(), task))
    tasks = development + outside
    if len(tasks) != 89 or len(set(tasks)) != 89 or set(tasks) != set(manifest['all_task_ids']):
        raise ValueError('Exactly 89 unique frozen tasks required')
    return [dict(trial_id=f'customfinal1-c3-{index:02d}-{task}', task_id=task,
        stage='final', harness='C3', parent=execution['parent'], base_parent=execution['base_parent'])
        for index, task in enumerate(tasks, 1)]


def source_transition(document, current):
    """Bind an explicit orchestration delta; never silently change the agent."""
    original = candidate_execution(document)['sources']
    selection = document['selection_logic_sources']
    source_bindings(current)
    required = set(original) | set(selection) | REQUIRED_SOURCE_FILES
    if not required.issubset(current):
        raise ValueError('Original, selection and new final admission source required')
    if any(current[name] != digest for name, digest in selection.items()):
        raise ValueError('Frozen selection or authentication implementation changed')
    changed = {name for name in original if current[name] != original[name]}
    if not changed.issubset(ORCHESTRATION_FILES):
        raise ValueError('Measured candidate behaviour or original evidence code changed')
    return {name: dict(original_sha256=original[name], qualified_sha256=current[name])
            for name in sorted(changed)}


def validate_qualification(proof, document, manifest):
    """Validate bound metadata, not the host's current files or native runtime."""
    if not isinstance(proof, dict):
        raise ValueError('Separate native final qualification required')
    execution = candidate_execution(document)
    expected = dict(kind='native_direct_final_qualification', experiment=EXPERIMENT,
        status='passed', live_api_calls=0, candidate_version=CANDIDATE_VERSION,
        candidate_sha256=fingerprint(document), policy_sha256=fingerprint(POLICY),
        model_protocol_sha256=SETTINGS.fingerprint(), input_manifest_sha256=INPUT_SHA256,
        manifest_canonical_sha256=MANIFEST_SHA256,
        python_runtime_sha256=PYTHON_SHA256, execution_contract=execution_contract(),
        dependencies=execution['dependencies'], setup_timeout_seconds=900)
    if any(fingerprint(proof.get(k)) != fingerprint(v) for k, v in expected.items()):
        raise ValueError('Final qualification does not match the selected candidate and policy')
    cells(document, manifest)
    dependency_bindings(proof['dependencies'])
    transition = source_transition(document, proof.get('sources'))
    if (proof.get('sources_sha256') != fingerprint(proof['sources'])
            or fingerprint(proof.get('orchestration_changes')) != fingerprint(transition)):
        raise ValueError('Qualified source transition changed')
    checks = proof.get('checks')
    if (not isinstance(checks, dict) or set(checks) != QUALIFICATION_CHECKS
            or any(value is not True for value in checks.values())):
        raise ValueError('Full final native qualification evidence required')
    offline = proof.get('offline')
    if (not isinstance(offline, dict) or offline.get('passed') is not True
            or type(offline.get('tests')) is not int or offline['tests'] < 1
            or any(type(offline.get(k)) is not int or offline[k] != 0
                   for k in ('skipped', 'errors', 'failures'))):
        raise ValueError('Final native offline tests must pass without skips')
    for field in ('gateway_image', 'guard_image'):
        if not isinstance(proof.get(field), str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', proof[field]):
            raise ValueError('Pinned qualified image required')
    return proof


def registration(document, manifest, proof):
    validate_qualification(proof, document, manifest)
    execution = candidate_execution(document)
    return dict(schema_version=1, kind='registered_direct_final89', experiment=EXPERIMENT,
        stage='final', condition=execution['harness'], parent=execution['parent'],
        base_parent=execution['base_parent'], candidate_version=CANDIDATE_VERSION,
        candidate_sha256=fingerprint(document), policy_sha256=fingerprint(POLICY),
        qualification_sha256=fingerprint(proof), sources_sha256=proof['sources_sha256'],
        model_protocol_sha256=SETTINGS.fingerprint(), input_manifest_sha256=INPUT_SHA256,
        manifest_canonical_sha256=MANIFEST_SHA256,
        python_runtime_sha256=PYTHON_SHA256, execution_contract=execution_contract(),
        primary_comparator='terminus-2', secondary_comparator='openhands',
        attempts_per_task=1, intended=89, parallel_trials=1, automatic_task_replay=False,
        cells=cells(document, manifest))


def require_policy(runtime):
    value = private_read(Path(runtime) / POLICY_FILE)
    if fingerprint(value) != fingerprint(POLICY):
        raise ValueError('Exact uncapped direct-final authority required')
    return value


def require_block(runtime):
    runtime = Path(runtime)
    require_policy(runtime)
    document = private_read(runtime / CANDIDATE_FILE)
    manifest = private_read(runtime / MANIFEST_FILE)
    proof = private_read(runtime / QUALIFICATION_FILE)
    block = private_read(runtime / REGISTRATION_FILE)
    expected = registration(document, manifest, proof)
    if fingerprint(block) != fingerprint(expected):
        raise ValueError('Exact unchanged direct-final registration required')
    return block


def require_trial(runtime, trial_id, stage):
    if (stage != 'final' or not isinstance(trial_id, str) or len(trial_id) > 120
            or not re.fullmatch(r'customfinal1-c3-\d{2}-[a-z0-9][a-z0-9_.-]*', trial_id)):
        raise ValueError('Registered direct-final attempt required')
    block = require_block(runtime)
    if not any(cell['trial_id'] == trial_id for cell in block['cells']):
        raise ValueError('Task is not registered in the final89 matrix')
    return block

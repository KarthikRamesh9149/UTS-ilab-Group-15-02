"""Lightweight contract for the measured C0-NC finalist's separate final89.

Structural validation is not native qualification or paid admission. The host
must perform fresh original/revision authentication, current-host checks and
an actual source-bound native rehearsal before registering or dispatching.
"""
import hashlib
from pathlib import Path
import re

import no_cutoff_custom_policy as development
import no_cutoff_final_candidate as candidate
from direct_final_candidate import MANIFEST_SHA256
from no_cutoff_custom_contract import CANDIDATE_VERSION, execution_contract
from portable_custom_policy import SETTINGS, INPUT_SHA256, PYTHON_SHA256, fingerprint
from retry_runtime import private_read

EXPERIMENT = 'custom-no-cutoff-final-20260928'
CONDITION = 'C0-NC'
POLICY_FILE = 'no-cutoff-final-credit-policy.json'
CANDIDATE_FILE = 'no-cutoff-final-candidate.json'
AUTHENTICATION_FILE = 'no-cutoff-final-authentication.json'
MANIFEST_FILE = 'no-cutoff-final-manifest.json'
RUNTIME_FILE = 'no-cutoff-final-runtime.json'
QUALIFICATION_FILE = 'no-cutoff-final-qualification.json'
REGISTRATION_FILE = 'no-cutoff-final-matrix.json'
POLICY = dict(development.POLICY, experiment=EXPERIMENT, predecessor=development.EXPERIMENT,
    authority='explicit-user-best-whole-candidate-direct-final89-after-single-no-cutoff-validation',
    stage='final', intended_tasks=89, confirmation='deferred-not-completed', diagnostic='deferred-not-completed')
ORCHESTRATION_FILES = frozenset({'scored_trial.py', 'local_trace.py'})
REQUIRED_SOURCE_FILES = frozenset({
    'no_cutoff_final_candidate.py', 'test_no_cutoff_final_candidate.py',
    'no_cutoff_evidence_freeze.py', 'test_no_cutoff_evidence_freeze.py',
    'no_cutoff_final_evidence.py', 'test_no_cutoff_final_evidence.py',
    'no_cutoff_final_policy.py', 'no_cutoff_final_gateway.py', 'test_no_cutoff_final_policy.py',
    'no_cutoff_final_runtime.py', 'test_no_cutoff_final_runtime.py',
})
TEST_MODULES = development.TEST_MODULES + ('test_no_cutoff_final_candidate',
    'test_no_cutoff_evidence_freeze', 'test_no_cutoff_final_evidence', 'test_no_cutoff_final_policy',
    'test_no_cutoff_final_runtime')
PROBE_MODES = development.PROBE_MODES


def candidate_execution(document):
    execution = candidate.validate_document(document)
    if (execution['harness'] != CONDITION or execution['parent'] != 'C0'
            or execution['base_parent'] is not None or execution['candidate_version'] != CANDIDATE_VERSION
            or execution['original_generation'] != 'no_cutoff'
            or fingerprint(execution['execution_contract']) != fingerprint(execution_contract())):
        raise ValueError('The actual measured C0-NC runtime is required, not a renamed original score')
    return execution


def cells(document, manifest):
    candidate_execution(document)
    if fingerprint(manifest) != MANIFEST_SHA256:
        raise ValueError('Exact original full benchmark manifest required')
    outside = sorted(manifest['outside_development_ids'], key=lambda task: (
        hashlib.sha256(('uts-stage2-dev20-v1:42:' + task).encode()).hexdigest(), task))
    tasks = manifest['development_ids'] + outside
    if len(tasks) != 89 or len(set(tasks)) != 89 or set(tasks) != set(manifest['all_task_ids']):
        raise ValueError('All 89 unique frozen tasks required')
    return [dict(trial_id=f'customfinal2-c0-nc-{index:02d}-{task}', task_id=task,
        stage='final', harness=CONDITION, parent='C0', base_parent=None)
        for index, task in enumerate(tasks, 1)]


def source_transition(document, current):
    measured = candidate_execution(document)['sources']
    logic = dict(document['original_candidate']['selection_logic_sources'])
    for name, digest in document['freeze_logic_sources'].items():
        if name in logic and logic[name] != digest:
            raise ValueError('Original and revised evidence logic must agree')
        logic[name] = digest
    development.source_bindings(current)
    if set(current) != set(measured) | set(logic) | REQUIRED_SOURCE_FILES:
        raise ValueError('Exact measured, evidence and new final source inventory required')
    if any(current[name] != digest for name, digest in logic.items()):
        raise ValueError('Original selection or revised-finalist evidence code changed')
    changes = {name for name, digest in measured.items() if current[name] != digest}
    if not changes.issubset(ORCHESTRATION_FILES):
        raise ValueError('Measured agent, tool, model, retry or evidence behaviour changed')
    return {name: dict(measured_sha256=measured[name], qualified_sha256=current[name]) for name in sorted(changes)}


def probe_checks(mode):
    return development.probe_checks(mode) | {'final_gateway_identity', 'final_stage_accounting'}


def validate_qualification(document, manifest, proof):
    """Validate metadata; the host must authenticate its real producer files."""
    execution = candidate_execution(document)
    cells(document, manifest)
    expected = dict(kind='native_no_cutoff_final_qualification', experiment=EXPERIMENT,
        status='passed', condition=CONDITION, parent='C0', base_parent=None,
        candidate_version=CANDIDATE_VERSION, candidate_sha256=fingerprint(document),
        original_candidate_sha256=fingerprint(document['original_candidate']),
        validation_results_sha256=fingerprint(document['result_bindings']),
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, manifest_canonical_sha256=MANIFEST_SHA256,
        python_runtime_sha256=PYTHON_SHA256, execution_contract=execution_contract(),
        dependencies=execution['dependencies'], setup_timeout_seconds=900, live_api_calls=0)
    if not isinstance(proof, dict) or any(fingerprint(proof.get(k)) != fingerprint(v) for k, v in expected.items()):
        raise ValueError('Separate source-bound native final qualification required')
    development.dependency_bindings(proof['dependencies'])
    transition = source_transition(document, proof.get('sources'))
    if (proof.get('sources_sha256') != fingerprint(proof['sources'])
            or fingerprint(proof.get('orchestration_changes')) != fingerprint(transition)):
        raise ValueError('Final source or explicit orchestration transition changed')
    for field in ('finalist_authentication_sha256', 'runtime_identity_sha256'):
        development._hash(proof.get(field))
    offline = proof.get('offline', {})
    if (offline.get('modules') != list(TEST_MODULES) or offline.get('passed') is not True
            or type(offline.get('tests')) is not int or offline['tests'] <= 0
            or any(type(offline.get(k)) is not int or offline[k] != 0 for k in ('skipped', 'errors', 'failures'))):
        raise ValueError('Complete source-bound final native regression run required')
    cases = proof.get('synthetic')
    if not isinstance(cases, list) or any(not isinstance(case, dict) for case in cases) or [
            case.get('mode') for case in cases] != list(PROBE_MODES):
        raise ValueError('All three actual final native lifecycle cases required')
    regression = proof.get('regression_path')
    if not isinstance(regression, str) or not re.fullmatch(
            r'\.runtime/stage2/native-no-cutoff-final-qualification-[a-zA-Z0-9_]+', regression):
        raise ValueError('Separate native final regression output required')
    files = {regression + '/regression.json', regression + '/regression.txt'}
    for case in cases:
        fixed = dict(condition=CONDITION, parent='C0', base_parent=None, status='passed', live_api_calls=0,
            kind='actual_harbor_no_cutoff_final_graph_synthetic_provider_not_benchmark_score')
        if (any(fingerprint(case.get(k)) != fingerprint(v) for k, v in fixed.items())
                or set(case.get('checks', {})) != probe_checks(case['mode'])
                or any(value is not True for value in case['checks'].values())):
            raise ValueError('Final native lifecycle evidence incomplete')
        path = case.get('runtime_path')
        if not isinstance(path, str) or not re.fullmatch(
                r'\.runtime/stage2/native-no-cutoff-final-C0-NC-' + case['mode'] + r'-[a-zA-Z0-9_]+', path):
            raise ValueError('Separate private native final lifecycle output required')
        files.update({path + '/evidence.json', path +
            '/.runtime/stage2/scored-trials/synthetic-nc-final-' + case['mode'] + '/result.json'})
    development.private_file_bindings(proof.get('evidence_files'))
    if set(proof['evidence_files']) != files:
        raise ValueError('All eight native producer outputs must be bound')
    for field in ('gateway_image', 'guard_image'):
        if not isinstance(proof.get(field), str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', proof[field]):
            raise ValueError('Pinned qualified gateway and guard image IDs required')
    if proof.get('image_sources_match') is not True:
        raise ValueError('Final gateway image must contain the qualified source')
    if (proof.get('python_runtime', {}).get('sha256') != PYTHON_SHA256
            or proof.get('host_environment', {}).get('execution_mode') != 'native_linux_x86_64'):
        raise ValueError('Actual native host and original Python runtime required')
    return proof


def registration(document, manifest, proof):
    validate_qualification(document, manifest, proof)
    return dict(schema_version=1, kind='registered_no_cutoff_final89', experiment=EXPERIMENT,
        stage='final', condition=CONDITION, parent='C0', base_parent=None, candidate_version=CANDIDATE_VERSION,
        candidate_sha256=fingerprint(document), original_candidate_sha256=fingerprint(document['original_candidate']),
        validation_results_sha256=fingerprint(document['result_bindings']),
        policy_sha256=fingerprint(POLICY), qualification_sha256=fingerprint(proof),
        sources_sha256=proof['sources_sha256'],
        orchestration_changes={name: dict(change) for name, change in proof['orchestration_changes'].items()},
        finalist_authentication_sha256=proof['finalist_authentication_sha256'], runtime_identity_sha256=proof['runtime_identity_sha256'],
        model_protocol_sha256=SETTINGS.fingerprint(), input_manifest_sha256=INPUT_SHA256,
        manifest_canonical_sha256=MANIFEST_SHA256, python_runtime_sha256=PYTHON_SHA256,
        execution_contract=execution_contract(), primary_comparator='terminus-2', secondary_comparator='openhands',
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run',
        attempts_per_task=1, intended=89, parallel_trials=1, automatic_task_replay=False,
        cells=cells(document, manifest))


def require_policy(runtime):
    value = private_read(Path(runtime) / POLICY_FILE)
    if fingerprint(value) != fingerprint(POLICY):
        raise ValueError('Exact uncapped no-cutoff final authority required')
    return value


def require_block(runtime):
    runtime = Path(runtime)
    require_policy(runtime)
    document = private_read(runtime / CANDIDATE_FILE)
    manifest = private_read(runtime / MANIFEST_FILE)
    proof = private_read(runtime / QUALIFICATION_FILE)
    block = private_read(runtime / REGISTRATION_FILE)
    if fingerprint(block) != fingerprint(registration(document, manifest, proof)):
        raise ValueError('Exact unchanged no-cutoff final registration required')
    return block


def require_trial(runtime, trial_id, stage):
    if (stage != 'final' or not isinstance(trial_id, str) or len(trial_id) > 120
            or not re.fullmatch(r'customfinal2-c0-nc-\d{2}-[a-z0-9][a-z0-9_.-]*', trial_id)):
        raise ValueError('Registered no-cutoff final attempt required')
    block = require_block(runtime)
    if not any(cell['trial_id'] == trial_id for cell in block['cells']):
        raise ValueError('Task is not registered in the no-cutoff final89 matrix')
    return block

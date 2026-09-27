"""One separately measured C0-NC development block, never a renamed C0 score.

This lightweight module validates contracts, not the authenticity of native
execution. Host admission must additionally authenticate original evidence,
hold ancestor locks and check a real source-bound native qualification.
"""
from pathlib import Path
import re

from direct_final_candidate import validate_document
from deadline_custom_policy import source_bindings, dependency_bindings
from no_cutoff_custom_contract import CANDIDATE_VERSION, execution_contract
from portable_custom_policy import (POLICY as PREDECESSOR_POLICY, SETTINGS,
    DEVELOPMENT_SHA256, INPUT_SHA256, PYTHON_SHA256, fingerprint)
from retry_runtime import private_read

EXPERIMENT = 'custom-no-cutoff-development-20260928'
CONDITION = 'C0-NC'
ORIGINAL_FREEZE_SHA256 = '378e7ddfea1b8ad7b63a2fec4f466b3a9dbdc43d229b0fb379e5265e04b57c66'
POLICY_FILE = 'no-cutoff-credit-policy.json'
CANDIDATE_FILE = 'no-cutoff-original-candidate.json'
AUTHENTICATION_FILE = 'no-cutoff-original-authentication.json'
RUNTIME_FILE = 'no-cutoff-runtime.json'
QUALIFICATION = 'no-cutoff-qualification.json'
BLOCKS = 'no-cutoff-development-blocks'
POLICY = dict(PREDECESSOR_POLICY, experiment=EXPERIMENT,
    candidate_version=CANDIDATE_VERSION, predecessor='custom-deadline-development-20260927',
    authorised_date='2026-09-28', authority='selected-c0-single-no-cutoff-validation',
    original_freeze_sha256=ORIGINAL_FREEZE_SHA256, allowed_conditions=[CONDITION],
    execution_contract=execution_contract(),
    design='whole-c0-without-time-advice-plus-disclosed-capture-transport-correction')

REQUIRED_SOURCE_FILES = frozenset({
    'no_cutoff_custom_contract.py', 'no_cutoff_custom_agent.py', 'no_cutoff_capture_backend.py',
    'no_cutoff_custom_policy.py', 'no_cutoff_custom_gateway.py', 'no_cutoff_custom_runtime.py',
    'no_cutoff_custom_study.py', 'run_no_cutoff_custom.py',
    'test_no_cutoff_custom_agent.py', 'test_no_cutoff_capture_backend.py',
    'test_no_cutoff_custom_policy.py', 'test_no_cutoff_custom_runtime.py',
    'test_no_cutoff_custom_study.py',
    'direct_final_candidate.py', 'direct_final_policy.py', 'direct_final_evidence.py',
    'direct_final_runtime.py', 'test_direct_final_policy.py', 'test_direct_final_evidence.py',
    'test_direct_final_runtime.py',
    'qualify_no_cutoff_custom.py', 'no_cutoff_custom_probe.py', 'export_no_cutoff_custom.py',
    'fixtures/Dockerfile.custom-no-cutoff', 'test_no_cutoff_custom_probe.py',
    'test_qualify_no_cutoff_custom.py', 'test_export_no_cutoff_custom.py',
})
ORCHESTRATION_DELTAS = frozenset({'scored_trial.py', 'local_trace.py'})
TEST_MODULES = ('test_no_cutoff_custom_agent', 'test_no_cutoff_capture_backend',
    'test_no_cutoff_custom_policy', 'test_no_cutoff_custom_runtime', 'test_no_cutoff_custom_study',
    'test_no_cutoff_custom_probe', 'test_qualify_no_cutoff_custom', 'test_export_no_cutoff_custom',
    'test_custom_deadline_execution', 'test_custom_process_capture', 'test_custom_text_transport',
    'test_custom_python_runtime', 'test_custom_dispatch_stop', 'test_retry_gateway',
    'test_credit_only_gateway', 'test_scored_trial', 'test_trial_execution',
    'custom_runner_tests', 'custom_backend_tests', 'custom_jobs_tests')
PROBE_MODES = ('tools', 'cancel_setup', 'boundary_stop')
BASE_CHECKS = frozenset({'model_revoked', 'expected_status', 'expected_verifier_result',
    'actual_pythonless_image', 'runtime_archive_bound', 'all_physical_requests_accounted',
    'unknown_costs_retained', 'no_receipt_or_credit_block', 'traces_recorded',
    'containers_removed', 'networks_removed', 'volumes_removed', 'sources_unchanged',
    'host_unchanged', 'images_unchanged', 'fixture_resources_audited'})
TOOL_CHECKS = frozenset({'actual_custom_tool_roundtrip', 'recovered_one_transient',
    'media_tool_text_only', 'long_read_and_tail', 'timeout_exit_124', 'background_service_alive',
    'no_dynamic_time_advice', 'more_than_two_repairs', 'no_command_count_quota',
    'command_passed_sixty_seconds', 'encoded_capture_process_matching', 'sizeable_command_capture'})


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Exact SHA256 binding required')


def private_file_bindings(value):
    if not isinstance(value, dict) or not value or any(
            not isinstance(name, str) or not name.startswith('.runtime/stage2/') for name in value):
        raise ValueError('Private runtime file bindings required')
    # The source-map validator intentionally rejects hidden leading names.
    # Strip only the exact allowed private prefix, not arbitrary dot paths.
    source_bindings({name.removeprefix('.runtime/stage2/'): sha for name, sha in value.items()})


def candidate_execution(document):
    selection = validate_document(document)
    execution = document['selected_execution']
    if (fingerprint(document) != ORIGINAL_FREEZE_SHA256 or selection['selected'] != 'C0'
            or execution['harness'] != 'C0' or execution['parent'] is not None
            or execution['base_parent'] is not None or execution['original_generation'] != 'portable'
            or execution['candidate_version'] != 'stage2-candidate-0.3.0'):
        raise ValueError('Only the already audited whole C0 may enter this single revision')
    return execution


def source_transition(document, current):
    candidate_execution(document)
    inherited = document['candidate']['c3_sources']
    logic = document['selection_logic_sources']
    expected = set(inherited) | set(logic) | REQUIRED_SOURCE_FILES
    source_bindings(current)
    if set(current) != expected:
        raise ValueError('Exact original, reused deadline, selection and revision source set required')
    if any(current[name] != sha for name, sha in logic.items()):
        raise ValueError('Original selection logic must not change')
    changes = {}
    for name, sha in inherited.items():
        if current[name] != sha:
            if name not in ORCHESTRATION_DELTAS:
                raise ValueError('Reused qualified implementation changed outside explicit admission hooks')
            changes[name] = dict(original_sha256=sha, revised_sha256=current[name])
    # C3 already changed construction hooks in three portable files. Retain
    # both original maps, rather than pretending the new assembly is C0 0.3.
    portable = document['selected_execution']['sources']
    if not set(portable).issubset(inherited):
        raise ValueError('Reused deadline implementation must retain the original source inventory')
    reused = {name: dict(portable_sha256=sha, deadline_sha256=inherited[name])
              for name, sha in portable.items() if sha != inherited.get(name)}
    return dict(original_execution_sha256=fingerprint(document['selected_execution']),
        reused_deadline_sources_sha256=fingerprint(inherited),
        inherited_portable_changes=reused, orchestration_changes=changes)


def cells(development):
    if (not isinstance(development, list) or len(development) != 20
            or fingerprint(development) != DEVELOPMENT_SHA256):
        raise ValueError('Exact original fixed20 split and order required')
    return [dict(trial_id=f'customdev4-c0-nc-{i:02d}-{task}', task_id=task, harness=CONDITION)
            for i, task in enumerate(development, 1)]


def probe_checks(mode):
    if mode not in PROBE_MODES:
        raise ValueError('Unknown no-cutoff native fixture mode')
    return BASE_CHECKS | ({'cancelled_setup_evidence'} if mode == 'cancel_setup' else TOOL_CHECKS) | (
        {'cooperative_stop_persisted', 'no_next_dispatch'} if mode == 'boundary_stop' else set())


def validate_qualification(document, proof):
    execution = candidate_execution(document)
    expected = dict(kind='native_no_cutoff_development_qualification', experiment=EXPERIMENT,
        status='passed', condition=CONDITION, parent='C0', base_parent=None,
        candidate_version=CANDIDATE_VERSION, original_candidate_sha256=fingerprint(document),
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, execution_contract=execution_contract(),
        dependencies=execution['dependencies'], live_api_calls=0, setup_timeout_seconds=900)
    if not isinstance(proof, dict) or any(fingerprint(proof.get(k)) != fingerprint(v) for k, v in expected.items()):
        raise ValueError('Separate source-bound native C0-NC qualification required')
    dependency_bindings(proof['dependencies'])
    transition = source_transition(document, proof.get('sources'))
    if (proof.get('sources_sha256') != fingerprint(proof['sources'])
            or fingerprint(proof.get('source_transition')) != fingerprint(transition)
            or proof.get('python_runtime', {}).get('sha256') != PYTHON_SHA256):
        raise ValueError('Revision source or Python runtime binding differs')
    for key in ('original_authentication_sha256', 'runtime_identity_sha256'):
        _hash(proof.get(key))
    offline = proof.get('offline', {})
    if (offline.get('modules') != list(TEST_MODULES) or offline.get('passed') is not True
            or type(offline.get('tests')) is not int or offline['tests'] <= 0
            or any(type(offline.get(k)) is not int or offline[k] != 0 for k in ('skipped', 'errors', 'failures'))):
        raise ValueError('Complete source-bound native regression run required')
    cases = proof.get('synthetic')
    if not isinstance(cases, list) or [v.get('mode') for v in cases] != list(PROBE_MODES):
        raise ValueError('All three actual no-cutoff native lifecycle cases required')
    for case in cases:
        fixed = dict(condition=CONDITION, parent='C0', base_parent=None, status='passed', live_api_calls=0,
            kind='actual_harbor_no_cutoff_graph_synthetic_provider_not_benchmark_score')
        if (any(fingerprint(case.get(k)) != fingerprint(v) for k, v in fixed.items())
                or set(case.get('checks', {})) != probe_checks(case['mode'])
                or any(v is not True for v in case['checks'].values())):
            raise ValueError('Native no-cutoff lifecycle evidence incomplete')
    evidence = proof.get('evidence_files')
    private_file_bindings(evidence)
    regression = proof.get('regression_path')
    if not isinstance(regression, str) or not re.fullmatch(
            r'\.runtime/stage2/native-no-cutoff-qualification-[a-zA-Z0-9_]+', regression):
        raise ValueError('Private native regression output required')
    expected_files = {regression + '/regression.json', regression + '/regression.txt'}
    for case in cases:
        path = case.get('runtime_path')
        if not isinstance(path, str) or not re.fullmatch(
                r'\.runtime/stage2/native-no-cutoff-C0-NC-' + case['mode'] + r'-[a-zA-Z0-9_]+', path):
            raise ValueError('Private actual native lifecycle output required')
        expected_files.update({path + '/evidence.json', path +
            '/.runtime/stage2/scored-trials/synthetic-nc-' + case['mode'] + '/result.json'})
    if set(evidence) != expected_files:
        raise ValueError('All regression and native lifecycle output files must be bound')
    for name in ('gateway_image', 'guard_image'):
        if not isinstance(proof.get(name), str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', proof[name]):
            raise ValueError('Qualified gateway and guard image IDs required')
    if proof.get('image_sources_match') is not True:
        raise ValueError('Gateway image must contain the qualified source')
    return proof


def registration(document, proof, development):
    validate_qualification(document, proof)
    return dict(experiment=EXPERIMENT, stage='development', condition=CONDITION, parent='C0',
        base_parent=None, candidate_version=CANDIDATE_VERSION, python_runtime_sha256=PYTHON_SHA256,
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        original_candidate_sha256=fingerprint(document),
        original_results_sha256=fingerprint(document['candidate']['result_bindings']),
        sources_sha256=proof['sources_sha256'], source_transition=proof['source_transition'],
        original_authentication_sha256=proof['original_authentication_sha256'],
        runtime_identity_sha256=proof['runtime_identity_sha256'], qualification_sha256=fingerprint(proof),
        input_manifest_sha256=INPUT_SHA256, development_ids=development,
        primary_comparator='terminus-2', secondary_comparator='openhands',
        execution_contract=execution_contract(), cells=cells(development))


def block_path(runtime):
    folder = Path(runtime) / BLOCKS
    if folder.is_symlink():
        raise ValueError('Unsafe revision registry')
    return folder / (CONDITION + '.json')


def require_policy(runtime):
    value = private_read(Path(runtime) / POLICY_FILE)
    if fingerprint(value) != fingerprint(POLICY):
        raise ValueError('Exact uncapped C0-NC authority required')
    return value


def require_block(runtime):
    runtime = Path(runtime)
    require_policy(runtime)
    document = private_read(runtime / CANDIDATE_FILE)
    proof = private_read(runtime / QUALIFICATION)
    value = private_read(block_path(runtime))
    expected = registration(document, proof, value.get('development_ids'))
    if fingerprint(value) != fingerprint(expected):
        raise ValueError('Immutable no-cutoff block differs from the qualified registration')
    return value


def require_trial(runtime, trial_id, stage):
    if (stage != 'development' or not isinstance(trial_id, str) or len(trial_id) > 120
            or not re.fullmatch(r'customdev4-c0-nc-\d{2}-[a-z0-9][a-z0-9_.-]*', trial_id)):
        raise ValueError('Only a registered C0-NC development attempt is admitted')
    block = require_block(runtime)
    if not any(row['trial_id'] == trial_id for row in block['cells']):
        raise ValueError('Unregistered no-cutoff attempt')
    return block

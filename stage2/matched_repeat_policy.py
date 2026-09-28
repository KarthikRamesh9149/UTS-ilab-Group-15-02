"""Lightweight matched-repeat contracts, not a host or paid-launch permit.

The future host must freshly authenticate predecessor audits and actual
off-server archives, original native baseline behaviour, current runtime and
real qualification producers. Self-consistent JSON cannot prove those actions.
Neither this module nor its gateway adds a scored-runner admission route.
"""
from copy import deepcopy
from pathlib import Path, PurePosixPath
import re

from matched_repeat_schedule import (EXPERIMENT, HARNESSES, SETTINGS, MODEL_SHA256,
    MANIFEST_SHA256, BASELINE_CSV_SHA256, fingerprint, schedule)
from retry_runtime import private_read

POLICY_FILE = 'matched-repeat-credit-policy.json'
MANIFEST_FILE = 'matched-repeat-manifest.json'
BASELINE_FILE = 'matched-repeat-original-qualification.json'
FINAL_FILE = 'matched-repeat-custom-final-qualification.json'
PREDECESSOR_FILE = 'matched-repeat-predecessor-authentication.json'
QUALIFICATION_FILE = 'matched-repeat-qualification.json'
REGISTRATION_FILE = 'matched-repeat-matrix.json'
ORIGINAL_QUALIFICATION_SHA256 = 'fc55f955f3e883b919704fc606e51bb530724559aa89a14a9a7b844ccc9bf686'
CUSTOM_FINAL_QUALIFICATION_SHA256 = 'b3e05d9c216463b044e3b264aa449cecb92d8b9bd8cbc33b77189e434107087e'
CUSTOM_FINAL_REGISTRATION_SHA256 = '17a4139c4f68b2e6d8e5b62db910242e3562662192c13da51e62f53441f764b2'
CUSTOM_FINAL_SOURCES_SHA256 = '4f73ab4083b76f555ff3bf695d7fed87ddbf4e5982551473418b8005eaf24d05'
CUSTOM_FINAL_EXPERIMENT = 'custom-no-cutoff-final-20260928'
POLICY = dict(schema_version=1, experiment=EXPERIMENT,
    authority='explicit-user-one-repeat-per-original-baseline-after-custom-final89',
    accounting_mode='provider-credit-only', project_cap_usd=None, stage_cap_usd=None,
    per_task_cap_usd=None, reserve_usd='0', model_call_cap=None,
    physical_request_count_cap=None, retry_count_cap=None, provider_max_price=None,
    accounting_blocks_dispatch=False, unknown_cost_is_zero=False,
    automatic_top_up=False, automatic_purchase=False, automatic_credit_limit_increase=False,
    model=SETTINGS.document(), attempts_per_task=1, parallel_trials=1,
    task_time_and_resources='official-unchanged',
    physical_request_retry='undelivered-transient-only-within-task-deadline',
    shared_provider_cooldown=True, baseline_agent_behaviour='original-corrected-unchanged',
    inherited_baseline_turn_guards={'terminus-2': 1000000, 'openhands': 1000000},
    native_guards_are_benchmark_rules=False, original_results_replaced=False,
    execution_order=['custom-final89', *HARNESSES],
    confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run')
REQUIRED_SOURCE_FILES = frozenset({'matched_repeat_schedule.py', 'test_matched_repeat_schedule.py',
    'matched_repeat_policy.py', 'matched_repeat_gateway.py', 'test_matched_repeat_policy.py',
    'test_native_agents.py', 'test_trial_execution.py', 'test_scored_trial.py',
    'openhands_fixture_audit.json'})
TEST_MODULES = ('test_matched_repeat_schedule', 'test_matched_repeat_policy',
    'test_native_agents', 'test_retry_gateway', 'test_credit_only_gateway',
    'test_trial_execution', 'test_scored_trial')
ORCHESTRATION_FILES = frozenset({'scored_trial.py', 'local_trace.py'})
# These seven deltas are already present in the pinned, qualified custom-final
# execution library. Recording them does not claim the original 84-file
# baseline tree was byte-identical to the later shared library.
INHERITED_BASELINE_DELTAS = frozenset({'credit_only_gateway.py', 'retry_gateway.py',
    'trial_execution.py', 'local_trace.py', 'scored_trial.py', 'custom_model.py', 'custom_runner.py'})
BASELINE_BEHAVIOUR_FILES = frozenset({'native_agents.py', 'recovery_agents.py',
    'openhands-requirements.lock', 'model_protocol.py', 'gateway_policy.py',
    'retry_policy.py', 'retry_runtime.py', 'retry_transport.py'})
PROBE_MODES = ('tools', 'cancel_setup', 'boundary_stop')


def _hash(value):
    if not isinstance(value, str) or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Exact SHA256 binding required')


def _bindings(value, *, private=False):
    if not isinstance(value, dict) or not value:
        raise ValueError('Nonempty file bindings required')
    for name, sha in value.items():
        if private:
            if not isinstance(name, str) or not name.startswith('.runtime/stage2/'):
                raise ValueError('Private native producer path required')
            name = name.removeprefix('.runtime/stage2/')
        path = PurePosixPath(name) if isinstance(name, str) else None
        if (path is None or path.is_absolute() or '..' in path.parts or str(path) != name
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', name)):
            raise ValueError('Normalised relative file path required')
        _hash(sha)


def _harness(value):
    if value not in HARNESSES:
        raise ValueError('Only the two separately registered baseline repeats are authorised')
    return value


def anchors(original, final):
    """Pinned metadata only; this is not a native baseline-source audit."""
    if (not isinstance(original, dict) or fingerprint(original) != ORIGINAL_QUALIFICATION_SHA256
            or not isinstance(final, dict) or fingerprint(final) != CUSTOM_FINAL_QUALIFICATION_SHA256):
        raise ValueError('Exact original baseline and qualified custom-final anchors required')
    _bindings(original['sources']); _bindings(final['sources'])
    if (final['sources_sha256'] != CUSTOM_FINAL_SOURCES_SHA256
            or fingerprint(final['sources']) != CUSTOM_FINAL_SOURCES_SHA256
            or not set(original['sources']).issubset(final['sources'])
            or not BASELINE_BEHAVIOUR_FILES.issubset(original['sources'])):
        raise ValueError('Original baseline and shared final source inventory disagree')
    changed = {name for name, sha in original['sources'].items() if final['sources'][name] != sha}
    if changed != INHERITED_BASELINE_DELTAS or changed & BASELINE_BEHAVIOUR_FILES:
        raise ValueError('Only the disclosed inherited execution-library deltas are allowed')
    if (original['policy']['terminus_default_max_turns'] != 1000000
            or original['policy']['openhands_max_iterations'] != 1000000
            or original['model_protocol_sha256'] != MODEL_SHA256
            or final['model_protocol_sha256'] != MODEL_SHA256):
        raise ValueError('Preserve original baseline controls and fixed model protocol')
    return final['sources']


def source_transition(original, final, current):
    inherited = anchors(original, final)
    _bindings(current)
    if set(current) != set(inherited) | REQUIRED_SOURCE_FILES:
        raise ValueError('Exact original, shared final and new repeat source inventory required')
    if not {name + '.py' for name in TEST_MODULES}.issubset(current):
        raise ValueError('Every declared native regression module must be source-bound')
    changes = {name for name, sha in inherited.items() if current[name] != sha}
    if not changes.issubset(ORCHESTRATION_FILES):
        raise ValueError('Baseline agent, tool, retry, model or prior evidence code changed')
    return dict(original_sources_sha256=fingerprint(original['sources']),
        reused_final_sources_sha256=CUSTOM_FINAL_SOURCES_SHA256,
        inherited_baseline_changes={name: dict(original_sha256=original['sources'][name],
            final_sha256=inherited[name]) for name in sorted(INHERITED_BASELINE_DELTAS)},
        orchestration_changes={name: dict(final_sha256=inherited[name], repeat_sha256=current[name])
            for name in sorted(changes)})


def cells(manifest, harness):
    _harness(harness)
    return schedule(manifest)['blocks'][HARNESSES.index(harness)]['cells']


def validate_predecessors(record, manifest, harness):
    """Require exact lineage/coverage; a future host must verify the real bytes.

    No scores enter the continuation decision. Failed or missing verifier
    outcomes remain represented by their original result hashes.
    """
    _harness(harness)
    plan = schedule(manifest)
    fields = {'kind', 'successor_harness', 'schedule_sha256', 'blocks', 'paid_launch_ready'}
    if (not isinstance(record, dict) or set(record) != fields
            or record['kind'] != 'authenticated_matched_repeat_predecessors_not_paid_admission'
            or record['successor_harness'] != harness or record['schedule_sha256'] != fingerprint(plan)
            or record['paid_launch_ready'] is not False or not isinstance(record['blocks'], list)
            or len(record['blocks']) != 1 + HARNESSES.index(harness)):
        raise ValueError('Exact sequential audited-and-backed-up predecessor lineage required')
    block_fields = {'experiment', 'harness', 'qualification_sha256', 'registration_sha256',
        'sources_sha256', 'results_sha256', 'audit_sha256', 'archive_sha256', 'backup_record_sha256'}
    for index, block in enumerate(record['blocks']):
        expected_harness = 'C0-NC' if index == 0 else 'terminus-2'
        expected_experiment = CUSTOM_FINAL_EXPERIMENT if index == 0 else EXPERIMENT
        if (not isinstance(block, dict) or set(block) != block_fields
                or block['harness'] != expected_harness or block['experiment'] != expected_experiment):
            raise ValueError('Predecessor order or identity changed')
        for key in block_fields - {'experiment', 'harness', 'results_sha256'}:
            _hash(block[key])
        expected_ids = ({f'customfinal2-c0-nc-{i:02d}-{cell["task_id"]}'
            for i, cell in enumerate(plan['blocks'][0]['cells'], 1)} if index == 0 else {
                cell['trial_id'] for cell in plan['blocks'][0]['cells']})
        _bindings(block['results_sha256'])
        if set(block['results_sha256']) != expected_ids:
            raise ValueError('All 89 distinct predecessor result files must be bound, without replay')
        if index == 0 and any(block[key] != value for key, value in (
                ('qualification_sha256', CUSTOM_FINAL_QUALIFICATION_SHA256),
                ('registration_sha256', CUSTOM_FINAL_REGISTRATION_SHA256),
                ('sources_sha256', CUSTOM_FINAL_SOURCES_SHA256))):
            raise ValueError('The actual qualified and registered custom final89 is required')
    return record


def probe_checks(mode):
    if mode not in PROBE_MODES:
        raise ValueError('Unknown native repeat qualification case')
    base = {'expected_status', 'expected_verifier_result', 'model_revoked',
        'all_physical_requests_accounted', 'unknown_costs_retained', 'no_receipt_or_credit_block',
        'traces_recorded', 'containers_removed', 'networks_removed', 'volumes_removed',
        'sources_unchanged', 'host_unchanged', 'images_unchanged', 'fixture_resources_audited',
        'repeat_gateway_identity', 'final_stage_accounting'}
    return base | ({'cancelled_setup_evidence'} if mode == 'cancel_setup' else {
        'actual_native_harness_tool_roundtrip', 'recovered_one_transient', 'baseline_controls_preserved'}) | (
        {'cooperative_stop_persisted', 'no_next_dispatch'} if mode == 'boundary_stop' else set())


def validate_qualification(original, final, predecessors, manifest, proof):
    """Structural contract only. Real native artifacts must be read by the host."""
    if not isinstance(proof, dict) or proof.get('paid_launch_ready', False) is not False:
        raise ValueError('Separate native matched-repeat qualification required')
    harness = _harness(proof.get('harness'))
    validate_predecessors(predecessors, manifest, harness)
    transition = source_transition(original, final, proof.get('sources'))
    expected = dict(schema_version=1, kind='native_matched_baseline_repeat_qualification',
        experiment=EXPERIMENT, status='passed', harness=harness, live_api_calls=0,
        setup_timeout_seconds=900, policy_sha256=fingerprint(POLICY),
        schedule_sha256=fingerprint(schedule(manifest)), manifest_canonical_sha256=MANIFEST_SHA256,
        model_protocol_sha256=MODEL_SHA256, original_baseline_csv_sha256=BASELINE_CSV_SHA256,
        original_qualification_sha256=ORIGINAL_QUALIFICATION_SHA256,
        custom_final_qualification_sha256=CUSTOM_FINAL_QUALIFICATION_SHA256,
        predecessor_authentication_sha256=fingerprint(predecessors),
        inherited_baseline_turn_guards=POLICY['inherited_baseline_turn_guards'],
        dependencies=final['dependencies'], sources_sha256=fingerprint(proof['sources']),
        source_transition=transition)
    if any(fingerprint(proof.get(k)) != fingerprint(v) for k, v in expected.items()):
        raise ValueError('Exact separate native repeat source/runtime/lineage proof required')
    for key in ('baseline_behaviour_authentication_sha256', 'runtime_identity_sha256'):
        _hash(proof.get(key))
    if proof.get('host_environment', {}).get('execution_mode') != 'native_linux_x86_64':
        raise ValueError('Actual native Linux repeat execution required')
    offline = proof.get('offline', {})
    if (offline.get('modules') != list(TEST_MODULES) or offline.get('passed') is not True
            or type(offline.get('tests')) is not int or offline['tests'] <= 0
            or any(type(offline.get(k)) is not int or offline[k] != 0 for k in ('skipped', 'errors', 'failures'))):
        raise ValueError('Complete native repeat regression outputs required')
    regression = proof.get('regression_path')
    if not isinstance(regression, str) or not re.fullmatch(
            r'\.runtime/stage2/native-matched-repeat-' + harness + r'-qualification-[a-zA-Z0-9_]+', regression):
        raise ValueError('Separate native repeat regression path required')
    cases = proof.get('synthetic')
    if (not isinstance(cases, list) or any(not isinstance(c, dict) for c in cases)
            or [c.get('mode') for c in cases] != list(PROBE_MODES)):
        raise ValueError('All three actual native baseline lifecycle cases required')
    files = {regression + '/regression.json', regression + '/regression.txt'}
    for case in cases:
        fixed = dict(harness=harness, status='passed', live_api_calls=0,
            kind='actual_native_matched_baseline_synthetic_provider_not_benchmark_score')
        if (any(fingerprint(case.get(k)) != fingerprint(v) for k, v in fixed.items())
                or set(case.get('checks', {})) != probe_checks(case['mode'])
                or any(v is not True for v in case['checks'].values())):
            raise ValueError('Actual repeat lifecycle evidence incomplete')
        path = case.get('runtime_path')
        if not isinstance(path, str) or not re.fullmatch(r'\.runtime/stage2/native-matched-repeat-'
                + harness + '-' + case['mode'] + r'-[a-zA-Z0-9_]+', path):
            raise ValueError('Separate private baseline lifecycle path required')
        files.update({path + '/evidence.json', path + '/.runtime/stage2/scored-trials/'
            + 'synthetic-matched-repeat-' + harness + '-' + case['mode'] + '/result.json'})
    _bindings(proof.get('evidence_files'), private=True)
    if set(proof['evidence_files']) != files:
        raise ValueError('All eight real native producer artifacts must be bound')
    for key in ('gateway_image', 'guard_image'):
        if not isinstance(proof.get(key), str) or not re.fullmatch(r'sha256:[a-f0-9]{64}', proof[key]):
            raise ValueError('Pinned qualified images required')
    if proof.get('image_sources_match') is not True:
        raise ValueError('Gateway must contain the qualified repeat source')
    return proof


def registration(original, final, predecessors, manifest, proof):
    validate_qualification(original, final, predecessors, manifest, proof)
    return dict(schema_version=1, kind='registered_matched_baseline_repeat89', experiment=EXPERIMENT,
        harness=proof['harness'], stage='final', phase='matched-baseline-repeat', intended=89,
        attempts_per_task=1, parallel_trials=1, automatic_task_replay=False,
        schedule_sha256=fingerprint(schedule(manifest)), policy_sha256=fingerprint(POLICY),
        qualification_sha256=fingerprint(proof), sources_sha256=proof['sources_sha256'],
        source_transition=deepcopy(proof['source_transition']),
        predecessor_authentication_sha256=fingerprint(predecessors),
        baseline_behaviour_authentication_sha256=proof['baseline_behaviour_authentication_sha256'],
        runtime_identity_sha256=proof['runtime_identity_sha256'],
        original_qualification_sha256=ORIGINAL_QUALIFICATION_SHA256,
        custom_final_qualification_sha256=CUSTOM_FINAL_QUALIFICATION_SHA256,
        model_protocol_sha256=MODEL_SHA256, manifest_canonical_sha256=MANIFEST_SHA256,
        original_baseline_csv_sha256=BASELINE_CSV_SHA256,
        inherited_baseline_turn_guards=dict(POLICY['inherited_baseline_turn_guards']),
        primary_comparator='terminus-2', secondary_comparator='openhands',
        original_scores={'terminus-2': 52, 'openhands': 44}, original_results_replaced=False,
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run',
        cells=cells(manifest, proof['harness']))


def require_policy(runtime):
    value = private_read(Path(runtime) / POLICY_FILE)
    if fingerprint(value) != fingerprint(POLICY):
        raise ValueError('Exact uncapped matched-repeat authority required')
    return value


def require_block(runtime):
    runtime = Path(runtime)
    require_policy(runtime)
    original = private_read(runtime / BASELINE_FILE)
    final = private_read(runtime / FINAL_FILE)
    predecessors = private_read(runtime / PREDECESSOR_FILE)
    manifest = private_read(runtime / MANIFEST_FILE)
    proof = private_read(runtime / QUALIFICATION_FILE)
    block = private_read(runtime / REGISTRATION_FILE)
    if fingerprint(block) != fingerprint(registration(original, final, predecessors, manifest, proof)):
        raise ValueError('Exact unchanged matched-repeat registration required')
    return block


def require_trial(runtime, trial_id, stage):
    if (stage != 'final' or not isinstance(trial_id, str) or len(trial_id) > 120
            or not re.fullmatch(r'matchedrepeat1-(terminus-2|openhands)-\d{2}-[a-z0-9][a-z0-9_.-]*', trial_id)):
        raise ValueError('Only a registered matched-repeat attempt is admitted')
    block = require_block(runtime)
    if not any(cell['trial_id'] == trial_id for cell in block['cells']):
        raise ValueError('Attempt is not in this separately qualified baseline block')
    return block

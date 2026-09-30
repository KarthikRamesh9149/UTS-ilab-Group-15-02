"""Separate three-cell recovery contracts, never a native admission witness.

The gateway checks private input bytes and structural qualification/lineage.
Only a real source-bound host session may authenticate audits, the retained
archive, actual producers/images and grant scoped scored execution. Saved JSON
accepted here does not perform or prove those operations.
"""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

import no_cutoff_recovery_plan as plan
from no_cutoff_custom_contract import CANDIDATE_VERSION, execution_contract
from portable_custom_policy import INPUT_SHA256, PYTHON_SHA256

EXPERIMENT = plan.EXPERIMENT
CONDITION = 'C0-NC'
SETTINGS = plan.SETTINGS
MODEL_SHA256 = plan.MODEL_SHA256
MANIFEST_SHA256 = plan.MANIFEST_SHA256
fingerprint = plan.fingerprint
PLAN_SHA256 = 'dd46fb43239d1b84ffcf0e387c234f6f8df693852f18bdaeeb7a034bdc3cdd38'
ORIGINAL_QUALIFICATION = plan.ORIGINAL_QUALIFICATION
ORIGINAL_QUALIFICATION_FILE_SHA256 = '008f2998d0df7646ba351c76b5a343354e25f4d99fdf66f05dee39e6ea19d110'
ORIGINAL_SOURCE_SET = plan.ORIGINAL_SOURCE_SET
ORIGINAL_RESULTS_SHA256 = 'cf8ad3c0edb6dd212535e89674171de2e452db112de491cef52abfb83a96cf02'
ORIGINAL_CANDIDATE = '29bcc290a269944441f40d6b8c904aed584d16d2a7c658465e5be16e906a5ecd'
ARCHIVE_SHA256 = '7e53dd3eb45bec457f81d59b694fd171a949fbf123f02baa14f4158d9634a400'
SNAPSHOT_SHA256 = '1e0855681c4a900d251ef44b6104876e246a71fe5cf502cb9a447e817afc7553'
AUDIT_SHA256 = 'b4bb9d1b0c076fd129bcac6a40827e335ad9b66fc57d4a2bb617a8b578584879'
BACKUP_SHA256 = 'e89db8545f072a44ab590df75ddce40e5f88e7ff6e8782607a247934cc1708f1'
REPORTER_COMMIT = 'a74e0dd053fed70a1ede3eef23e0ccdb6db6fb09'
PREPARATION_SHA256 = 'fb1cf6c9e3a6ee79579de2ebcbfd0f97cac39e989000bbb77b20a00f114b6815'
COMMAND_SHA256 = 'ce4b19308a2c727d159110d218fb6a8d5492d1f3842b2156d3e9fc9500fc2d76'
PUBLIC_FILES = {
    'summary.json': '468043e2a2e375e3f15f4e6683b89121e0ee38beab235fa3d02926219c177881',
    'trials.json': '53b0da52330102e17aebc928cbc3b19466fc3125e8be9ec218862eeb46ca4fe0',
    'trials.csv': 'ecc5cf3e7a4220688a8bf87e97ed104f74dc810baa3ad8fc432e0d07c3ac9a72'}
POLICY_FILE = 'no-cutoff-recovery-credit-policy.json'
PLAN_FILE = 'no-cutoff-recovery-plan.json'
MANIFEST_FILE = 'no-cutoff-recovery-manifest.json'
ORIGINAL_FILE = 'no-cutoff-recovery-original-qualification.json'
PREDECESSOR_FILE = 'no-cutoff-recovery-predecessor.json'
RUNTIME_FILE = 'no-cutoff-recovery-runtime.json'
QUALIFICATION_FILE = 'no-cutoff-recovery-qualification.json'
REGISTRATION_FILE = 'no-cutoff-recovery-matrix.json'
QUALIFIER_INTENT_FILE = 'no-cutoff-recovery-qualification-intent.json'
QUALIFIER_RESULT_FILE = 'no-cutoff-recovery-qualification-result.json'
QUALIFIER_FAILURE_FILE = 'no-cutoff-recovery-qualification-failure.json'
IMAGE_INTENT_FILE = 'no-cutoff-recovery-image-build.json'
IMAGE_RESULT_FILE = 'no-cutoff-recovery-images.json'
IMAGE_EVIDENCE_FILES = frozenset('.runtime/stage2/' + name
    for name in (IMAGE_INTENT_FILE, IMAGE_RESULT_FILE))
INPUT_FILES = (POLICY_FILE, PLAN_FILE, MANIFEST_FILE, ORIGINAL_FILE,
    PREDECESSOR_FILE, QUALIFICATION_FILE, REGISTRATION_FILE)
POLICY = dict(schema_version=1, experiment=EXPERIMENT,
    authority='explicit-user-one-separate-recovery-for-original-setup-only-63-65',
    condition=CONDITION, parent='C0', base_parent=None, stage='final', intended=3,
    plan_sha256=PLAN_SHA256, accounting_mode='provider-credit-only',
    project_cap_usd=None, stage_cap_usd=None, per_task_cap_usd=None, reserve_usd='0',
    model_call_cap=None, physical_request_count_cap=None, retry_count_cap=None,
    provider_max_price=None, accounting_blocks_dispatch=False, unknown_cost_is_zero=False,
    automatic_top_up=False, automatic_purchase=False, automatic_credit_limit_increase=False,
    attempts_per_task=1, parallel_trials=1, automatic_task_replay=False,
    model=SETTINGS.document(), task_time_and_resources='official-unchanged',
    execution_contract=execution_contract(), candidate_version=CANDIDATE_VERSION,
    preparation_source_sha256=PREPARATION_SHA256, preparation_command_sha256=COMMAND_SHA256,
    setup_timeout_seconds=900, package_command_timeout_seconds=180,
    preparation_command_retries=0, speculative_infrastructure_repair=False,
    physical_request_retry='undelivered-transient-only-within-task-deadline',
    shared_provider_cooldown=True, provider_credit_auth_and_identity_checks=True,
    original_results_replaced=False, recovery_merged_into_original89=False,
    best_of_selection=False, success_guaranteed=False,
    original_full89_denominator=89, separate_recovery_denominator=3)
# This is a prospective component inventory, not a retroactive qualification.
# Add the real host/service/producer sources before their future native freeze.
REQUIRED_SOURCE_FILES = frozenset({
    'protocols/custom_setup_recovery_handoff_order_20260930.md',
    'protocols/custom_setup_recovery_regression_20260930.md',
    'no_cutoff_recovery_plan.py', 'test_no_cutoff_recovery_plan.py',
    'protocols/custom_setup_recovery_20260929.md', 'matched_repeat_schedule.py',
    'no_cutoff_recovery_setup.py', 'test_no_cutoff_recovery_setup.py',
    'protocols/custom_setup_recovery_instrumentation_20260929.md',
    'no_cutoff_recovery_policy.py', 'no_cutoff_recovery_gateway.py',
    'test_no_cutoff_recovery_policy.py', 'protocols/custom_setup_recovery_gateway_20260929.md',
    # Unchanged helper imports bound for current verification only.
    'calibrate_tokenizer.py', 'extended_token_calibration.py', 'setup_probe.py',
    'cetus_local_probe.py', 'custom_agent_probe.py', 'direct_final_gateway.py',
    'final_schedule.py', 'freeze_inputs.py', 'local_langfuse.py',
    # Historical module names are retained, but these previously unlisted
    # test bytes are bound now, not retroactively added to original proof.
    'custom_backend_tests.py', 'custom_jobs_tests.py', 'custom_runner_tests.py',
    'test_scored_trial.py', 'test_trial_execution.py',
    # Current recovery consumers plus unchanged archived reporter dependencies.
    'no_cutoff_recovery_predecessor.py',
    'no_cutoff_recovery_handoff.py',
    'test_no_cutoff_recovery_handoff.py',
    'protocols/custom_setup_recovery_handoff_20260929.md',
    'no_cutoff_recovery_runtime.py', 'no_cutoff_recovery_libraries.py',
    'test_no_cutoff_recovery_runtime.py',
    'protocols/custom_setup_recovery_runtime_20260929.md',
    'no_cutoff_recovery_session.py', 'test_no_cutoff_recovery_session.py',
    'protocols/custom_setup_recovery_session_20260929.md',
    'no_cutoff_recovery_bootstrap.py', 'no_cutoff_recovery_connection.py',
    'no_cutoff_recovery_service.py', 'test_no_cutoff_recovery_connection.py',
    'protocols/custom_setup_recovery_connection_20260929.md',
    'no_cutoff_recovery_files.py', 'no_cutoff_recovery_result.py',
    'no_cutoff_recovery_images.py', 'fixtures/Dockerfile.no-cutoff-recovery',
    'no_cutoff_recovery_qualification.py', 'no_cutoff_recovery_study.py',
    'no_cutoff_recovery_fixture.py', 'no_cutoff_recovery_probe.py',
    'qualify_no_cutoff_recovery.py', 'run_no_cutoff_recovery.py',
    'test_no_cutoff_recovery_result.py', 'test_no_cutoff_recovery_execution.py',
    'test_no_cutoff_recovery_qualification.py', 'test_no_cutoff_recovery_images.py',
    'test_no_cutoff_recovery_service_operations.py', 'test_qualify_no_cutoff_recovery.py',
    'test_no_cutoff_recovery_probe.py',
    'no_cutoff_recovery_install.py', 'test_no_cutoff_recovery_install.py',
    'no_cutoff_recovery_report.py', 'no_cutoff_recovery_archive.py', 'no_cutoff_recovery_reporting.py',
    'test_no_cutoff_recovery_reporting.py',
    'protocols/custom_setup_recovery_execution_20260930.md',
    'no_cutoff_recovery_revision.py', 'test_no_cutoff_recovery_revision.py',
    'protocols/custom_setup_recovery_location_20260930.md',
    'protocols/custom_setup_recovery_image_20260930.md',
    'fixtures/lifecycle/task.toml', 'fixtures/lifecycle/instruction.md',
    'fixtures/lifecycle/environment/Dockerfile', 'fixtures/lifecycle/tests/test.sh',
    # Explicit current installed-image closure; unchanged inherited files.
    'budget_ledger.py', 'collect_deferred_receipts.py', 'completion_wait.py',
    'credit_only_gateway.py', 'credit_only_policy.py', 'custom_control.py',
    'deferred_billing.py', 'deadline_custom_contract.py', 'gateway_core.py', 'gateway_http.py',
    'gateway_policy.py', 'historical_hold.py', 'no_cutoff_custom_contract.py',
    'model_protocol.py', 'openrouter_transport.py', 'portable_custom_policy.py',
    'rate_limit_candidate.py', 'receipt_accounting.py', 'receipt_polling.py',
    'rerun_budget.py', 'retry_gateway.py', 'retry_policy.py', 'retry_runtime.py',
    'retry_transport.py', 'scored_gateway.py', 'study_budget.py', 'trial_estimator.py',
    'progress_dashboard.py',  # Unchanged pinned SSH helper, current binding.
    'matched_repeat_stream.py',
    'no_cutoff_final_report.py',
    'test_no_cutoff_final_report.py',
    'no_cutoff_final_guard.py',
    'test_no_cutoff_final_guard.py',
    'no_cutoff_final_dependencies.py',
    'test_no_cutoff_final_dependencies.py',
    'no_cutoff_final_transport.py',
    'test_no_cutoff_final_transport.py',
    'no_cutoff_final_inventory_audit.py',
    'test_no_cutoff_final_inventory_audit.py',
    'no_cutoff_final_environment_audit.py',
    'test_no_cutoff_final_environment_audit.py',
    'test_no_cutoff_final_environment.py',
    'protocols/custom_final_reporting_environment_20260929.md',
    'no_cutoff_final_archive_logs.py',
    'test_no_cutoff_final_archive_logs.py',
    'protocols/custom_final_archive_logs_20260929.md',
    'protocols/custom_final_reporting_inventory_20260929.md',
    'no_cutoff_final_backup.py',
    'test_no_cutoff_final_backup.py',
    'no_cutoff_final_backup_operator.py',
    'test_no_cutoff_final_backup_operator.py',
    'no_cutoff_final_export.py',
    'test_no_cutoff_final_export.py',
    'matched_repeat_amended_predecessor.py',
    'test_matched_repeat_amended_predecessor.py',
    'matched_repeat_amended_handoff.py',
    'test_matched_repeat_amended_handoff.py',
    'no_cutoff_final_reporting.py',
    'test_no_cutoff_final_reporting.py',
    'no_cutoff_final_archive.py',
    'test_no_cutoff_final_archive.py',
    'no_cutoff_final_phase_audit.py',
    'test_no_cutoff_final_phase_audit.py',
    'protocols/custom_final_phase_reporting_20260928.md',
})
ORCHESTRATION_FILES = frozenset({'scored_trial.py'})
RECOVERY_TEST_MODULES = ('test_no_cutoff_recovery_plan',
    'test_no_cutoff_recovery_setup', 'test_no_cutoff_recovery_policy',
    'test_no_cutoff_recovery_handoff', 'test_no_cutoff_recovery_runtime',
    'test_no_cutoff_recovery_session', 'test_no_cutoff_recovery_connection',
    'test_no_cutoff_recovery_result', 'test_no_cutoff_recovery_execution',
    'test_no_cutoff_recovery_qualification', 'test_no_cutoff_recovery_images',
    'test_no_cutoff_recovery_service_operations', 'test_qualify_no_cutoff_recovery',
    'test_no_cutoff_recovery_probe', 'test_no_cutoff_recovery_install', 'test_no_cutoff_recovery_reporting',
    'test_no_cutoff_recovery_revision')
PROBE_MODES = ('tools', 'prepare_not_applicable', 'prepare_nonzero',
    'prepare_exception', 'cancel_setup', 'boundary_stop')
PREPARATION_OUTCOMES = dict(tools='refreshed', prepare_not_applicable='not_applicable',
    prepare_nonzero='preparation_command_nonzero', prepare_exception='command_execution_exception',
    cancel_setup='preparation_cancelled', boundary_stop='refreshed')


def _same(value, expected):
    try:
        equal = fingerprint(value) == fingerprint(expected)
    except (TypeError, ValueError, OverflowError):
        equal = False
    if not equal:
        raise ValueError('Exact recovery metadata required')


def _hash(value):
    if type(value) is not str or not re.fullmatch('[a-f0-9]{64}', value):
        raise ValueError('Exact recovery SHA256 required')


def _bindings(value, *, private=False):
    if type(value) is not dict or not value:
        raise ValueError('Nonempty exact recovery file bindings required')
    for name, digest in value.items():
        if type(name) is not str:
            raise ValueError('Bound path must be a string')
        relative = name.removeprefix('.runtime/stage2/') if private else name
        path = PurePosixPath(relative)
        if (private and relative == name or path.is_absolute() or '..' in path.parts
                or str(path) != relative or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*', relative)):
            raise ValueError('Normalised recovery file binding required')
        _hash(digest)


def cells(manifest):
    schedule = plan.schedule(manifest)
    _same(fingerprint(schedule), PLAN_SHA256)
    return schedule['cells']


def original_final(final):
    if type(final) is not dict:
        raise ValueError('Original final qualification metadata required')
    _same(fingerprint(final), ORIGINAL_QUALIFICATION)
    sources = final.get('sources')
    _bindings(sources)
    _same(fingerprint(sources), ORIGINAL_SOURCE_SET)
    expected = dict(experiment=plan.ORIGINAL_EXPERIMENT, condition=CONDITION,
        parent='C0', base_parent=None, candidate_version=CANDIDATE_VERSION,
        candidate_sha256=ORIGINAL_CANDIDATE, sources_sha256=ORIGINAL_SOURCE_SET,
        model_protocol_sha256=MODEL_SHA256, execution_contract=execution_contract())
    for key, value in expected.items():
        _same(final.get(key), value)
    _same(sources.get('task_preparation.py'), PREPARATION_SHA256)
    return sources


def test_modules(final):
    original_final(final)
    modules = final.get('offline', {}).get('modules')
    if (type(modules) is not list or not modules or len(set(modules)) != len(modules)
            or any(type(n) is not str or not re.fullmatch('[a-z_][a-z0-9_]*', n) for n in modules)):
        raise ValueError('Original regression module bindings required')
    return tuple(dict.fromkeys((*modules, *RECOVERY_TEST_MODULES)))


def source_transition(final, current):
    inherited = original_final(final)
    _bindings(current)
    if set(current) != set(inherited) | REQUIRED_SOURCE_FILES:
        raise ValueError('Exact original and prospective recovery source inventory required')
    if not {name + '.py' for name in test_modules(final)}.issubset(current):
        raise ValueError('All recovery regression modules must be bound')
    changed = {name for name, digest in inherited.items() if current[name] != digest}
    if not changed.issubset(ORCHESTRATION_FILES):
        raise ValueError('Original agent, prompt, tools, model, preparation or evidence source changed')
    return {name: dict(original_sha256=inherited[name], recovery_sha256=current[name])
        for name in sorted(changed)}


def validate_predecessor(value, manifest):
    """Exact retained original bindings, not proof of fresh audit/archive reads."""
    cells(manifest)
    fixed = dict(kind='recovery_original_final_evidence_not_admission', schema_version=1,
        successor_experiment=EXPERIMENT, plan_sha256=PLAN_SHA256,
        original_experiment=plan.ORIGINAL_EXPERIMENT, harness=CONDITION,
        qualification_sha256=ORIGINAL_QUALIFICATION,
        registration_sha256=plan.ORIGINAL_REGISTRATION, sources_sha256=ORIGINAL_SOURCE_SET,
        retained_snapshot_sha256=SNAPSHOT_SHA256, audit_sha256=AUDIT_SHA256, archive_sha256=ARCHIVE_SHA256,
        backup_record_sha256=BACKUP_SHA256, reporter_commit=REPORTER_COMMIT,
        public_files=PUBLIC_FILES, paid_launch_ready=False)
    if type(value) is not dict or set(value) != set(fixed) | {'results_sha256'}:
        raise ValueError('Exact original evidence metadata required, not a saved diagnosis')
    for key, expected in fixed.items():
        _same(value[key], expected)
    results = value['results_sha256']; _bindings(results)
    expected_ids = {plan.original_id(index, task)
        for index, task in enumerate(plan.task_order(manifest), 1)}
    if set(results) != expected_ids or fingerprint(results) != ORIGINAL_RESULTS_SHA256:
        raise ValueError('All 89 original outcome hashes must remain unchanged')
    for ordinal, task, digest in plan.TARGETS:
        _same(results[plan.original_id(ordinal, task)], digest)
    return deepcopy(value)


def probe_checks(mode):
    if mode not in PROBE_MODES:
        raise ValueError('Unknown recovery qualification case')
    checks = {'expected_status', 'expected_verifier_result', 'model_revoked',
        'all_physical_requests_accounted', 'unknown_costs_retained', 'traces_recorded',
        'containers_removed', 'networks_removed', 'volumes_removed', 'sources_unchanged',
        'host_unchanged', 'images_unchanged', 'fixture_resources_audited',
        'recovery_gateway_identity', 'final_stage_accounting', 'original_C0_NC_controls',
        'preparation_callback_once', 'original_preparation_command',
        'preparation_observation_retained', 'preparation_outcome_corroborated', 'no_raw_diagnostics'}
    if mode in {'tools', 'boundary_stop'}:
        checks |= {'actual_native_graph_tool_roundtrip', 'recovered_one_transient'}
    if mode in {'prepare_nonzero', 'prepare_exception', 'cancel_setup'}:
        checks |= {'no_model_request', 'agent_and_verifier_not_run'}
    if mode == 'cancel_setup':
        checks.add('cancelled_setup_evidence')
    if mode == 'boundary_stop':
        checks |= {'cooperative_stop_persisted', 'no_next_dispatch'}
    return checks


def validate_qualification(final, predecessor, manifest, proof):
    """Only structural validation. Actual producer/image reads belong to host."""
    validate_predecessor(predecessor, manifest)
    if type(proof) is not dict:
        raise ValueError('Separate recovery qualification metadata required')
    transition = source_transition(final, proof.get('sources'))
    fixed = dict(schema_version=1, kind='native_separate_C0_NC_recovery_qualification',
        experiment=EXPERIMENT, status='passed', condition=CONDITION, parent='C0', base_parent=None,
        live_api_calls=0, paid_launch_ready=False, setup_timeout_seconds=900,
        package_command_timeout_seconds=180, preparation_source_sha256=PREPARATION_SHA256,
        preparation_command_sha256=COMMAND_SHA256, plan_sha256=PLAN_SHA256,
        policy_sha256=fingerprint(POLICY), original_qualification_sha256=ORIGINAL_QUALIFICATION,
        original_candidate_sha256=ORIGINAL_CANDIDATE, candidate_version=CANDIDATE_VERSION,
        predecessor_authentication_sha256=fingerprint(predecessor),
        model_protocol_sha256=MODEL_SHA256, manifest_canonical_sha256=MANIFEST_SHA256,
        input_manifest_sha256=INPUT_SHA256, python_runtime_sha256=PYTHON_SHA256,
        execution_contract=execution_contract(), dependencies=final['dependencies'],
        python_runtime=final['python_runtime'], host_environment=final['host_environment'],
        guard_image=final['guard_image'], sources_sha256=fingerprint(proof['sources']),
        orchestration_changes=transition, image_sources_match=True)
    dynamic = {'sources', 'runtime_identity_sha256', 'image_build_sha256', 'image_evidence_files',
        'gateway_image', 'offline', 'regression_path', 'synthetic', 'evidence_files'}
    if set(proof) != set(fixed) | dynamic:
        raise ValueError('Exact allowlisted recovery qualification fields required')
    for key, expected in fixed.items():
        _same(proof[key], expected)
    for key in ('runtime_identity_sha256', 'image_build_sha256'):
        _hash(proof[key])
    for key in ('gateway_image', 'guard_image'):
        if type(proof[key]) is not str or not re.fullmatch('sha256:[a-f0-9]{64}', proof[key]):
            raise ValueError('Immutable recovery image IDs required')
    _bindings(proof['image_evidence_files'], private=True)
    if set(proof['image_evidence_files']) != IMAGE_EVIDENCE_FILES:
        raise ValueError('Both real image build producer files must be bound')
    if (final['host_environment'].get('execution_mode') != 'native_linux_x86_64'
            or final['python_runtime'].get('sha256') != PYTHON_SHA256):
        raise ValueError('Keep the actual native host and original Python runtime')
    offline = proof['offline']
    if (type(offline) is not dict or set(offline) != {'modules', 'passed', 'tests', 'skipped', 'errors', 'failures'}
            or offline['modules'] != list(test_modules(final)) or offline['passed'] is not True
            or type(offline['tests']) is not int or offline['tests'] <= 0
            or any(type(offline[k]) is not int or offline[k] != 0 for k in ('skipped', 'errors', 'failures'))):
        raise ValueError('Complete real native recovery regressions required')
    regression = proof['regression_path']
    if type(regression) is not str or not re.fullmatch(
            r'\.runtime/stage2/native-no-cutoff-recovery-qualification-[a-zA-Z0-9_]+', regression):
        raise ValueError('Separate recovery regression output path required')
    files = {regression + '/regression.json', regression + '/regression.txt'}
    cases = proof['synthetic']
    if (type(cases) is not list or any(type(c) is not dict for c in cases)
            or [c.get('mode') for c in cases] != list(PROBE_MODES)):
        raise ValueError('All six actual recovery preparation/lifecycle cases required')
    for case in cases:
        mode = case['mode']
        expected = dict(mode=mode, condition=CONDITION, status='passed', live_api_calls=0,
            kind='actual_native_recovery_synthetic_provider_not_benchmark_score',
            preparation_outcome=PREPARATION_OUTCOMES[mode],
            checks=dict.fromkeys(sorted(probe_checks(mode)), True))
        if set(case) != set(expected) | {'runtime_path', 'preparation_observation_sha256'}:
            raise ValueError('Exact recovery lifecycle metadata required')
        for key, value in expected.items():
            _same(case[key], value)
        _hash(case['preparation_observation_sha256'])
        path = case['runtime_path']
        if type(path) is not str or not re.fullmatch(
                r'\.runtime/stage2/native-no-cutoff-recovery-' + mode + r'-[a-zA-Z0-9_]+', path):
            raise ValueError('Separate recovery lifecycle producer path required')
        files |= {path + '/evidence.json', path + '/.runtime/stage2/scored-trials/'
            + 'synthetic-nc-recovery-' + mode + '/result.json'}
    _bindings(proof['evidence_files'], private=True)
    if set(proof['evidence_files']) != files:
        raise ValueError('All fourteen regression and lifecycle producer files must be bound')
    return deepcopy(proof)


def registration(final, predecessor, manifest, proof):
    validate_qualification(final, predecessor, manifest, proof)
    return dict(schema_version=1, kind='registered_separate_C0_NC_recovery3',
        experiment=EXPERIMENT, condition=CONDITION, parent='C0', base_parent=None,
        stage='final', phase='separate-setup-recovery', intended=3, attempts_per_task=1,
        parallel_trials=1, automatic_task_replay=False, original_results_replaced=False,
        recovery_merged_into_original89=False, original_full89_denominator=89,
        separate_recovery_denominator=3, best_of_selection=False, success_guaranteed=False,
        plan_sha256=PLAN_SHA256, policy_sha256=fingerprint(POLICY),
        qualification_sha256=fingerprint(proof), original_qualification_sha256=ORIGINAL_QUALIFICATION,
        original_candidate_sha256=ORIGINAL_CANDIDATE, candidate_version=CANDIDATE_VERSION,
        predecessor_authentication_sha256=fingerprint(predecessor),
        runtime_identity_sha256=proof['runtime_identity_sha256'],
        image_build_sha256=proof['image_build_sha256'], sources_sha256=proof['sources_sha256'],
        orchestration_changes=deepcopy(proof['orchestration_changes']),
        model_protocol_sha256=MODEL_SHA256, manifest_canonical_sha256=MANIFEST_SHA256,
        execution_contract=execution_contract(), cells=cells(manifest), paid_launch_ready=False)


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid,
        info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _directory(info):
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise ValueError('Owned private recovery runtime required')
    # Unrelated legitimate accounting files change directory size/times.
    return (info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid)


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('Duplicate recovery JSON field')
        value[key] = item
    return value


def _constant(value):
    raise ValueError('Nonfinite recovery JSON refused')


def _capture(runtime):
    """Read only the seven fixed private inputs, with descriptor/identity checks."""
    runtime = Path(runtime)
    if not runtime.is_absolute() or runtime != runtime.resolve() or runtime.parts[-2:] != ('.runtime', 'stage2'):
        raise ValueError('Canonical recovery runtime path required')
    fd = os.open(runtime, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        directory = _directory(os.fstat(fd))
        values, bindings = {}, {}
        for name in INPUT_FILES:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
            with os.fdopen(descriptor, 'rb') as stream:
                before = os.fstat(stream.fileno())
                if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.geteuid()
                        or before.st_nlink != 1 or stat.S_IMODE(before.st_mode) != 0o600):
                    raise ValueError('Owned private single-link recovery input required')
                raw = stream.read()
                if (_identity(before) != _identity(os.fstat(stream.fileno())) or
                        _identity(before) != _identity(os.stat(name, dir_fd=fd, follow_symlinks=False))):
                    raise ValueError('Recovery input changed during read')
            digest = hashlib.sha256(raw).hexdigest()
            pinned = {ORIGINAL_FILE: ORIGINAL_QUALIFICATION_FILE_SHA256, MANIFEST_FILE: INPUT_SHA256}
            if name in pinned and digest != pinned[name]:
                raise ValueError('Exact original private copy bytes required')
            value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs, parse_constant=_constant)
            if type(value) is not dict:
                raise ValueError('Recovery input must be a JSON object')
            values[name] = value
            bindings[name] = dict(sha256=digest, identity=_identity(before))
        if (directory != _directory(os.fstat(fd)) or directory != _directory(runtime.lstat())
                or runtime != runtime.resolve()):
            raise ValueError('Recovery runtime changed during read')
        return values, dict(directory=directory, files=bindings)
    finally:
        os.close(fd)


def read_block(runtime):
    """Return structurally checked metadata and byte identities, not host scope."""
    try:
        values, binding = _capture(runtime)
        _same(values[POLICY_FILE], POLICY)
        manifest = values[MANIFEST_FILE]
        plan.validate_schedule(values[PLAN_FILE], manifest)
        expected = registration(values[ORIGINAL_FILE], values[PREDECESSOR_FILE], manifest,
            values[QUALIFICATION_FILE])
        _same(values[REGISTRATION_FILE], expected)
        _, final_binding = _capture(runtime)
        if final_binding != binding:
            raise ValueError('Recovery inputs changed across validation')
        return expected, binding
    except (OSError, UnicodeError, KeyError, TypeError, OverflowError, RecursionError, ValueError):
        raise ValueError('Recovery gateway inputs refused; inspect retained state without replay') from None


def require_block(runtime):
    return read_block(runtime)[0]


def read_trial(runtime, trial_id, stage):
    if stage != 'final' or type(trial_id) is not str or trial_id not in {
            f'customrecovery1-c0-nc-{ordinal:02d}-{task}' for ordinal, task, _ in plan.TARGETS}:
        raise ValueError('Only the three fixed fresh recovery identities are supported')
    return read_block(runtime)


def require_trial(runtime, trial_id, stage):
    return read_trial(runtime, trial_id, stage)[0]

"""Fixed, separately authorised three-task recovery plan, never admission.

The original missing outcomes are retained. This pure plan grants no native
scope, qualification, registration, task replay or provider access.
"""
from matched_repeat_schedule import (MANIFEST_SHA256, MODEL_SHA256, SETTINGS,
    fingerprint, schedule as baseline_schedule, task_order)

EXPERIMENT = 'custom-no-cutoff-recovery-20260929'
ROOT = '/opt/uts-capstone-custom-no-cutoff-recovery-20260929'
ORIGINAL_EXPERIMENT = 'custom-no-cutoff-final-20260928'
ORIGINAL_QUALIFICATION = 'b3e05d9c216463b044e3b264aa449cecb92d8b9bd8cbc33b77189e434107087e'
ORIGINAL_REGISTRATION = '17a4139c4f68b2e6d8e5b62db910242e3562662192c13da51e62f53441f764b2'
ORIGINAL_SOURCE_SET = '4f73ab4083b76f555ff3bf695d7fed87ddbf4e5982551473418b8005eaf24d05'
TARGETS = (
    (63, 'schemelike-metacircular-eval', '600f86d41ba1c947a1c5c712ae61bb9d7371b29e1528ffe1a25f78b5c8d695f7'),
    (64, 'pytorch-model-recovery', '4bb373abb6b61ab4789cf944fb602aec90b6ced34fb75b88a588d9f7bb814e9d'),
    (65, 'query-optimize', 'a3dfc7db0cd2292244bfaf64b35760c06845641e33f7ac9c1f55ee85238385ff'))


def original_id(ordinal, task):
    return f'customfinal2-c0-nc-{ordinal:02d}-{task}'


def schedule(manifest):
    """Describe only the explicit three-task recovery; never select by score."""
    ordered = task_order(manifest)
    if SETTINGS.fingerprint() != MODEL_SHA256:
        raise ValueError('Keep the exact original model protocol')
    tasks = {row['task_id']: row for row in manifest['tasks']}
    cells = []
    for ordinal, task, result_hash in TARGETS:
        if ordered[ordinal - 1] != task or tasks[task]['development'] is not False:
            raise ValueError('Exact approved original ordinals and tasks required')
        meta = tasks[task]
        cells.append(dict(trial_id=f'customrecovery1-c0-nc-{ordinal:02d}-{task}',
            task_id=task, harness='C0-NC', stage='final', phase='separate-setup-recovery',
            recovery_attempt=1, original_ordinal=ordinal,
            original_trial_id=original_id(ordinal, task), original_result_sha256=result_hash,
            task_config_sha256=meta['task_config_sha256'],
            official_resources={k: meta[k] for k in ('cpus', 'memory_mb', 'storage_mb', 'gpus')},
            original_outcome='setup_only_missing_verifier', original_reward=None))
    baseline = baseline_schedule(manifest)
    old_ids = {original_id(i, task) for i, task in enumerate(ordered, 1)}
    baseline_ids = {cell['trial_id'] for block in baseline['blocks'] for cell in block['cells']}
    ids = {cell['trial_id'] for cell in cells}
    if len(ids) != 3 or ids & (old_ids | baseline_ids) or any(len(name) > 120 for name in ids):
        raise ValueError('Three fresh nonoverlapping recovery identities required')
    return dict(kind='separate_custom_setup_recovery_plan_not_admission', schema_version=1,
        experiment=EXPERIMENT, proposed_native_root=ROOT,
        original_experiment=ORIGINAL_EXPERIMENT, manifest_sha256=MANIFEST_SHA256,
        original_qualification_sha256=ORIGINAL_QUALIFICATION,
        original_registration_sha256=ORIGINAL_REGISTRATION,
        original_sources_sha256=ORIGINAL_SOURCE_SET,
        model_protocol=SETTINGS.document(), model_protocol_sha256=MODEL_SHA256,
        intended=3, cells=cells, attempts_per_registered_cell=1, parallel_trials=1,
        scope_basis='explicit-user-recovery-of-original-setup-only-63-65',
        arbitrary_failed_task_selection=False, automatic_task_replay=False,
        original_results_replaced=False, recovery_merged_into_original89=False,
        best_of_selection=False, success_guaranteed=False,
        original_full89_denominator=89, separate_recovery_denominator=3,
        agent_prompt_tools_model='original-qualified-C0-NC-unchanged',
        setup_preparation='same-original-index-refresh-no-automatic-retry',
        setup_timeout_seconds=900, package_command_timeout_seconds=180,
        task_time_and_resources='official-unchanged',
        setup_diagnostics='source-bound-allowlisted-stage-metadata-no-raw-output',
        lower_level_original_cause='not_retained_not_established',
        accounting=dict(mode='provider-credit-only', project_cap_usd=None, per_task_cap_usd=None,
            reserve_usd='0', model_call_cap=None, physical_request_count_cap=None,
            accounting_blocks_dispatch=False, unknown_cost_is_zero=False,
            shared_provider_cooldown=True, automatic_top_up=False,
            automatic_purchase=False, automatic_credit_limit_increase=False),
        baseline_schedule_sha256=fingerprint(baseline), baseline_schedule_changed=False,
        baseline_order=['terminus-2', 'openhands'],
        requirements=['fresh-original-audit-and-existing-archive-authentication',
            'new-exclusive-root-and-source-bound-recovery-scope',
            'all-ancestor-locks-and-no-active-native-work',
            'real-isolated-native-regressions-and-lifecycle-qualification',
            'exact-new-three-cell-registration-and-no-started-key-reuse',
            'same-official-task-config-images-and-original-C0-NC-controls',
            'completed-recovery-audit-one-private-backup-separate-public-export'],
        recovery_execution_qualified=False, registered=False, paid_launch_ready=False)


def validate_schedule(value, manifest):
    expected = schedule(manifest)
    if not isinstance(value, dict) or fingerprint(value) != fingerprint(expected):
        raise ValueError('Separate approved recovery plan changed')
    return expected

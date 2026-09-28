"""Deterministic agreed repeat order, not registration or execution admission.

This pure builder reads no runtime, outcome, account or provider state. The
future runner still needs authentic completed custom evidence, qualified native
baseline behaviour, exact registration and all no-overlap/no-replay safeguards.
"""
import hashlib
import json

from model_protocol import ModelSettings

EXPERIMENT = 'baseline-matched-repeat-20260928'
MANIFEST_SHA256 = '8bf5271d51eb4306c5fadadf8beee58edd70f595c404223768e39949cca81571'
MODEL_SHA256 = '75718eac81a70390e879743b3c760e942281ac205f577960beec845d50057238'
BASELINE_CSV_SHA256 = '8769a865d19bc81132166d67f85a5fb84725f2cda8f5b2a45f98b1d9993d5429'
HARNESSES = ('terminus-2', 'openhands')
SETTINGS = ModelSettings(384000, 1., 'high')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode()).hexdigest()


def task_order(manifest):
    if not isinstance(manifest, dict) or fingerprint(manifest) != MANIFEST_SHA256:
        raise ValueError('Exact frozen full89 manifest required')
    outside = sorted(manifest['outside_development_ids'], key=lambda task: (
        hashlib.sha256(('uts-stage2-dev20-v1:42:' + task).encode()).hexdigest(), task))
    tasks = list(manifest['development_ids']) + outside
    if (len(tasks) != 89 or len(set(tasks)) != 89 or len(manifest['development_ids']) != 20
            or set(tasks) != set(manifest['all_task_ids'])):
        raise ValueError('Exact development20 and remaining69 coverage required')
    return tasks


def schedule(manifest):
    """One full89 per original baseline, after the custom final89 audit/backup."""
    tasks = task_order(manifest)
    if SETTINGS.fingerprint() != MODEL_SHA256:
        raise ValueError('Original model/provider/sampling must remain unchanged')
    blocks = []
    for index, harness in enumerate(HARNESSES):
        blocks.append(dict(harness=harness, intended=89,
            prerequisite=('custom-final89-audited-and-privately-backed-up' if index == 0
                          else 'matched-terminus-2-repeat89-audited-and-privately-backed-up'),
            cells=[dict(trial_id=f'matchedrepeat1-{harness}-{ordinal:02d}-{task}',
                task_id=task, harness=harness, stage='final',
                phase='matched-baseline-repeat', attempt=1)
                for ordinal, task in enumerate(tasks, 1)]))
    return dict(schema_version=1, kind='matched_baseline_repeat_schedule_not_admission',
        experiment=EXPERIMENT, manifest_sha256=MANIFEST_SHA256,
        model_protocol=SETTINGS.document(), model_protocol_sha256=MODEL_SHA256,
        original_baseline_csv_sha256=BASELINE_CSV_SHA256,
        execution_order=['custom-final89', *HARNESSES], blocks=blocks,
        total_repeat_attempts=178, parallel_trials=1, attempts_per_registered_cell=1,
        automatic_task_replay=False, original_results_replaced=False,
        outcome_dependent_selection=False, primary_comparator='terminus-2',
        secondary_comparator='openhands', original_scores={'terminus-2': 52, 'openhands': 44},
        task_time_and_resources='official-unchanged', baseline_agent_behaviour='original-corrected-unchanged',
        accounting=dict(mode='provider-credit-only', per_task_cap_usd=None, project_cap_usd=None,
            reserve_usd='0', additional_model_call_cap=None, additional_physical_request_count_cap=None,
            retry_count_cap=None, accounting_blocks_dispatch=False, unknown_cost_is_zero=False,
            shared_provider_cooldown=True, automatic_top_up=False),
        # These are existing baseline-agent guards, not new study request caps
        # and not benchmark requirements. Native source authentication remains
        # required; removing them would change the preserved baseline behaviour.
        inherited_baseline_turn_guards={'terminus-2': 1000000, 'openhands': 1000000},
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run',
        requires_completed_custom_audit_and_backup=True, requires_native_source_authentication=True,
        requires_separate_native_qualification=True, requires_exact_registration=True,
        paid_launch_ready=False, full_benchmark_win_claimed=False)


def validate_schedule(value, manifest):
    expected = schedule(manifest)
    if not isinstance(value, dict) or fingerprint(value) != fingerprint(expected):
        raise ValueError('Agreed repeat scope, sequence, accounting or attempt identity changed')
    return expected

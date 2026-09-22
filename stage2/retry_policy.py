"""Explicit, shared protocol for the fresh recovery experiment, not old results."""
from model_protocol import ModelSettings
from retry_runtime import private_read

EXPERIMENT = 'baseline-corrected-credit-only-20260923'
POLICY_FILE = 'corrected-policy.json'
SETTINGS = ModelSettings(384000, 1., 'high')
POLICY = dict(experiment=EXPERIMENT, schema_version=1,
    per_task_cap_usd=None, project_cap_usd=None, reserve_usd='0', provider_max_price=None,
    accounting_blocks_dispatch=False, automatic_top_up=False,
    attempts_per_task=1, parallel_trials=1, model=SETTINGS.document(),
    task_time_and_resources='official-unchanged',
    physical_request_retry='undelivered-transient-only-within-task-deadline',
    retry_count_cap=None, shared_provider_cooldown=True,
    openhands_max_iterations=1000000, terminus_default_max_turns=1000000)


def require_policy(runtime):
    if private_read(runtime / POLICY_FILE) != POLICY:
        raise ValueError('Corrected experiment policy mismatch')

"""26 September custom authority, separate from all baseline financial policies.

No balance, price, ledger, receipt, reserve or model-call allowance is read.
An exact private registered development cell is still required; financial
freedom does not authorize task replay, a different model or held-out tuning.
"""
import hashlib
import json
from pathlib import Path
import re

from custom_control import Condition
from retry_policy import SETTINGS
from retry_runtime import private_read

EXPERIMENT = 'custom-portable-development-20260926'
CANDIDATE_VERSION = 'stage2-candidate-0.3.0'
PYTHON_SHA256 = '7226bdfba69e2fda71033da1d47661b3fc5844e06c1361976d920cde7b64164e'
POLICY_FILE = 'portable-credit-policy.json'
QUALIFICATION = 'portable-qualification.json'
BLOCKS = 'portable-development-blocks'
DEVELOPMENT_SHA256 = 'e81af63f33e27624c48fc38594d8a41ae9ddfadea374f69fa5754cd8ca92483e'
INPUT_SHA256 = 'a33de38d1794617b2acc7c50b1f997da49c34b7df5032b481f023184e4aacbc7'
POLICY = dict(schema_version=2, experiment=EXPERIMENT, candidate_version=CANDIDATE_VERSION,
    python_runtime_sha256=PYTHON_SHA256, predecessor='custom-corrected-development-20260926',
    predecessor_results='retained-separately-not-replaced-or-best-of', authorised_date='2026-09-26',
    authority='explicit-user-custom-no-spend-reserve-or-api-call-cap',
    accounting_mode='provider-credit-only', per_task_cap_usd=None,
    stage_cap_usd=None, project_cap_usd=None, reserve_usd='0', provider_max_price=None,
    model_call_cap=None, physical_request_count_cap=None, accounting_blocks_dispatch=False,
    automatic_top_up=False, automatic_purchase=False, automatic_credit_limit_increase=False,
    automatic_task_replay=False, attempts_per_task_per_variant=1, parallel_trials=1,
    model=SETTINGS.document(), task_time_and_resources='official-unchanged',
    physical_request_retry='undelivered-transient-only-within-task-deadline',
    shared_provider_cooldown=True, primary_comparator='terminus-2',
    secondary_comparator='openhands', development_tasks=20,
    provider_credit_auth_and_identity_checks=True)


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
        allow_nan=False).encode()).hexdigest()


def require_policy(runtime):
    value = private_read(Path(runtime) / POLICY_FILE)
    # Canonical equality also rejects bool-as-int substitutions.
    if fingerprint(value) != fingerprint(POLICY):
        raise ValueError('Explicit uncapped custom credit policy required')
    return value


def cells(development, condition, parent=None):
    Condition(condition, parent)
    if (not isinstance(development, list) or len(development) != 20
            or fingerprint(development) != DEVELOPMENT_SHA256):
        raise ValueError('Original fixed development split and order required')
    return [dict(trial_id=f'customdev2-{condition.lower()}-{i:02d}-{task}',
        task_id=task, harness=condition) for i, task in enumerate(development, 1)]


def block_path(runtime, condition):
    if condition not in {'C0', 'C1', 'C2'}:
        raise ValueError('Unknown custom condition')
    return Path(runtime) / BLOCKS / (condition + '.json')


def require_block(runtime, condition):
    require_policy(runtime)
    if (Path(runtime) / BLOCKS).is_symlink():
        raise ValueError('Unsafe registration directory')
    value = private_read(block_path(runtime, condition))
    if (value.get('experiment') != EXPERIMENT or value.get('stage') != 'development'
            or value.get('candidate_version') != CANDIDATE_VERSION
            or value.get('python_runtime_sha256') != PYTHON_SHA256
            or value.get('condition') != condition or value.get('policy_sha256') != fingerprint(POLICY)
            or value.get('model_protocol_sha256') != SETTINGS.fingerprint()
            or value.get('input_manifest_sha256') != INPUT_SHA256
            or value.get('primary_comparator') != POLICY['primary_comparator']
            or value.get('secondary_comparator') != POLICY['secondary_comparator']):
        raise ValueError('Custom development registration mismatch')
    expected = cells(value.get('development_ids'), condition, value.get('parent'))
    if value.get('cells') != expected:
        raise ValueError('Exactly one registered attempt per fixed development task required')
    for name in ('qualification_sha256', 'sources_sha256'):
        if not isinstance(value.get(name), str) or not re.fullmatch('[a-f0-9]{64}', value[name]):
            raise ValueError('Qualified source binding required')
    return value


def require_trial(runtime, trial_id, stage):
    if stage != 'development' or not isinstance(trial_id, str):
        raise ValueError('Only registered custom development is supported')
    match = re.fullmatch(r'customdev2-(c[012])-\d{2}-[a-z0-9][a-z0-9_.-]*', trial_id)
    if match is None or len(trial_id) > 120:
        raise ValueError('Invalid registered custom trial')
    block = require_block(runtime, match[1].upper())
    if not any(cell['trial_id'] == trial_id for cell in block['cells']):
        raise ValueError('Unregistered custom cell')
    proof = private_read(Path(runtime) / QUALIFICATION)
    if fingerprint(proof) != block['qualification_sha256']:
        raise ValueError('Custom qualification changed after registration')
    if (proof.get('sources_sha256') != block['sources_sha256']
            or proof.get('candidate_version') != CANDIDATE_VERSION
            or proof.get('python_runtime', {}).get('sha256') != PYTHON_SHA256
            or proof.get('status') != 'passed' or proof.get('experiment') != EXPERIMENT
            or proof.get('policy_sha256') != fingerprint(POLICY)
            or proof.get('model_protocol_sha256') != SETTINGS.fingerprint()):
        raise ValueError('Custom qualification and registration differ')
    return block

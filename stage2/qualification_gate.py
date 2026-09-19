"""Pure paid-expansion gate for the first 20 Terminus development trials.

No calls, task replacements, resampling, allowances or model selection occur here.
"""
from decimal import Decimal, InvalidOperation
from study_budget import TRIAL_CAP


def evaluate(records, *, task_ids, protocol_sha256, systemic_review_clear=False):
    if len(task_ids) != 20 or len(set(task_ids)) != 20:
        raise ValueError('Exactly the frozen 20 unique development tasks required')
    if not isinstance(protocol_sha256, str) or len(protocol_sha256) != 64:
        raise ValueError('Frozen protocol fingerprint required')
    if type(systemic_review_clear) is not bool:
        raise ValueError('Explicit systemic failure review status required')
    reasons, observed, passes, stops = [], set(), 0, 0
    if len(records) != 20:
        reasons.append('incomplete_or_extra_trials')
    for row in records:
        task = row.get('task_id')
        expected_unique = task in task_ids and task not in observed
        if not expected_unique:
            reasons.append('unexpected_or_duplicate_task')
        observed.add(task)
        if row.get('harness') != 'terminus-2' or row.get('stage') != 'development':
            reasons.append('wrong_condition')
        if row.get('model_protocol_sha256') != protocol_sha256:
            reasons.append('model_protocol_mismatch')
        if row.get('status') != 'verified' or row.get('model_revoked') is not True:
            reasons.append('trial_not_verified')
        if not all(row.get(key) is True for key in ['containers_removed', 'networks_removed', 'volumes_removed']):
            reasons.append('cleanup_unverified')
        reward = (row.get('verifier_result') or {}).get('rewards', {}).get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1):
            reasons.append('invalid_verifier_reward')
        elif expected_unique and row.get('status') == 'verified' and row.get('harness') == 'terminus-2' and row.get('stage') == 'development':
            passes += int(reward)
        billing = row.get('billing') or {}
        if billing.get('billing_verified') is not True or billing.get('model_protocol_sha256') != protocol_sha256:
            reasons.append('billing_unverified')
        count = billing.get('budget_stop_count')
        if type(count) is not int or count < 0:
            reasons.append('budget_stop_status_unknown')
        else:
            stops += int(count > 0)
        for key in ['prompt_tokens', 'completion_tokens', 'requests']:
            if type(billing.get(key)) is not int or billing[key] < 0:
                reasons.append('usage_missing')
        try:
            cost = Decimal(str(billing['charged_usd']))
            if not cost.is_finite() or not 0 <= cost <= Decimal(TRIAL_CAP):
                reasons.append('invalid_trial_charge')
        except (KeyError, InvalidOperation, ValueError):
            reasons.append('invalid_trial_charge')
    if observed != set(task_ids): reasons.append('frozen_tasks_missing')
    if passes < 10: reasons.append('fewer_than_ten_successes')
    if stops > 2: reasons.append('more_than_two_budget_stops')
    if not systemic_review_clear: reasons.append('systemic_failure_review_required')
    return {'paid_expansion_allowed': not reasons, 'verified_successes': passes,
            'budget_exhausted_trials': stops, 'reasons': sorted(set(reasons)),
            'expected_trials': 20, 'observed_trials': len(records)}

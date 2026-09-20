"""Read-only paid-expansion gate for the first 20 Terminus development trials.

No calls, task replacements, resampling, allowances or model selection occur here.
"""
from decimal import Decimal, InvalidOperation
from matrix_resume import HELD_TERMINAL, validated_held_cell
from study_budget import TRIAL_CAP


def evaluate(records, *, task_ids, protocol_sha256, systemic_review_clear=False, runtime=None):
    if len(task_ids) != 20 or len(set(task_ids)) != 20:
        raise ValueError('Exactly the frozen 20 unique development tasks required')
    if not isinstance(protocol_sha256, str) or len(protocol_sha256) != 64:
        raise ValueError('Frozen protocol fingerprint required')
    if type(systemic_review_clear) is not bool:
        raise ValueError('Explicit systemic failure review status required')
    reasons, amended_reasons, observed, passes, stops = [], [], set(), 0, 0
    holds, raw_stops, pending_barrier_stops = [], 0, 0

    def reject(reason, *, historical_exception=False):
        reasons.append(reason)
        if not historical_exception:
            amended_reasons.append(reason)

    if len(records) != 20:
        reject('incomplete_or_extra_trials')
    for row in records:
        held = None
        if row.get('resume_disposition') == HELD_TERMINAL:
            try:
                held = validated_held_cell(runtime, row, protocol_sha256)
            except (ValueError, OSError, KeyError):
                reject('historical_hold_invalid')
            if held is not None:
                holds.append(held)
        task = row.get('task_id')
        expected_unique = task in task_ids and task not in observed
        if not expected_unique:
            reject('unexpected_or_duplicate_task')
        observed.add(task)
        if row.get('harness') != 'terminus-2' or row.get('stage') != 'development':
            reject('wrong_condition')
        if row.get('model_protocol_sha256') != protocol_sha256:
            reject('model_protocol_mismatch')
        if row.get('status') != 'verified' or row.get('model_revoked') is not True:
            reject('trial_not_verified', historical_exception=held is not None)
        if not all(row.get(key) is True for key in ['containers_removed', 'networks_removed', 'volumes_removed']):
            reject('cleanup_unverified')
        reward = (row.get('verifier_result') or {}).get('rewards', {}).get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1):
            reject('invalid_verifier_reward')
        elif expected_unique and (row.get('status') == 'verified' or held is not None) and row.get('harness') == 'terminus-2' and row.get('stage') == 'development':
            passes += int(reward)
        billing = row.get('billing') or {}
        if billing.get('billing_verified') is not True or billing.get('model_protocol_sha256') != protocol_sha256:
            reject('billing_unverified', historical_exception=held is not None)
        count = billing.get('budget_stop_count')
        if type(count) is not int or count < 0:
            reject('budget_stop_status_unknown')
        else:
            raw_stops += count
            # The two immutable old markers came from the pending-request
            # barrier. Their validated classification is not cap exhaustion.
            if held is not None:
                if (held.get('budget_stop_classification') != 'historical_pending_barrier'
                        or type(held.get('capacity_budget_stop_count')) is not int
                        or held['capacity_budget_stop_count'] != 0):
                    reject('budget_stop_status_unknown')
                else:
                    pending_barrier_stops += count
                    stops += int(held['capacity_budget_stop_count'] > 0)
            else:
                stops += int(count > 0)
        for key in ['prompt_tokens', 'completion_tokens', 'requests']:
            if type(billing.get(key)) is not int or billing[key] < 0:
                reject('usage_missing', historical_exception=held is not None)
        try:
            cost = Decimal(str(billing['charged_usd']))
            if not cost.is_finite() or not 0 <= cost <= Decimal(TRIAL_CAP):
                reject('invalid_trial_charge', historical_exception=held is not None)
        except (KeyError, InvalidOperation, ValueError):
            reject('invalid_trial_charge', historical_exception=held is not None)
    if len(holds) > 1: reject('more_than_one_historical_hold')
    if observed != set(task_ids): reject('frozen_tasks_missing')
    if passes < 10: reject('fewer_than_ten_successes')
    if stops > 2: reject('more_than_two_budget_stops')
    if not systemic_review_clear: reject('systemic_failure_review_required')
    bounded_allowed = len(holds) == 1 and not amended_reasons
    billing_complete = (len(records) == 20 and observed == set(task_ids)
        and not set(reasons).intersection({'billing_unverified', 'usage_missing', 'invalid_trial_charge'}))
    return {'paid_expansion_allowed': not reasons, 'verified_successes': passes,
            'budget_exhausted_trials': stops, 'reasons': sorted(set(reasons)),
            'expected_trials': 20, 'observed_trials': len(records),
            'status': ('original_qualification_passed' if not reasons else
                       'accounting_bounded_expansion_allowed' if bounded_allowed else 'qualification_not_cleared'),
            'model_protocol_sha256': protocol_sha256,
            'original_billing_completeness_satisfied': billing_complete,
            'accounting_bounded_expansion_allowed': bounded_allowed,
            'accounting_bounded_reasons': sorted(set(amended_reasons)),
            'held_terminal_trials': len(holds),
            'historical_hold_sha256': holds[0]['sidecar_sha256'] if len(holds) == 1 else None,
            'budget_stop_markers': raw_stops,
            'historical_pending_barrier_markers': pending_barrier_stops,
            'actual_charge_and_token_totals_complete': billing_complete}

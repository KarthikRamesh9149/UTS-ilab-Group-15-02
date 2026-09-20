"""Read-only paid-expansion gate for the first 20 Terminus development trials.

No calls, task replacements, resampling, allowances or model selection occur here.
"""
from decimal import Decimal, InvalidOperation
from historical_hold import hold_entries, validate_historical_hold
from deferred_billing import validate_policy
from matrix_resume import HELD_TERMINAL, DEFERRED_TERMINAL, validated_held_cell, validated_deferred_cell
from study_budget import TRIAL_CAP


def evaluate(records, *, task_ids, protocol_sha256, systemic_review_clear=False, runtime=None):
    if len(task_ids) != 20 or len(set(task_ids)) != 20:
        raise ValueError('Exactly the frozen 20 unique development tasks required')
    if not isinstance(protocol_sha256, str) or len(protocol_sha256) != 64:
        raise ValueError('Frozen protocol fingerprint required')
    if type(systemic_review_clear) is not bool:
        raise ValueError('Explicit systemic failure review status required')
    reasons, amended_reasons, completion_reasons, observed, passes, stops = [], [], [], set(), 0, 0
    holds, raw_stops, pending_barrier_stops = [], 0, 0
    completion_amendment = None
    deferral_policy, deferrals, continuation_reasons = None, [], []

    def reject(reason, *, historical_exception=False, completion_exception=False, deferral_exception=False):
        reasons.append(reason)
        if not historical_exception:
            amended_reasons.append(reason)
        if not historical_exception and not completion_exception:
            completion_reasons.append(reason)
            if not (deferral_exception and deferral_policy is not None):
                continuation_reasons.append(reason)

    # A caller cannot enable the approved completion amendment with a flag.
    # Its exact private sidecar, immutable results and live ledger must validate.
    if runtime is not None:
        try:
            deferral_policy = validate_policy(runtime)
            if deferral_policy is not None and deferral_policy['model_protocol_sha256'] != protocol_sha256:
                reject('billing_deferral_policy_invalid')
        except (ValueError, OSError, KeyError):
            reject('billing_deferral_policy_invalid')
        try:
            registered = validate_historical_hold(runtime)
            if registered is not None and registered.get('schema_version') == 2:
                if (registered['model_protocol_sha256'] != protocol_sha256
                        or len(hold_entries(registered)) != 2):
                    reject('completion_amendment_invalid')
                else:
                    completion_amendment = registered
        except (ValueError, OSError, KeyError):
            reject('historical_hold_invalid')

    if len(records) != 20:
        reject('incomplete_or_extra_trials')
    for row in records:
        held = None
        deferred = None
        if row.get('resume_disposition') == HELD_TERMINAL:
            try:
                held = validated_held_cell(runtime, row, protocol_sha256)
            except (ValueError, OSError, KeyError):
                reject('historical_hold_invalid')
            if held is not None:
                holds.append(held)
        if row.get('resume_disposition') == DEFERRED_TERMINAL:
            try:
                deferred = validated_deferred_cell(runtime, row, protocol_sha256)
                if deferred is None or deferral_policy is None or deferred['policy_sha256'] != deferral_policy['sidecar_sha256']:
                    reject('billing_deferral_invalid')
                    deferred = None
            except (ValueError, OSError, KeyError):
                reject('billing_deferral_invalid')
            if deferred is not None:
                deferrals.append(deferred)
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
            reject('trial_not_verified', historical_exception=held is not None, deferral_exception=deferred is not None)
        if not all(row.get(key) is True for key in ['containers_removed', 'networks_removed', 'volumes_removed']):
            reject('cleanup_unverified')
        reward = (row.get('verifier_result') or {}).get('rewards', {}).get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1):
            reject('invalid_verifier_reward')
        elif expected_unique and (row.get('status') == 'verified' or held is not None or deferred is not None) and row.get('harness') == 'terminus-2' and row.get('stage') == 'development':
            passes += int(reward)
        billing = row.get('billing') or {}
        if billing.get('billing_verified') is not True or billing.get('model_protocol_sha256') != protocol_sha256:
            reject('billing_unverified', historical_exception=held is not None, deferral_exception=deferred is not None)
        count = billing.get('budget_stop_count')
        if type(count) is not int or count < 0:
            reject('budget_stop_status_unknown')
        else:
            raw_stops += count
            # The two immutable old markers came from the pending-request
            # barrier. Their validated classification is not cap exhaustion.
            if held is not None:
                if (held.get('budget_stop_classification') not in
                        {'historical_pending_barrier', 'no_budget_stop'}
                        or type(held.get('capacity_budget_stop_count')) is not int
                        or held['capacity_budget_stop_count'] != 0
                        or (held.get('budget_stop_classification') == 'no_budget_stop' and count != 0)):
                    reject('budget_stop_status_unknown')
                else:
                    pending_barrier_stops += count
                    stops += int(held['capacity_budget_stop_count'] > 0)
            else:
                stops += int(count > 0)
        for key in ['prompt_tokens', 'completion_tokens', 'requests']:
            if type(billing.get(key)) is not int or billing[key] < 0:
                reject('usage_missing', historical_exception=held is not None, deferral_exception=deferred is not None)
        try:
            cost = Decimal(str(billing['charged_usd']))
            if not cost.is_finite() or not 0 <= cost <= Decimal(TRIAL_CAP):
                reject('invalid_trial_charge', historical_exception=held is not None, deferral_exception=deferred is not None)
        except (KeyError, InvalidOperation, ValueError):
            reject('invalid_trial_charge', historical_exception=held is not None, deferral_exception=deferred is not None)
    registered_ids = ({entry['trial_id'] for entry in hold_entries(completion_amendment)}
                      if completion_amendment else set())
    exact_completion_holds = (completion_amendment is not None and len(holds) == 2
        and {entry['trial_id'] for entry in holds} == registered_ids
        and all(entry['sidecar_sha256'] == completion_amendment['sidecar_sha256'] for entry in holds))
    if len(holds) > 1:
        reject('more_than_one_historical_hold', completion_exception=exact_completion_holds)
    if completion_amendment is not None and not exact_completion_holds:
        reject('completion_amendment_held_cells_missing')
    if observed != set(task_ids): reject('frozen_tasks_missing')
    if passes < 10:
        reject('fewer_than_ten_successes', completion_exception=completion_amendment is not None)
    if stops > 2:
        reject('more_than_two_budget_stops', completion_exception=completion_amendment is not None)
    if not systemic_review_clear: reject('systemic_failure_review_required')
    bounded_allowed = completion_amendment is None and len(holds) == 1 and not amended_reasons
    completion_allowed = exact_completion_holds and not completion_reasons
    continuation_allowed = (deferral_policy is not None and not continuation_reasons
        and (completion_amendment is None or exact_completion_holds))
    billing_complete = (len(records) == 20 and observed == set(task_ids)
        and not set(reasons).intersection({'billing_unverified', 'usage_missing', 'invalid_trial_charge'}))
    return {'paid_expansion_allowed': not reasons, 'verified_successes': passes,
            'budget_exhausted_trials': stops, 'reasons': sorted(set(reasons)),
            'expected_trials': 20, 'observed_trials': len(records),
            'status': ('original_qualification_passed' if not reasons else
                       'billing_deferral_expansion_allowed' if continuation_allowed else
                       'completion_amendment_expansion_allowed' if completion_allowed else
                       'accounting_bounded_expansion_allowed' if bounded_allowed else 'qualification_not_cleared'),
            'model_protocol_sha256': protocol_sha256,
            'original_billing_completeness_satisfied': billing_complete,
            'accounting_bounded_expansion_allowed': bounded_allowed,
            'accounting_bounded_reasons': sorted(set(amended_reasons)),
            'held_terminal_trials': len(holds),
            'historical_hold_sha256': (completion_amendment['sidecar_sha256'] if exact_completion_holds
                                      else holds[0]['sidecar_sha256'] if len(holds) == 1 else None),
            'held_trial_ids': sorted(entry['trial_id'] for entry in holds),
            'original_performance_gate_satisfied': passes >= 10 and stops <= 2,
            'completion_amendment_expansion_allowed': completion_allowed,
            'completion_amendment_sha256': (completion_amendment['sidecar_sha256']
                                            if completion_amendment else None),
            'completion_amendment_reasons': sorted(set(completion_reasons)),
            'budget_stop_markers': raw_stops,
            'historical_pending_barrier_markers': pending_barrier_stops,
            'billing_deferral_expansion_allowed': continuation_allowed,
            'billing_deferral_policy_sha256': deferral_policy['sidecar_sha256'] if deferral_policy else None,
            'billing_deferred_trials': len(deferrals),
            'billing_deferred_trial_ids': sorted(entry['trial_id'] for entry in deferrals),
            'deferred_billing_result_registrations': {entry['trial_id']: entry['sidecar_sha256'] for entry in deferrals},
            'billing_deferral_reasons': sorted(set(continuation_reasons)),
            'actual_charge_and_token_totals_complete': billing_complete}

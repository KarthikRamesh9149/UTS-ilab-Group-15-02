"""Registered development selection; consumes audited metadata, never task text."""
from decimal import Decimal
import math
from matrix_resume import validated_deferred_cell
from study_budget import TRIAL_CAP


def summarize(records, *, condition, task_ids, protocol, parent=None, runtime=None):
    if condition not in {'C0', 'C1', 'C2'}:
        raise ValueError('Unregistered custom condition')
    if (condition == 'C2' and parent not in {'C0', 'C1'}) or (condition != 'C2' and parent is not None):
        raise ValueError('Invalid condition parent')
    if len(task_ids) != 20 or len(set(task_ids)) != 20 or len(records) != 20:
        raise ValueError('Complete fixed development subset required')
    observed, passes, cost, elapsed = set(), 0, Decimal(0), 0.
    deferred_count, retained = 0, 0
    for row in records:
        deferred = validated_deferred_cell(runtime, row, protocol)
        task = row.get('task_id')
        if task not in task_ids or task in observed:
            raise ValueError('Unexpected or duplicate task')
        observed.add(task)
        if (row.get('harness'), row.get('stage'), row.get('model_protocol_sha256')) != (
                condition, 'development', protocol) or (row.get('status') != 'verified' and deferred is None):
            raise ValueError('Condition/protocol/status mismatch')
        if not all(row.get(key) is True for key in ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
            raise ValueError('Unverified trial cleanup')
        if condition == 'C2' and (row.get('agent_context') or {}).get('metadata', {}).get('custom_parent') != parent:
            raise ValueError('C2 parent mismatch')
        reward = (row.get('verifier_result') or {}).get('rewards', {}).get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1):
            raise ValueError('Binary verifier reward required')
        billing = row.get('billing') or {}
        if deferred is None and (billing.get('billing_verified') is not True or billing.get('model_protocol_sha256') != protocol):
            raise ValueError('Reaudited billing required')
        if deferred is None:
            for key in ('prompt_tokens', 'completion_tokens', 'requests'):
                if type(billing.get(key)) is not int or billing[key] < 0:
                    raise ValueError('Complete usage required')
            charge = Decimal(str(billing['charged_usd']))
            if not charge.is_finite() or not 0 <= charge <= Decimal(TRIAL_CAP):
                raise ValueError('Invalid charge')
        else:
            deferred_count += 1
            charge = Decimal(deferred['known_charged_nanodollars']) / 1_000_000_000
            retained += deferred['retained_liability_nanodollars']
        seconds = row.get('phase_seconds', {}).get('agent')
        if type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError('Measured agent runtime required')
        passes += int(reward)
        cost += charge
        elapsed += seconds
    result = {'condition': condition, 'parent': parent, 'passes': passes,
            'charged_usd': str(cost) if not deferred_count else None, 'agent_seconds': elapsed,
            'complexity': int(condition == 'C1' or parent == 'C1') + int(condition == 'C2')}
    if deferred_count:
        result.update(billing_complete=False, billing_deferred_trials=deferred_count,
                      known_billed_subtotal_usd=str(cost),
                      retained_liability_usd=str(Decimal(retained) / 1_000_000_000),
                      efficiency_win_accepted=False)
    return result


def select(blocks, *, task_ids, protocol, c2_parent=None, runtime=None):
    """C0/C1 parent selection, or final C0/C1/C2 selection after parent freeze.

    Caller must re-audit receipts first and persist the chosen parent/finalist
    before subsequent paid work. This pure function does not launch or freeze.
    """
    if set(blocks) not in ({'C0', 'C1'}, {'C0', 'C1', 'C2'}):
        raise ValueError('Complete registered comparison required')
    rows = {condition: summarize(records, condition=condition, task_ids=task_ids,
                                protocol=protocol, parent=c2_parent if condition == 'C2' else None,
                                runtime=runtime)
            for condition, records in blocks.items()}
    complete_costs = all(value['charged_usd'] is not None for value in rows.values())
    parent_complete_costs = all(rows[condition]['charged_usd'] is not None for condition in ('C0', 'C1'))
    def key(condition, *, use_cost=complete_costs):
        value = rows[condition]
        return (-value['passes'], *((Decimal(value['charged_usd']),) if use_cost else ()), value['complexity'],
                value['agent_seconds'], condition)
    # Parent was frozen before C2. Later C2 uncertainty cannot retrospectively
    # alter which C0/C1 parent the registered run was required to use.
    parent = min(('C0', 'C1'), key=lambda condition: key(condition, use_cost=parent_complete_costs))
    if 'C2' in rows and c2_parent != parent:
        raise ValueError('C2 did not use the registered selected parent')
    winner = min(rows, key=key)
    diagnostic = None
    if 'C2' in rows:
        additions = []
        if winner == 'C1' or (winner == 'C2' and parent == 'C1'):
            additions.append((rows['C1']['passes'] - rows['C0']['passes'], 1, 'planning', 'C0'))
        if winner == 'C2':
            additions.append((rows['C2']['passes'] - rows[parent]['passes'], 2, 'completion', parent))
        improving = [addition for addition in additions if addition[0] > 0]
        if improving:
            gain, _, addition, fallback = max(improving)
            # Removing planning from C2 retains completion checking on C0.
            diagnostic = {'kind': 'ablation', 'remove': addition, 'incremental_pass_gain': gain,
                          'condition': 'C2' if winner == 'C2' and addition == 'planning' else fallback,
                          'parent': 'C0' if winner == 'C2' and addition == 'planning' else None}
        else:
            diagnostic = {'kind': 'unchanged_repeat', 'condition': winner,
                          'parent': parent if winner == 'C2' else None}
    result = {'selected': winner, 'selected_parent': parent, 'summaries': rows,
            'diagnostic': diagnostic, 'final_evaluation_success_claimed': False}
    if not complete_costs:
        result.update(cost_tiebreak_used=False, parent_cost_tiebreak_used=parent_complete_costs,
                      selection_billing_complete=False, efficiency_win_accepted=False)
    return result

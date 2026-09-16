"""Pure paired analysis of a complete, externally reaudited final matrix.

No winner is inferred from efficiency or development scores. Statistical
outputs are exploratory and do not certify the full project as complete.
"""
from decimal import Decimal
from math import comb, isfinite
from final_schedule import schedule

ROLES = ('terminus-2', 'openhands', 'custom')


def summarize(rows):
    return {'tasks': len(rows), 'passes': sum(row['reward'] for row in rows),
            'accuracy': sum(row['reward'] for row in rows) / len(rows),
            'charged_usd': str(sum((row['cost'] for row in rows), Decimal(0))),
            'prompt_tokens': sum(row['prompt_tokens'] for row in rows),
            'completion_tokens': sum(row['completion_tokens'] for row in rows),
            'requests': sum(row['requests'] for row in rows),
            'agent_seconds': sum(row['agent_seconds'] for row in rows),
            'budget_stopped_trials': sum(row['budget_stop_count'] > 0 for row in rows)}


def paired(custom, baseline, tasks):
    gains = [task for task in tasks if custom[task]['reward'] > baseline[task]['reward']]
    losses = [task for task in tasks if custom[task]['reward'] < baseline[task]['reward']]
    discordant = len(gains) + len(losses)
    tail = sum(comb(discordant, k) for k in range(min(len(gains), len(losses)) + 1))
    p = min(1., 2 * tail / (2 ** discordant)) if discordant else 1.
    return {'gained_tasks': gains, 'regressed_tasks': losses,
            'net_pass_gain': len(gains) - len(losses),
            'accuracy_difference': (len(gains) - len(losses)) / len(tasks),
            'exact_mcnemar_two_sided_p_exploratory': p,
            'observed_accuracy_lead': len(gains) > len(losses),
            'efficiency_win_accepted': False}


def analyze(records, *, all_tasks, development_tasks, custom_condition, custom_parent, protocol):
    if len(all_tasks) != 89 or len(set(all_tasks)) != 89:
        raise ValueError('Exactly 89 unique final tasks required')
    if len(development_tasks) != 20 or len(set(development_tasks)) != 20 or not set(development_tasks) <= set(all_tasks):
        raise ValueError('Exactly 20 registered development tasks required')
    if custom_condition not in {'C0', 'C1', 'C2'} or (
        custom_condition == 'C2' and custom_parent not in {'C0', 'C1'}) or (
        custom_condition != 'C2' and custom_parent is not None):
        raise ValueError('Frozen custom identity required')
    by_role = {role: {} for role in ROLES}
    expected = {(cell['role'], cell['task_id']): cell['trial_id'] for cell in schedule(
        all_tasks, custom_condition=custom_condition, custom_parent=custom_parent)}
    identities = set()
    for record in records:
        harness, task = record.get('harness'), record.get('task_id')
        role = 'custom' if harness == custom_condition else harness
        if role not in ROLES or task not in all_tasks or task in by_role[role]:
            raise ValueError('Unexpected or duplicate final cell')
        identifier = record.get('trial_id')
        if not isinstance(identifier, str) or identifier != expected[(role, task)] or identifier in identities:
            raise ValueError('Fresh unique final trial identity required')
        identities.add(identifier)
        if record.get('stage') != 'final' or record.get('status') != 'verified' or record.get('model_protocol_sha256') != protocol:
            raise ValueError('Final protocol/status mismatch')
        if not all(record.get(key) is True for key in ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
            raise ValueError('Unverified cleanup')
        if role == 'custom' and custom_condition == 'C2' and (record.get('agent_context') or {}).get('metadata', {}).get('custom_parent') != custom_parent:
            raise ValueError('Custom parent mismatch')
        reward = (record.get('verifier_result') or {}).get('rewards', {}).get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1):
            raise ValueError('Binary verifier reward required')
        billing = record.get('billing') or {}
        if billing.get('billing_verified') is not True or billing.get('model_protocol_sha256') != protocol:
            raise ValueError('Reaudited billing required')
        metrics = {}
        for key in ('prompt_tokens', 'completion_tokens', 'requests', 'budget_stop_count'):
            value = billing.get(key)
            if type(value) is not int or value < 0:
                raise ValueError('Known nonnegative usage required')
            metrics[key] = value
        cost = Decimal(str(billing['charged_usd']))
        seconds = record.get('phase_seconds', {}).get('agent')
        if not cost.is_finite() or not 0 <= cost <= Decimal('.055'):
            raise ValueError('Invalid final cost')
        if type(seconds) not in (int, float) or not isfinite(seconds) or seconds < 0:
            raise ValueError('Measured finite agent runtime required')
        by_role[role][task] = dict(metrics, reward=int(reward), cost=cost, agent_seconds=seconds)
    if any(set(rows) != set(all_tasks) for rows in by_role.values()):
        raise ValueError('Complete 267-cell matrix required; no missing-cell imputation')
    output = {}
    for name, tasks in [('full_89', sorted(all_tasks)),
                        ('outside_development_69', sorted(set(all_tasks) - set(development_tasks)))]:
        output[name] = {'conditions': {role: summarize([rows[task] for task in tasks])
                                       for role, rows in by_role.items()},
                        'paired': {role: paired(by_role['custom'], by_role[role], tasks)
                                   for role in ROLES[:2]}}
    output['limitations'] = [
        'Pure analysis: caller must reaudit durable results and receipts.',
        'One attempt per condition/task; results do not establish repeatability.',
        'Exact paired p values are exploratory and unadjusted for two comparisons.',
        'Observed tied accuracy does not establish equivalence or an accepted efficiency win.',
        'Final costs include all calls in these trials; setup/development/corrections require separate accounting.']
    output['project_success_certified'] = False
    return output

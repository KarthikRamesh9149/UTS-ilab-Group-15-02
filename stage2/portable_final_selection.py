"""Pure selection over complete, audited portable-development summaries.

The caller must verify registration, source and result-file bindings before
using these summaries. This module neither audits files nor authorises calls,
freezes a deployment, or launches a study. It imports no legacy billing gates.
"""
from decimal import Decimal, InvalidOperation
import math
import re

from portable_custom_policy import cells


def amount(value):
    if not isinstance(value, str):
        raise ValueError('Recorded decimal cost string required')
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError('Invalid recorded cost') from error
    if not result.is_finite() or result < 0:
        raise ValueError('Nonnegative finite recorded cost required')
    return result


def checked(summary, condition, *, expected_cells=None, complexity=None):
    """Reject incomplete/tampered aggregates; keep missing rewards distinct."""
    if not isinstance(summary, dict):
        raise ValueError('Recorded development summary required')
    parent = summary.get('parent')
    rows = summary.get('rows')
    if (summary.get('condition') != condition or not isinstance(rows, list)
            or len(rows) != 20 or summary.get('started_without_result') != []):
        raise ValueError('Complete registered development block required')
    required = {'trial_id', 'task_id', 'harness', 'reward', 'requests',
        'unknown_cost_requests', 'known_charged_usd', 'charged_usd',
        'agent_seconds', 'result_sha256'}
    if any(not isinstance(row, dict) or not required.issubset(row) for row in rows):
        raise ValueError('Explicit per-attempt metadata required')
    tasks = [row.get('task_id') for row in rows]
    expected = cells(tasks, condition, parent) if expected_cells is None else expected_cells
    if len(expected)!=20:
        raise ValueError('Exactly 20 expected cells required')
    if any(any(row.get(k) != value for k, value in cell.items())
           for row, cell in zip(rows, expected)):
        raise ValueError('Original fixed task order and variant trial IDs required')
    costs, known, seconds, result_hashes = [], Decimal(0), [], {}
    unknown = 0
    for row in rows:
        reward = row.get('reward')
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Binary verifier reward or explicitly missing result required')
        for field in ('requests', 'unknown_cost_requests'):
            if type(row.get(field)) is not int or row[field] < 0:
                raise ValueError('Nonnegative observed request counts required')
        if row['unknown_cost_requests'] > row['requests']:
            raise ValueError('Unknown cost count exceeds physical requests')
        subtotal = amount(row.get('known_charged_usd'))
        charge = row.get('charged_usd')
        if row['unknown_cost_requests']:
            if charge is not None:
                raise ValueError('Incomplete cost must remain unknown')
            costs.append(None)
        else:
            total = amount(charge)
            if total != subtotal:
                raise ValueError('Complete cost and known subtotal differ')
            costs.append(total)
        known += subtotal
        unknown += row['unknown_cost_requests']
        elapsed = row.get('agent_seconds')
        if elapsed is not None and (type(elapsed) not in (int, float)
                or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError('Invalid observed agent runtime')
        seconds.append(elapsed)
        digest = row.get('result_sha256')
        if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
            raise ValueError('Result-file hash required')
        result_hashes[row['trial_id']] = digest
    integer_fields = dict(intended=20, attempted=20,
        passes=sum(row['reward'] == 1 for row in rows),
        failures=sum(row['reward'] == 0 for row in rows),
        no_verifier_result=sum(row['reward'] is None for row in rows),
        unknown_cost_requests=unknown,
        complexity=(int(condition == 'C1' or parent == 'C1') + int(condition == 'C2'))
            if complexity is None else complexity)
    if any(type(summary.get(k)) is not int or summary[k] != v for k, v in integer_fields.items()):
        raise ValueError('Summary counts differ from retained rows')
    total = None if None in costs else sum(costs, Decimal(0))
    if amount(summary.get('known_charged_usd')) != known:
        raise ValueError('Known subtotal differs from retained rows')
    if total is None:
        if summary.get('charged_usd') is not None:
            raise ValueError('Unknown total must not become zero or a complete bill')
    elif amount(summary.get('charged_usd')) != total:
        raise ValueError('Complete block cost differs from retained rows')
    elapsed = None if None in seconds else sum(seconds)
    recorded = summary.get('agent_seconds')
    if elapsed is None:
        if recorded is not None:
            raise ValueError('Unknown runtime must remain unknown')
    elif type(recorded) not in (int, float) or not math.isfinite(recorded) or recorded != elapsed:
        raise ValueError('Block runtime differs from retained rows')
    return dict(condition=condition, parent=parent, **integer_fields,
        charged_usd=None if total is None else str(total), known_charged_usd=str(known),
        agent_seconds=elapsed, results_sha256=result_hashes)


def ranked(rows):
    complete_costs = all(row['charged_usd'] is not None for row in rows.values())
    def key(condition):
        row = rows[condition]
        return (-row['passes'],
            *((amount(row['charged_usd']),) if complete_costs else ()),
            row['complexity'],
            row['agent_seconds'] if row['agent_seconds'] is not None else math.inf,
            condition)
    return min(rows, key=key), complete_costs


def diagnostic(rows, winner, parent):
    """Preserve the planned one-lever ablation or unchanged-repeat rule."""
    additions = []
    if winner == 'C1' or (winner == 'C2' and parent == 'C1'):
        additions.append((rows['C1']['passes'] - rows['C0']['passes'],
                          1, 'planning', 'C0'))
    if winner == 'C2':
        additions.append((rows['C2']['passes'] - rows[parent]['passes'],
                          2, 'completion', parent))
    improving = [addition for addition in additions if addition[0] > 0]
    if not improving:
        return dict(kind='unchanged_repeat', condition=winner,
                    parent=parent if winner == 'C2' else None)
    gain, _, addition, fallback = max(improving)
    remove_planning_from_c2 = winner == 'C2' and addition == 'planning'
    return dict(kind='ablation', remove=addition, incremental_pass_gain=gain,
        condition='C2' if remove_planning_from_c2 else fallback,
        parent='C0' if remove_planning_from_c2 else None)


def select(summaries):
    """Apply the registered ranking, not a new score or a best-of task merge."""
    if not isinstance(summaries, dict) or set(summaries) != {'C0', 'C1', 'C2'}:
        raise ValueError('All three complete development variants required')
    rows = {condition: checked(summaries[condition], condition)
            for condition in ('C0', 'C1', 'C2')}
    parent, parent_cost = ranked({condition: rows[condition] for condition in ('C0', 'C1')})
    if rows['C2']['parent'] != parent:
        raise ValueError('C2 does not match the preselected C0/C1 parent')
    winner, finalist_cost = ranked(rows)
    return dict(kind='portable_development_selection_not_final_freeze',
        selected=winner, selected_parent=parent,
        custom_parent=parent if winner == 'C2' else None,
        parent_cost_tiebreak_used=parent_cost, cost_tiebreak_used=finalist_cost,
        summaries=rows, total_development_attempts=60,
        diagnostic=diagnostic(rows, winner, parent),
        primary_comparator='terminus-2', secondary_comparator='openhands',
        efficiency_win_claimed=False, full_benchmark_win_claimed=False,
        paid_launch_ready=False,
        remaining=['source-bound confirmation and diagnostic', 'final freeze',
                   'native final-run qualification', 'exact final89 registration'])

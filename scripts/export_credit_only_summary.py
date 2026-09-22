"""Audit a completed, private evidence copy and export only allowlisted metadata.

No provider calls, receipt collection, trial execution or mutation of evidence.
Unknown costs remain unknown. Historical result sets are kept separate.
"""
import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re


HARNESSES = ('terminus-2', 'openhands')


def read(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Regular evidence file required: ' + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def error_name(value):
    if value is None:
        return None
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,79}', value),
            'Only exception class names may be exported')
    return value


def safe_task_id(value):
    return isinstance(value, str) and bool(re.fullmatch(r'[a-z0-9][a-z0-9_.-]*', value)) and '..' not in value


def audit_trial(runtime, cell):
    trial_id = cell['trial_id']
    result_path = runtime / 'scored-trials' / trial_id / 'result.json'
    result = read(result_path)
    require(all(result.get(k) == cell[k] for k in ('trial_id', 'task_id', 'harness')), 'Trial identity mismatch')
    require(all(result.get(k) is True for k in ('containers_removed', 'networks_removed', 'volumes_removed'))
            and result.get('status') != 'cleanup_failed' and not result.get('bridge_error_type'),
            'Incomplete cleanup')
    reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    require(type(reward) in (int, float) and reward in (0, 1), 'Missing or nonbinary verifier result')
    evidence = runtime / 'scored-attempts' / trial_id
    requests = sorted(evidence.glob('*.request.json'))
    outcomes = sorted(evidence.glob('*.outcome.json'))
    require({p.name.removesuffix('.request.json') for p in requests}
            == {p.name.removesuffix('.outcome.json') for p in outcomes}, 'Unpaired request/outcome evidence')
    known, unknown, accepted, rate_limited = Decimal(0), 0, 0, 0
    tokens = {'input_tokens': [], 'output_tokens': []}
    for path in outcomes:
        value = read(path)
        require(value['trial_id'] == trial_id, 'Call identity mismatch')
        cost = value.get('cost_usd')
        if cost is None:
            unknown += 1
        else:
            require(type(cost) in (str, int), 'Exact decimal cost required')
            amount = Decimal(cost)
            require(amount.is_finite() and amount >= 0, 'Invalid cost')
            known += amount
        require(value['status'] in ('ok', 'error'), 'Nonterminal model request')
        accepted += value['status'] == 'ok' and value.get('accepted_for_agent') is True
        for key in tokens:
            token_count = value.get(key)
            require(token_count is None or type(token_count) is int and token_count >= 0, 'Invalid token count')
            if token_count is not None:
                tokens[key].append(token_count)
        diagnostic = path.with_name(path.name.removesuffix('.outcome.json') + '.transport-error.json')
        if diagnostic.exists():
            rate_limited += read(diagnostic).get('http_status') == 429
    billing = result['billing']
    require(billing['accounting_mode'] == 'provider-credit-only', 'Wrong accounting mode')
    require(billing['requests'] == len(requests) and billing['unknown_cost_requests'] == unknown
            and Decimal(billing['known_charged_usd']) == known, 'Recorded accounting disagrees with call evidence')
    require(billing['charged_usd'] is None if unknown else Decimal(billing['charged_usd']) == known,
            'Unknown charge was presented as a complete total')
    require(billing['costs_complete'] is (unknown == 0), 'Cost completeness mismatch')
    require(not (evidence / 'provider-stop.json').exists(), 'Provider stop requires separate disposition')
    token_fields = {}
    for source, target in (('input_tokens', 'prompt_tokens'), ('output_tokens', 'completion_tokens')):
        token_fields['known_' + target] = sum(tokens[source])
        token_fields[target] = sum(tokens[source]) if len(tokens[source]) == len(requests) else None
        require(billing['known_' + target] == token_fields['known_' + target]
                and billing[target] == token_fields[target], 'Recorded tokens disagree with call evidence')
    return dict(trial_id=trial_id, task_id=cell['task_id'], harness=cell['harness'], reward=int(reward),
        agent_error_type=error_name(result.get('agent_error_type')),
        verifier_error_type=error_name(result.get('verifier_error_type')),
        model_requests=len(requests), accepted_model_responses=accepted,
        http_429_requests=rate_limited, known_cost_usd=str(known),
        total_cost_usd=None if unknown else str(known), unknown_cost_requests=unknown,
        **token_fields, cleanup_complete=True, result_sha256=sha(result_path))


def condition(rows):
    unknown = sum(r['unknown_cost_requests'] for r in rows)
    known = str(sum((Decimal(r['known_cost_usd']) for r in rows), Decimal(0)))
    return dict(attempted=len(rows), passed=sum(r['reward'] == 1 for r in rows),
        failed=sum(r['reward'] == 0 for r in rows), no_verifier_result=0,
        model_requests=sum(r['model_requests'] for r in rows),
        accepted_model_responses=sum(r['accepted_model_responses'] for r in rows),
        http_429_requests=sum(r['http_429_requests'] for r in rows),
        trials_with_http_429=sum(r['http_429_requests'] > 0 for r in rows),
        zero_model_request_trials=sum(r['model_requests'] == 0 for r in rows),
        agent_error_types=dict(Counter(r['agent_error_type'] or 'none' for r in rows)),
        known_cost_usd=known, total_cost_usd=None if unknown else known, unknown_cost_requests=unknown,
        known_prompt_tokens=sum(r['known_prompt_tokens'] for r in rows),
        known_completion_tokens=sum(r['known_completion_tokens'] for r in rows),
        prompt_tokens=sum(r['prompt_tokens'] for r in rows) if all(r['prompt_tokens'] is not None for r in rows) else None,
        completion_tokens=sum(r['completion_tokens'] for r in rows) if all(r['completion_tokens'] is not None for r in rows) else None)


def historical(runtime, registration_name):
    registration = read(runtime / registration_name)
    rows = []
    for cell in registration['cells']:
        path = runtime / 'scored-trials' / cell['trial_id'] / 'result.json'
        if not path.exists():
            continue
        result = read(path)
        require(all(result.get(k) == cell[k] for k in ('trial_id', 'task_id', 'harness')), 'Historical identity mismatch')
        reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        require(type(reward) in (int, float) and reward in (0, 1), 'Historical nonbinary outcome')
        rows.append(dict(harness=cell['harness'], task_id=cell['task_id'], reward=reward))
    require(len({(r['harness'], r['task_id']) for r in rows}) == len(rows), 'Duplicate historical cell')
    return dict(intended=len(registration['cells']), completed=len(rows),
        conditions={h: dict(attempted=sum(r['harness'] == h for r in rows),
                            passed=sum(r['harness'] == h and r['reward'] == 1 for r in rows)) for h in HARNESSES})


def audit(root, history):
    runtime = root / '.runtime/stage2'
    registration = read(runtime / 'credit-only-matrix.json')
    qualification = read(runtime / 'credit-only-qualification.json')
    manifest = read(root / 'stage2/input_manifest.json')
    task_ids = manifest['all_task_ids']
    cells = registration['cells']
    require(len(task_ids) == len(set(task_ids)) == 89, 'Exactly 89 frozen tasks required')
    require(all(safe_task_id(task) for task in task_ids), 'Unexpected task identifier')
    require(len(cells) == 178 and len({c['trial_id'] for c in cells}) == 178, 'Expected 178 unique trials')
    require({(c['harness'], c['task_id']) for c in cells}
            == {(h, task) for h in HARNESSES for task in task_ids}, 'Frozen task coverage mismatch')
    expected = {c['trial_id'] for c in cells}
    require({p.name for p in (runtime / 'scored-trials').iterdir()} == expected, 'Missing or unexpected trials')
    require({p.name for p in (runtime / 'scored-attempts').iterdir()} == expected, 'Missing or unexpected attempts')
    require(registration['sources'] == qualification['sources'], 'Qualification source binding mismatch')
    require(qualification['offline_passed'] is True and qualification['synthetic_passed'] is True
            and qualification['live_api_calls'] == 0, 'Incomplete native qualification')
    require(set(qualification['evidence_sha256']) == {'credit-only-offline-tests.json',
            'credit-only-image-tests.json', 'credit-only-synthetic.json'}, 'Incomplete qualification evidence')
    require(registration['model_protocol_sha256'] == qualification['model_protocol_sha256']
            and registration['attempts_per_cell'] == registration['parallel_trials'] == 1,
            'Frozen execution protocol mismatch')
    require(all(sha(runtime / name) == digest for name, digest in qualification['evidence_sha256'].items()),
            'Qualification evidence hash mismatch')
    policy = registration['policy']
    require(all(policy[k] is None for k in ('per_task_cap_usd', 'stage_cap_usd', 'project_cap_usd', 'provider_max_price'))
            and Decimal(policy['reserve_usd']) == 0 and policy['accounting_blocks_dispatch'] is False,
            'Monetary gating policy mismatch')
    rows = [audit_trial(runtime, c) for c in cells]
    original = history / 'uts-capstone/.runtime/stage2'
    repeat = history / 'uts-capstone-baseline-repeat-20260921/.runtime/stage2'
    require(sha(repeat / 'baseline-repeat-matrix.json') == registration['predecessor_registration_sha256'],
            'Predecessor registration changed')
    require(all(sha(repeat / 'scored-trials' / trial / 'result.json') == digest
                for trial, digest in registration['predecessor_results_sha256'].items()), 'Predecessor result changed')
    require(sha(original / 'baseline-matrix.json') == read(repeat / 'baseline-repeat-matrix.json')['parent_registration_sha256'],
            'Original registration changed')
    summary = dict(experiment=registration['experiment'], intended=178, completed=178,
        model_protocol=read(runtime / 'model-protocol.json'),
        model_protocol_sha256=registration['model_protocol_sha256'],
        conditions={h: condition([r for r in rows if r['harness'] == h]) for h in HARNESSES},
        all_calls=condition(rows), accounting_source='response_usage_cost; not independently receipt-reconciled',
        qualification_and_coverage_checks='passed', predecessor_results_unchanged=True,
        registration_sha256=sha(runtime / 'credit-only-matrix.json'),
        qualification_sha256=sha(runtime / 'credit-only-qualification.json'),
        historical_runs={'original_capped': historical(original, 'baseline-matrix.json'),
                         'capped_repeat_terminal_partial': historical(repeat, 'baseline-repeat-matrix.json')})
    require(summary['historical_runs']['original_capped']['completed'] == 178
            and summary['historical_runs']['capped_repeat_terminal_partial']['completed'] == registration['predecessor_completed'],
            'Historical coverage disagrees with handoff registration')
    starts = [datetime.fromisoformat(read(runtime / 'scored-trials' / c['trial_id'] / 'result.json')['started_utc']) for c in cells]
    last_write = max((runtime / 'scored-trials' / c['trial_id'] / 'result.json').stat().st_mtime for c in cells)
    summary['first_trial_started_utc'] = min(starts).isoformat()
    summary['last_result_written_utc'] = datetime.fromtimestamp(last_write, timezone.utc).isoformat()
    summary['elapsed_minutes_to_last_result_write'] = round((last_write - min(starts).timestamp()) / 60, 2)
    return rows, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True)
    parser.add_argument('--history-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rows, summary = audit(args.evidence_root, args.history_root)
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / 'trials.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(dict(completed=len(rows), conditions=summary['conditions'], checks='passed')))


if __name__ == '__main__':
    main()

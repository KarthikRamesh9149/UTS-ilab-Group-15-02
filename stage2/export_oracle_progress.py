"""Export only qualification metadata, never reference or verifier logs."""
from datetime import datetime, timezone
import json
from pathlib import Path


def summary(root):
    selected = json.loads((root / 'stage2/input_manifest.json').read_text())['development_ids']
    if len(selected) != 20 or len(set(selected)) != 20:
        raise ValueError('Expected frozen unique dev20')
    results, pending = [], []
    for task in selected:
        source = root / '.runtime/stage2/oracle-dev20-v2' / task / 'result.json'
        if not source.exists():
            pending.append(task)
            continue
        value = json.loads(source.read_text())
        if value['task'] != task or value['live_api_calls'] != 0 or value.get('runtime_revision') != 'explicit-log-mounts-v2':
            raise ValueError('Unexpected qualification identity')
        row = {key: value[key] for key in ['task', 'status', 'time_utc', 'elapsed_seconds', 'cleanup_verified']}
        for key in ['image_id', 'resource_limits_verified', 'error_type']:
            if key in value:
                row[key] = value[key]
        row.update(value['task_limits'])
        if value['status'] == 'verified':
            reward = value['verifier']['rewards']['reward']
            if isinstance(reward, bool) or reward not in (0, 1):
                raise ValueError('Unexpected reward semantics')
            row['reward'] = reward
        results.append(row)
    valid = sum(row['status'] == 'verified' for row in results)
    passed = sum(row.get('reward') == 1 for row in results)
    qualified = passed == 20 and all(row.get('resource_limits_verified') is True and row['cleanup_verified'] is True for row in results)
    return {'kind': 'reference_solution_runtime_qualification_not_model_score',
        'status': 'all_references_passed' if qualified else 'qualification_incomplete' if not pending else 'partial_snapshot',
        'snapshot_utc': datetime.now(timezone.utc).isoformat(), 'frozen_development_tasks': 20,
        'valid_results_in_snapshot': valid, 'reference_passes_in_snapshot': passed,
        'live_api_calls': 0, 'runtime_revision': 'explicit-log-mounts-v2',
        'results': results, 'pending_tasks': pending,
        'limitations': ['Reference results are not baseline or custom-model scores.',
            'The original uncollected video-processing attempt is retained locally; only log mounts changed for v2.',
            'Reward-zero results are preserved and do not qualify a task as reference-passing.']}


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    value = summary(root)
    output = root / 'stage2/oracle_qualification_progress.json'
    temporary = output.with_suffix('.json.tmp')
    with temporary.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
    temporary.replace(output)
    print(json.dumps({key: value[key] for key in ['status', 'valid_results_in_snapshot', 'reference_passes_in_snapshot']}))

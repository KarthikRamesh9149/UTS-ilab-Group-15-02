"""Summarise a Harbor job directory into a classified per-trial CSV.

Usage:
    python -m saranya_harness.summarize <job_dir> <output.csv> [--host mac]

Reads each trial's result.json only. Writes no raw model exchanges.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path

from saranya_harness.classify import classify_trial

FIELDS = ['task_id', 'trial_name', 'reward', 'category', 'reason', 'exception_type', 'stop_reason',
          'model_calls', 'input_tokens', 'cached_tokens', 'output_tokens', 'charged_usd',
          'reported_cost_usd', 'unknown_usage_calls', 'agent_seconds', 'host']


def _seconds(timing: dict | None) -> float | None:
    from datetime import datetime
    if not timing or not timing.get('started_at') or not timing.get('finished_at'):
        return None
    start = datetime.fromisoformat(timing['started_at'])
    end = datetime.fromisoformat(timing['finished_at'])
    return round((end - start).total_seconds(), 3)


def trial_row(result: dict, host_override: str | None = None) -> dict:
    rewards = (result.get('verifier_result') or {}).get('rewards') or {}
    reward = rewards.get('reward')
    exception = (result.get('exception_info') or {}).get('exception_type')
    agent = result.get('agent_result') or {}
    metadata = agent.get('metadata') or {}
    host = host_override or metadata.get('host') or 'unknown'
    signals = [s for entry in metadata.get('infrastructure_signals') or [] for s in entry.get('signatures', [])]
    stop_reason = metadata.get('stop_reason')
    category, reason = classify_trial(
        task_id=result['task_name'].split('/')[-1], reward=reward, exception_type=exception,
        infrastructure_signals=signals, host=host, stop_reason=stop_reason)
    return {
        'task_id': result['task_name'].split('/')[-1], 'trial_name': result.get('trial_name'),
        'reward': reward, 'category': category, 'reason': reason, 'exception_type': exception,
        'stop_reason': stop_reason, 'model_calls': metadata.get('model_calls'),
        'input_tokens': agent.get('n_input_tokens'), 'cached_tokens': agent.get('n_cache_tokens'),
        'output_tokens': agent.get('n_output_tokens'), 'charged_usd': metadata.get('charged_usd'),
        'reported_cost_usd': metadata.get('reported_cost_usd'),
        'unknown_usage_calls': metadata.get('unknown_usage_calls'),
        'agent_seconds': _seconds(result.get('agent_execution')), 'host': host,
    }


def summarise(job_dir: Path, output: Path, host: str | None = None) -> Counter:
    rows = []
    for path in sorted(Path(job_dir).glob('*/result.json')):
        result = json.loads(path.read_text())
        if 'task_name' in result:
            rows.append(trial_row(result, host))
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return Counter(row['category'] for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('job_dir', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--host', default=None)
    args = parser.parse_args()
    counts = summarise(args.job_dir, args.output, args.host)
    for category, count in sorted(counts.items()):
        print(f'{category}: {count}')


if __name__ == '__main__':
    main()

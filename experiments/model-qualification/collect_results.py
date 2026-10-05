"""Build results.csv from local Terminus-2 trial records plus Stage 2 reference rows.

Usage:
    python collect_results.py <output.csv> <jobs-dir> [<jobs-dir> ...] [--ollama URL]

Every local trial is kept, with a validity label:
- "pilot": run before top_p = 1.0 was added, so not part of the comparison;
- "invalid: Mac slept during trial": a macOS sleep or wake event (from
  `pmset -g log`) falls between the trial's start and finish, so Harbor's time
  limit did not hold;
- "infrastructure: failed before any model call": an exception, no tokens and
  an empty agent folder;
- "infrastructure: verifier tests did not run": a reward was written but the
  verifier output has no test summary (for example, it could not download its
  test tools), so the reward is not a measurement;
- "valid": everything else.

Model digests come from the running Ollama server (/api/tags). Reference rows
are the committed Stage 2 Terminus-2 + DeepSeek V4 Flash round C results
(stage2/results/baseline-corrected-20260923/trials.csv, read only) for the tasks
that have at least one valid local trial.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
from urllib.request import urlopen

REFERENCE = Path(__file__).resolve().parents[2] / 'stage2/results/baseline-corrected-20260923/trials.csv'
FIELDS = ['source', 'validity', 'harness', 'model', 'tag', 'digest', 'host', 'task', 'reward',
          'tests_passed', 'tests_total', 'exception_type', 'input_tokens', 'output_tokens',
          'agent_seconds', 'total_seconds', 'started_utc', 'trial_name']
SUMMARY = re.compile(r'=+ (.*) in [\d.]+s')


def _time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return round((_time(end) - _time(start)).total_seconds(), 1)


def sleep_events() -> list[datetime]:
    """Times of macOS Sleep, DarkWake and Wake events (not "Wake Requests")."""
    log = subprocess.run(['pmset', '-g', 'log'], capture_output=True, text=True).stdout
    events = []
    for line in log.splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        kind = parts[3]
        if kind in ('Sleep', 'DarkWake') or (kind == 'Wake' and (len(parts) < 5 or parts[4] != 'Requests')):
            try:
                events.append(datetime.strptime(' '.join(parts[:3]), '%Y-%m-%d %H:%M:%S %z'))
            except ValueError:
                pass
    return events


def tests(verifier_stdout: Path) -> tuple[int | None, int | None]:
    if not verifier_stdout.exists():
        return None, None
    matches = SUMMARY.findall(verifier_stdout.read_text(errors='replace'))
    if not matches:
        return None, None
    counts = dict((word, int(n)) for n, word in re.findall(r'(\d+) (passed|failed|error)', matches[-1]))
    passed = counts.get('passed', 0)
    return passed, passed + counts.get('failed', 0) + counts.get('error', 0)


def validity(result: dict, trial_dir: Path, events: list[datetime]) -> str:
    kwargs = (result.get('config') or {}).get('agent', {}).get('kwargs') or {}
    if 'top_p' not in (kwargs.get('llm_call_kwargs') or {}):
        return 'pilot: top_p not sent (Ollama default 0.95)'
    start, end = _time(result.get('started_at')), _time(result.get('finished_at'))
    if start and end and any(start <= event <= end for event in events):
        return 'invalid: Mac slept during trial'
    agent_dir = trial_dir / 'agent'
    empty = not agent_dir.exists() or not any(agent_dir.iterdir())
    no_tokens = not (result.get('agent_result') or {}).get('n_input_tokens')
    if result.get('exception_info') and no_tokens and empty:
        return 'infrastructure: failed before any model call'
    if tests(trial_dir / 'verifier' / 'test-stdout.txt') == (None, None):
        return 'infrastructure: verifier tests did not run'
    return 'valid'


def ollama_digests(base: str) -> dict[str, str]:
    with urlopen(base.rstrip('/') + '/api/tags', timeout=10) as response:
        return {m['name']: m['digest'] for m in json.load(response)['models']}


def local_rows(jobs_dirs: list[Path], digests: dict[str, str], events: list[datetime]) -> list[dict]:
    rows = []
    for jobs_dir in jobs_dirs:
        for path in sorted(jobs_dir.glob('*/*/result.json')):
            result = json.loads(path.read_text())
            if 'task_name' not in result:
                continue
            tag = (result.get('config') or {}).get('agent', {}).get('model_name', '').removeprefix('openai/')
            agent = result.get('agent_result') or {}
            timing = result.get('agent_execution') or {}
            passed, total = tests(path.parent / 'verifier' / 'test-stdout.txt')
            rows.append({
                'source': 'this check (local Ollama)',
                'validity': validity(result, path.parent, events),
                'harness': 'terminus-2', 'model': tag.split(':')[0], 'tag': tag,
                'digest': digests.get(tag, 'unknown'),
                'host': 'Apple Silicon Mac, Docker Desktop (x86-64 images under Rosetta)',
                'task': result['task_name'].split('/')[-1],
                'reward': ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward'),
                'tests_passed': passed, 'tests_total': total,
                'exception_type': (result.get('exception_info') or {}).get('exception_type'),
                'input_tokens': agent.get('n_input_tokens'), 'output_tokens': agent.get('n_output_tokens'),
                'agent_seconds': _seconds(timing.get('started_at'), timing.get('finished_at')),
                'total_seconds': _seconds(result.get('started_at'), result.get('finished_at')),
                'started_utc': result.get('started_at'), 'trial_name': result.get('trial_name'),
            })
    return sorted(rows, key=lambda row: row['started_utc'] or '')


def reference_rows(tasks: set[str]) -> list[dict]:
    rows = []
    with open(REFERENCE, newline='') as handle:
        for row in csv.DictReader(handle):
            if row['harness'] != 'terminus-2' or row['task_id'] not in tasks:
                continue
            rows.append({
                'source': 'Stage 2 round C (committed)', 'validity': 'reference',
                'harness': 'terminus-2', 'model': 'deepseek-v4-flash-0731',
                'tag': 'deepseek/deepseek-v4-flash-0731 via deepinfra/fp8', 'digest': 'n/a (hosted)',
                'host': 'native x86-64 Linux server (Netcup)', 'task': row['task_id'],
                'reward': row['reward'], 'tests_passed': None, 'tests_total': None,
                'exception_type': row['agent_error_type'] or None,
                # Known token counts only; requests with unknown usage are not included.
                'input_tokens': row['known_input_tokens'] or None,
                'output_tokens': row['known_output_tokens'] or None,
                'agent_seconds': round(float(row['agent_seconds']), 1) if row['agent_seconds'] else None,
                'total_seconds': None, 'started_utc': row['started_utc'], 'trial_name': row['trial_id'],
            })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('jobs_dirs', type=Path, nargs='+')
    parser.add_argument('--ollama', default='http://127.0.0.1:11434')
    args = parser.parse_args()
    local = local_rows(args.jobs_dirs, ollama_digests(args.ollama), sleep_events())
    valid_tasks = {row['task'] for row in local if row['validity'] == 'valid'}
    rows = local + reference_rows(valid_tasks)
    with open(args.output, 'w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f'{len(local)} local rows, {len(rows) - len(local)} reference rows -> {args.output}')


if __name__ == '__main__':
    main()

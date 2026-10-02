"""Print every analysis table as markdown.

Usage (from experiments/saranya-analysis/):
    python -m saranya_analysis.report [--root REPO_ROOT]
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from saranya_analysis.failures import CATEGORIES, failure_counts, passes_with_agent_error
from saranya_analysis.load import DEV20, DEV20_REFERENCE, FULL89, find_root, load_group, load_recovery
from saranya_analysis.stats import bootstrap_difference, mcnemar_exact, outcome_vector, paired, score
from saranya_analysis.usage import usage

RESAMPLES = 10_000
SEED = 42


def _pct(value: float | None) -> str:
    return '—' if value is None else f'{100 * value:.1f}%'


def _table(header: list[str], rows: list[list]) -> str:
    lines = ['| ' + ' | '.join(header) + ' |', '|' + '|'.join('---' for _ in header) + '|']
    lines += ['| ' + ' | '.join(str(cell) for cell in row) + ' |' for row in rows]
    return '\n'.join(lines)


def score_section(runs: dict, intended: list[str], title: str) -> str:
    rows = []
    for name, trials in runs.items():
        s = score(name, trials, intended)
        rows.append([name, f'{s.passed} / {s.intended}', f'{s.valid} / {s.intended} ({_pct(s.coverage)})',
                     _pct(s.pass_rate_intended), _pct(s.pass_rate_valid)])
    return f'### {title}\n\n' + _table(
        ['Harness', 'Passes / intended', 'Valid verifier outcomes', 'Pass rate (intended)',
         'Pass rate (valid only)'], rows)


def split_section(runs: dict, dev_tasks: list[str], intended: list[str]) -> str:
    """Stage 2's protocol reports the 69 tasks outside development separately.

    C0-NC's parent (C0) was chosen using the dev20 results, so only the other
    69 tasks are held out from custom-harness selection.
    """
    held_out = [task for task in intended if task not in set(dev_tasks)]
    rows = []
    for name, trials in runs.items():
        dev, rest = score(name, trials, sorted(dev_tasks)), score(name, trials, held_out)
        rows.append([name, f'{dev.passed} / {dev.intended}', f'{rest.passed} / {rest.intended}',
                     f'{rest.valid} / {rest.intended}', _pct(rest.pass_rate_intended)])
    return ('### Development tasks vs held-out tasks (same runs, split)\n\n'
            'These are the same 89-task runs split by task set. C0 was selected on the dev20 '
            'tasks, so only the other 69 are held out from custom-harness selection.\n\n'
            + _table(['Harness', 'dev20 tasks', 'Other 69 tasks', 'Valid on other 69',
                      'Pass rate on other 69 (intended)'], rows))


def paired_section(runs: dict, intended: list[str], recovery: dict) -> str:
    out = ['### Paired per-task comparison', '',
           'Counts use tasks where both harnesses have a verifier outcome. The exact McNemar '
           'p-value is two-sided, on the discordant pairs only.', '']
    rows = []
    sensitivity = []
    c0nc_with_recovery = {**runs['C0-NC'], **{t: replace(r, harness='C0-NC') for t, r in recovery.items()}}
    for other in ('Terminus-2', 'OpenHands'):
        p = paired('C0-NC', runs['C0-NC'], other, runs[other], intended)
        rows.append([f'C0-NC vs {other}', p.both, p.only_a, p.only_b, p.neither,
                     len(p.a_missing) + len(p.b_missing), f'{mcnemar_exact(p.only_a, p.only_b):.3f}'])
        # Sensitivity 1: C0-NC's missing outcomes counted as failures.
        only_b_missing = sum(1 for t in p.a_missing if runs[other][t].passed)
        sensitivity.append([f'C0-NC vs {other}', 'missing counted as C0-NC failures',
                            p.only_a, p.only_b + only_b_missing,
                            f'{mcnemar_exact(p.only_a, p.only_b + only_b_missing):.3f}'])
        # Sensitivity 2: Stage 2's separate recovery outcomes substituted (not the official score).
        q = paired('C0-NC', c0nc_with_recovery, other, runs[other], intended)
        sensitivity.append([f'C0-NC vs {other}', 'recovery outcomes substituted (not official)',
                            q.only_a, q.only_b, f'{mcnemar_exact(q.only_a, q.only_b):.3f}'])
    out.append(_table(['Comparison', 'Both pass', 'Only C0-NC', 'Only baseline', 'Neither',
                       'Excluded (no outcome)', 'McNemar p'], rows))
    missing = [t for t in intended if not runs['C0-NC'][t].valid]
    out += ['', f'Excluded tasks (C0-NC setup failures): {", ".join(sorted(missing))}.', '',
            '#### Sensitivity checks', '', _table(
                ['Comparison', 'Treatment of the 3 missing', 'Only C0-NC', 'Only baseline', 'McNemar p'],
                sensitivity)]
    return '\n'.join(out)


def bootstrap_section(runs: dict, intended: list[str]) -> str:
    pairs = [('C0-NC', 'Terminus-2'), ('C0-NC', 'OpenHands'), ('Terminus-2', 'OpenHands')]
    rows = []
    for a, b in pairs:
        interval = bootstrap_difference(outcome_vector(runs[a], intended), outcome_vector(runs[b], intended),
                                        resamples=RESAMPLES, seed=SEED)
        label = f'{a} − {b}' + (' (reference)' if a != 'C0-NC' else '')
        rows.append([label, f'{100 * interval.difference:+.1f} pts',
                     f'[{100 * interval.low:+.1f}, {100 * interval.high:+.1f}] pts'])
    return ('### Pass-rate differences with paired bootstrap intervals\n\n'
            f'Pass rates are over all 89 intended tasks; a missing verifier outcome counts as not passed. '
            f'Whole tasks are resampled with replacement ({RESAMPLES:,} resamples, seed {SEED}); the '
            'interval is the 2.5th–97.5th percentile.\n\n'
            + _table(['Difference', 'Observed', '95% bootstrap interval'], rows))


def failure_section(runs: dict, title: str) -> str:
    rows = []
    for name, trials in runs.items():
        counts = failure_counts(trials)
        rows.append([name, sum(t.passed for t in trials.values()), *[counts.get(c, 0) for c in CATEGORIES],
                     passes_with_agent_error(trials)])
    return f'### {title}\n\n' + _table(
        ['Harness', 'Passed', *[c.capitalize() for c in CATEGORIES], 'Passes with an agent error recorded'], rows)


def usage_section(runs: dict, title: str) -> str:
    cost_rows, time_rows = [], []
    for name, trials in runs.items():
        u = usage(name, trials)
        cost_rows.append([name, f'{u.model_requests:,}', f'{u.accepted_responses:,}', f'{u.http_429_requests:,}',
                          f'{u.unknown_cost_requests:,}', f'{u.known_cost_usd:.4f}',
                          'known' if u.total_cost_known else 'unknown',
                          f'{u.known_input_tokens:,}', f'{u.known_output_tokens:,}',
                          f'{u.trials_with_complete_tokens} / {u.trials}'])
        time_rows.append([name, f'{u.trials_with_agent_time} / {u.trials}', f'{u.agent_seconds_total / 3600:.1f}',
                          '—' if u.agent_seconds_median is None else f'{u.agent_seconds_median:.0f}'])
    return (f'### {title}: cost and tokens\n\n'
            + _table(['Harness', 'Model requests', 'Accepted responses', 'HTTP 429', 'Unknown-cost requests',
                      'Known cost (US$)', 'Total cost', 'Known input tokens', 'Known output tokens',
                      'Trials with complete token counts'], cost_rows)
            + f'\n\n### {title}: agent runtime\n\n'
            + _table(['Harness', 'Trials with measured agent time', 'Total agent hours',
                      'Median agent seconds'], time_rows))


def build(root: Path | None = None) -> str:
    root = root or find_root()
    full = load_group(FULL89, root)
    intended = sorted(full['Terminus-2'])
    for name, trials in full.items():
        if sorted(trials) != intended:
            raise ValueError(f'{name} does not cover the same 89 tasks')
    dev = {**load_group(DEV20, root), **load_group(DEV20_REFERENCE, root)}
    dev_intended = sorted(dev['C0'])
    for name, trials in dev.items():
        if sorted(trials) != dev_intended:
            raise ValueError(f'{name} does not cover the same 20 tasks')
    recovery = load_recovery(root)
    custom_dev = {k: dev[k] for k in DEV20}
    reference_dev = {k: dev[k] for k in DEV20_REFERENCE}
    sections = [
        '## All 89 tasks (one run each)',
        score_section(full, intended, 'Scores'),
        split_section(full, dev_intended, intended),
        paired_section(full, intended, recovery),
        bootstrap_section(full, intended),
        failure_section(full, 'Failure categories'),
        usage_section(full, 'All 89 tasks'),
        '## Fixed dev20 tasks (separate; never pooled with the 89-task numbers)',
        score_section({**custom_dev, **reference_dev}, dev_intended, 'dev20 scores'),
        failure_section({**custom_dev, **reference_dev}, 'dev20 failure categories'),
        usage_section({**custom_dev, **reference_dev}, 'dev20'),
    ]
    return '\n\n'.join(sections) + '\n'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=None, help='repository root (default: found automatically)')
    print(build(parser.parse_args().root), end='')


if __name__ == '__main__':
    main()

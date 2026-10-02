"""Load committed Stage 2 trial CSVs into one normalised record type.

Only files under stage2/results/ are read; nothing there is written. Blank
fields stay None (unknown), never zero.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

RESULTS = 'stage2/results'

# Full 89-task runs. Round C is the "corrected" baseline experiment.
FULL89 = {
    'Terminus-2': ('baseline-corrected-20260923/trials.csv', 'terminus-2'),
    'OpenHands': ('baseline-corrected-20260923/trials.csv', 'openhands'),
    'C0-NC': ('custom-no-cutoff-final-20260928/c0-nc/trials.csv', None),
}

# Fixed dev20 runs. The baseline rows are the round C attempts on the same 20
# tasks, published separately for custom development comparisons.
DEV20 = {
    'C0': ('custom-portable-20260926/c0/trials.csv', None),
    'C1': ('custom-portable-20260926/c1/trials.csv', None),
    'C2': ('custom-portable-20260926/c2/trials.csv', None),
    'C3': ('custom-deadline-20260927/c3/trials.csv', None),
}
DEV20_REFERENCE = {
    'Terminus-2 (round C, dev20)': ('baseline-corrected-20260923/development-baselines.csv', 'terminus-2'),
    'OpenHands (round C, dev20)': ('baseline-corrected-20260923/development-baselines.csv', 'openhands'),
}

# Separate recovery attempts for C0-NC's three setup failures. Stage 2 states
# these are not replacements for, or additions to, the original 89.
RECOVERY = 'custom-no-cutoff-recovery-20260929/trials.csv'


@dataclass(frozen=True)
class Trial:
    task_id: str
    harness: str
    reward: int | None  # 1 pass, 0 verified fail, None no verifier outcome
    status: str  # 'verified' or the file's own non-verified status
    agent_error_type: str | None
    verifier_error_type: str | None
    model_requests: int | None
    accepted_responses: int | None
    http_429_requests: int | None
    unknown_cost_requests: int | None
    known_cost_usd: Decimal | None
    total_cost_usd: Decimal | None
    known_input_tokens: int | None
    known_output_tokens: int | None
    input_tokens: int | None  # complete total; blank when some requests lack usage
    output_tokens: int | None
    setup_seconds: float | None
    agent_seconds: float | None
    verifier_seconds: float | None

    @property
    def valid(self) -> bool:
        return self.reward is not None

    @property
    def passed(self) -> bool:
        return self.reward == 1


def _text(value: str | None) -> str | None:
    return value if value not in (None, '') else None


def _int(value: str | None) -> int | None:
    return int(value) if value not in (None, '') else None


def _float(value: str | None) -> float | None:
    return float(value) if value not in (None, '') else None


def _decimal(value: str | None) -> Decimal | None:
    return Decimal(value) if value not in (None, '') else None


def _reward(value: str | None) -> int | None:
    if value in (None, ''):
        return None
    number = float(value)
    if number not in (0.0, 1.0):
        raise ValueError(f'Unexpected non-binary reward {value!r}')
    return int(number)


def parse_row(row: dict[str, str], harness: str) -> Trial:
    reward = _reward(row.get('reward'))
    status = _text(row.get('status')) or ('verified' if reward is not None else 'missing')
    if (status == 'verified') != (reward is not None):
        raise ValueError(f"{row.get('task_id')}: status {status!r} disagrees with reward {row.get('reward')!r}")
    return Trial(
        task_id=row['task_id'], harness=harness, reward=reward, status=status,
        agent_error_type=_text(row.get('agent_error_type')),
        verifier_error_type=_text(row.get('verifier_error_type')),
        model_requests=_int(row.get('model_requests')),
        accepted_responses=_int(row.get('accepted_model_responses')),
        http_429_requests=_int(row.get('http_429_requests')),
        unknown_cost_requests=_int(row.get('unknown_cost_requests')),
        known_cost_usd=_decimal(row.get('known_cost_usd')),
        total_cost_usd=_decimal(row.get('total_cost_usd')),
        known_input_tokens=_int(row.get('known_input_tokens')),
        known_output_tokens=_int(row.get('known_output_tokens')),
        input_tokens=_int(row.get('input_tokens')),
        output_tokens=_int(row.get('output_tokens')),
        setup_seconds=_float(row.get('setup_seconds')),
        agent_seconds=_float(row.get('agent_seconds')),
        verifier_seconds=_float(row.get('verifier_seconds')),
    )


def load_csv(path: Path, harness: str, harness_filter: str | None = None) -> dict[str, Trial]:
    """Return trials keyed by task_id. Duplicate task IDs are an error, not overwritten."""
    trials: dict[str, Trial] = {}
    with open(path, newline='') as handle:
        for row in csv.DictReader(handle):
            if harness_filter is not None and row.get('harness') != harness_filter:
                continue
            trial = parse_row(row, harness)
            if trial.task_id in trials:
                raise ValueError(f'Duplicate task {trial.task_id} for {harness} in {path}')
            trials[trial.task_id] = trial
    return trials


def find_root(start: Path | None = None) -> Path:
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / RESULTS).is_dir():
            return candidate
    raise FileNotFoundError(f'Could not find {RESULTS} above {here}')


def load_group(group: dict[str, tuple[str, str | None]], root: Path | None = None) -> dict[str, dict[str, Trial]]:
    base = (root or find_root()) / RESULTS
    return {name: load_csv(base / relative, name, harness_filter)
            for name, (relative, harness_filter) in group.items()}


def load_recovery(root: Path | None = None) -> dict[str, Trial]:
    return load_csv((root or find_root()) / RESULTS / RECOVERY, 'C0-NC recovery')

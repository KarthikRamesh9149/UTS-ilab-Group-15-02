"""Scores, paired comparisons, exact McNemar tests and paired bootstrap intervals."""
from __future__ import annotations

from dataclasses import dataclass
from math import comb
import random

from saranya_analysis.load import Trial


@dataclass(frozen=True)
class Score:
    harness: str
    intended: int
    valid: int
    passed: int

    @property
    def pass_rate_intended(self) -> float:
        """Passes over all intended tasks; a missing verifier outcome counts as not passed."""
        return self.passed / self.intended

    @property
    def pass_rate_valid(self) -> float | None:
        return self.passed / self.valid if self.valid else None

    @property
    def coverage(self) -> float:
        return self.valid / self.intended


def score(harness: str, trials: dict[str, Trial], intended: list[str]) -> Score:
    missing = [task for task in intended if task not in trials]
    if missing:
        raise ValueError(f'{harness} has no row for {missing}')
    rows = [trials[task] for task in intended]
    return Score(harness, len(intended), sum(t.valid for t in rows), sum(t.passed for t in rows))


@dataclass(frozen=True)
class Paired:
    a: str
    b: str
    both: int
    only_a: int
    only_b: int
    neither: int
    a_missing: list[str]  # tasks where A has no verifier outcome
    b_missing: list[str]

    @property
    def discordant(self) -> tuple[int, int]:
        return self.only_a, self.only_b


def paired(a_name: str, a: dict[str, Trial], b_name: str, b: dict[str, Trial], intended: list[str]) -> Paired:
    """Count task-level agreement over tasks where both have a verifier outcome.

    Tasks missing an outcome on either side are listed, not silently dropped.
    """
    both = only_a = only_b = neither = 0
    a_missing, b_missing = [], []
    for task in intended:
        x, y = a[task], b[task]
        if not x.valid:
            a_missing.append(task)
        if not y.valid:
            b_missing.append(task)
        if not (x.valid and y.valid):
            continue
        if x.passed and y.passed:
            both += 1
        elif x.passed:
            only_a += 1
        elif y.passed:
            only_b += 1
        else:
            neither += 1
    return Paired(a_name, b_name, both, only_a, only_b, neither, a_missing, b_missing)


def mcnemar_exact(only_a: int, only_b: int) -> float:
    """Two-sided exact McNemar p-value: a binomial test of the discordant pairs at p = 0.5."""
    n = only_a + only_b
    if n == 0:
        return 1.0
    tail = sum(comb(n, k) for k in range(min(only_a, only_b) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def outcome_vector(trials: dict[str, Trial], intended: list[str]) -> list[int]:
    """1 for a pass, 0 otherwise. A missing verifier outcome counts as not passed."""
    return [1 if trials[task].passed else 0 for task in intended]


@dataclass(frozen=True)
class Interval:
    difference: float
    low: float
    high: float
    resamples: int
    seed: int


def bootstrap_difference(a: list[int], b: list[int], *, resamples: int = 10_000, seed: int = 42) -> Interval:
    """Percentile 95% interval for mean(a) - mean(b), resampling whole tasks.

    The same task indices are drawn for both harnesses, so the pairing is kept.
    """
    if len(a) != len(b) or not a:
        raise ValueError('Paired outcome vectors must be non-empty and the same length')
    n = len(a)
    generator = random.Random(seed)
    population = range(n)
    differences = []
    for _ in range(resamples):
        indices = generator.choices(population, k=n)
        differences.append(sum(a[i] - b[i] for i in indices) / n)
    differences.sort()
    low = differences[int(0.025 * resamples)]
    high = differences[int(0.975 * resamples) - 1]
    return Interval((sum(a) - sum(b)) / n, low, high, resamples, seed)

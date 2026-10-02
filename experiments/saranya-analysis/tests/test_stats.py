import pytest

from conftest import TASKS
from saranya_analysis.stats import bootstrap_difference, mcnemar_exact, outcome_vector, paired, score


def test_score_keeps_missing_in_denominator(custom):
    s = score('C0-NC', custom, TASKS)
    assert (s.passed, s.valid, s.intended) == (2, 3, 4)
    assert s.pass_rate_intended == 0.5
    assert s.pass_rate_valid == pytest.approx(2 / 3)
    assert s.coverage == 0.75


def test_score_requires_every_intended_task(custom):
    with pytest.raises(ValueError, match='no row'):
        score('C0-NC', custom, TASKS + ['task-z'])


def test_paired_table(custom, terminus, openhands):
    # C0-NC: a pass, b fail, c pass, d missing. Terminus: a pass, b fail, c pass, d fail.
    p = paired('C0-NC', custom, 'Terminus-2', terminus, TASKS)
    assert (p.both, p.only_a, p.only_b, p.neither) == (2, 0, 0, 1)
    assert p.a_missing == ['task-d'] and p.b_missing == []
    # OpenHands: a pass, b pass, c fail, d fail.
    q = paired('C0-NC', custom, 'OpenHands', openhands, TASKS)
    assert (q.both, q.only_a, q.only_b, q.neither) == (1, 1, 1, 0)
    assert q.both + q.only_a + q.only_b + q.neither + len(q.a_missing) == len(TASKS)


@pytest.mark.parametrize('only_a, only_b, expected', [
    (0, 0, 1.0),
    (8, 8, 1.0),
    (0, 5, 2 / 32),  # 2 * P(X <= 0), X ~ Binomial(5, 0.5)
    (1, 9, 22 / 1024),  # 2 * (1 + 10) / 2**10
    (9, 1, 22 / 1024),  # symmetric
    (3, 4, 1.0),  # capped at 1
])
def test_mcnemar_exact(only_a, only_b, expected):
    assert mcnemar_exact(only_a, only_b) == pytest.approx(expected)


def test_outcome_vector_counts_missing_as_not_passed(custom):
    assert outcome_vector(custom, TASKS) == [1, 0, 1, 0]


def test_bootstrap_is_deterministic_with_seed():
    a = [1, 0, 1, 1, 0, 1, 0, 1, 1, 0]
    b = [1, 1, 0, 1, 0, 0, 0, 1, 0, 0]
    first = bootstrap_difference(a, b, resamples=2000, seed=42)
    second = bootstrap_difference(a, b, resamples=2000, seed=42)
    other = bootstrap_difference(a, b, resamples=2000, seed=7)
    assert first == second
    assert (first.low, first.high) != (other.low, other.high)
    assert first.difference == pytest.approx(0.2)
    assert first.low <= first.difference <= first.high


def test_bootstrap_identical_outcomes_give_zero_interval():
    a = [1, 0, 1, 0]
    interval = bootstrap_difference(a, list(a), resamples=500, seed=42)
    assert (interval.difference, interval.low, interval.high) == (0.0, 0.0, 0.0)


def test_bootstrap_rejects_unpaired_vectors():
    with pytest.raises(ValueError):
        bootstrap_difference([1, 0], [1], resamples=10)

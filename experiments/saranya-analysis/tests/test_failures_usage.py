from decimal import Decimal

import pytest

from saranya_analysis.failures import categorise, failure_counts, passes_with_agent_error
from saranya_analysis.load import parse_row
from saranya_analysis.usage import usage


def trial(**fields):
    row = {'task_id': 't', 'reward': '0', 'agent_error_type': '', 'http_429_requests': '0'}
    row.update(fields)
    return parse_row(row, 'H')


@pytest.mark.parametrize('fields, category', [
    ({'agent_error_type': 'TimeoutError'}, 'timeout'),
    ({'agent_error_type': 'TimeoutError', 'http_429_requests': '3'}, 'rate limit'),
    ({'agent_error_type': 'APIError', 'http_429_requests': '1'}, 'rate limit'),
    ({'agent_error_type': 'APIError'}, 'needs review'),
    ({}, 'verifier fail'),
    ({'reward': '', 'status': 'setup_failed', 'agent_error_type': 'RuntimeError'}, 'setup error'),
    ({'reward': '', 'status': 'unknown_state'}, 'needs review'),
    ({'agent_error_type': 'NetworkConnectionError'}, 'needs review'),
    ({'agent_error_type': 'OpenAIPermissionDeniedError', 'http_429_requests': '9'}, 'needs review'),
    ({'agent_error_type': 'SomethingNew'}, 'needs review'),
    ({'verifier_error_type': 'VerifierTimeoutError'}, 'needs review'),
])
def test_categories(fields, category):
    assert categorise(trial(**fields))[0] == category


def test_review_note_keeps_recorded_exception():
    category, note = categorise(trial(agent_error_type='SomethingNew'))
    assert category == 'needs review' and 'SomethingNew' in note


def test_passes_are_not_categorised():
    with pytest.raises(ValueError):
        categorise(trial(reward='1'))


def test_fixture_counts(terminus, openhands, custom):
    assert failure_counts(terminus) == {'rate limit': 1, 'verifier fail': 1}
    # task-c NetworkConnectionError needs review; task-d APIError with 2 HTTP 429s is a rate limit.
    assert failure_counts(openhands) == {'needs review': 1, 'rate limit': 1}
    assert failure_counts(custom) == {'needs review': 1, 'setup error': 1}
    assert passes_with_agent_error(terminus) == 1


def test_usage_counts_unknowns_and_never_zero_fills(terminus, custom):
    u = usage('Terminus-2', terminus)
    assert u.unknown_cost_requests == 4
    assert u.known_cost_usd == Decimal('0.0036')
    assert not u.total_cost_known
    assert u.trials_with_complete_tokens == 3
    c = usage('C0-NC', custom)
    assert c.trials_with_agent_time == 3  # the setup failure has no agent time, not zero
    assert c.agent_seconds_total == pytest.approx(1385.0)

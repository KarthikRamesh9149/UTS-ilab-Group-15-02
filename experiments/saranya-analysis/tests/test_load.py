from decimal import Decimal

import pytest

from conftest import FIXTURES
from saranya_analysis.load import load_csv, parse_row


def test_harness_filter_and_values(terminus):
    assert sorted(terminus) == ['task-a', 'task-b', 'task-c', 'task-d']
    a = terminus['task-a']
    assert (a.reward, a.status, a.passed, a.valid) == (1, 'verified', True, True)
    assert a.known_cost_usd == Decimal('0.0010')
    assert a.agent_error_type is None


def test_blank_fields_stay_unknown(terminus):
    b = terminus['task-b']
    assert b.total_cost_usd is None
    assert b.input_tokens is None and b.output_tokens is None
    assert b.unknown_cost_requests == 4


def test_setup_failure_has_no_reward(custom):
    d = custom['task-d']
    assert d.reward is None and d.status == 'setup_failed'
    assert not d.valid and not d.passed
    assert d.agent_seconds is None


def test_duplicate_task_is_rejected(tmp_path):
    path = tmp_path / 'dup.csv'
    path.write_text('task_id,harness,reward\nx,h,1\nx,h,0\n')
    with pytest.raises(ValueError, match='Duplicate'):
        load_csv(path, 'H')


def test_non_binary_reward_is_rejected():
    with pytest.raises(ValueError, match='non-binary'):
        parse_row({'task_id': 'x', 'reward': '0.5'}, 'H')


def test_status_must_agree_with_reward():
    with pytest.raises(ValueError, match='disagrees'):
        parse_row({'task_id': 'x', 'reward': '', 'status': 'verified'}, 'H')
    with pytest.raises(ValueError, match='disagrees'):
        parse_row({'task_id': 'x', 'reward': '1', 'status': 'setup_failed'}, 'H')


def test_fixture_files_exist():
    assert (FIXTURES / 'baseline_trials.csv').exists()

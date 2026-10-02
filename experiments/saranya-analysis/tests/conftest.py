from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from saranya_analysis.load import load_csv  # noqa: E402

FIXTURES = Path(__file__).parent / 'fixtures'
TASKS = ['task-a', 'task-b', 'task-c', 'task-d']


@pytest.fixture
def terminus():
    return load_csv(FIXTURES / 'baseline_trials.csv', 'Terminus-2', 'terminus-2')


@pytest.fixture
def openhands():
    return load_csv(FIXTURES / 'baseline_trials.csv', 'OpenHands', 'openhands')


@pytest.fixture
def custom():
    return load_csv(FIXTURES / 'custom_trials.csv', 'C0-NC')

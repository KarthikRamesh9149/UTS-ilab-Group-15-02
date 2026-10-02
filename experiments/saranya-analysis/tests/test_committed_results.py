"""Regression checks against the committed Stage 2 results and their published figures.

Skipped when the repository's stage2/results directory is not present.
"""
from pathlib import Path

import pytest

from saranya_analysis.load import DEV20, DEV20_REFERENCE, FULL89, find_root, load_group
from saranya_analysis.report import build

try:
    ROOT = find_root()
except FileNotFoundError:
    ROOT = None

pytestmark = pytest.mark.skipif(ROOT is None, reason='stage2/results not available')


def test_published_scores():
    full = load_group(FULL89, ROOT)
    assert {k: sum(t.passed for t in v.values()) for k, v in full.items()} == \
        {'Terminus-2': 52, 'OpenHands': 44, 'C0-NC': 50}
    assert sum(t.valid for t in full['C0-NC'].values()) == 86
    dev = load_group({**DEV20, **DEV20_REFERENCE}, ROOT)
    assert [sum(t.passed for t in v.values()) for v in dev.values()] == [15, 14, 14, 13, 14, 10]


def test_report_builds_and_is_deterministic():
    first = build(ROOT)
    assert first == build(ROOT)
    assert '| C0-NC vs Terminus-2 | 42 | 8 | 8 | 28 | 3 | 1.000 |' in first


def test_readme_tables_match_generated_report():
    readme = (Path(__file__).resolve().parents[1] / 'README.md').read_text()
    rows = [line for line in build(ROOT).splitlines() if line.startswith('| ')]
    missing = [line for line in rows if line not in readme]
    assert not missing, f'README is out of date; regenerate tables. First stale row: {missing[0]}'

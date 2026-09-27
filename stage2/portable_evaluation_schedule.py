"""Exact post-development schedules. No execution, admission or file writes."""
import hashlib

from portable_candidate_freeze import validate_document
from portable_custom_policy import fingerprint

MANIFEST_SHA256 = '8bf5271d51eb4306c5fadadf8beee58edd70f595c404223768e39949cca81571'
PHASES = ('confirmation', 'diagnostic', 'final')


def _cell(phase, index, task, role, harness, parent):
    prefix = {'confirmation': 'customconfirm1', 'diagnostic': 'customdiagnostic1',
              'final': 'customfinal1'}[phase]
    return dict(trial_id=f'{prefix}-{role}-{index:02d}-{task}',
        task_id=task, stage='final' if phase == 'final' else 'development',
        phase=phase, role=role, harness=harness, parent=parent)


def schedule(document, manifest, phase):
    """Keep confirmation/diagnostics separate from the fresh custom 89 score."""
    selection = validate_document(document)
    if not isinstance(manifest, dict) or fingerprint(manifest) != MANIFEST_SHA256:
        raise ValueError('The unchanged full input manifest is required')
    if phase not in PHASES:
        raise ValueError('Explicit registered evaluation phase required')
    development = manifest['development_ids']
    condition, parent = selection['selected'], selection['custom_parent']
    cells = []
    if phase == 'confirmation':
        roles = ['terminus-2', 'openhands', 'custom']
        for index, task in enumerate(development, 1):
            offset = (index - 1) % len(roles)
            for role in roles[offset:] + roles[:offset]:
                cells.append(_cell(phase, index, task, role,
                    condition if role == 'custom' else role,
                    parent if role == 'custom' else None))
    elif phase == 'diagnostic':
        diagnostic = selection['diagnostic']
        cells = [_cell(phase, index, task, 'custom', diagnostic['condition'], diagnostic['parent'])
                 for index, task in enumerate(development, 1)]
    else:
        outside = sorted(manifest['outside_development_ids'], key=lambda task: (
            hashlib.sha256(('uts-stage2-dev20-v1:42:' + task).encode()).hexdigest(), task))
        cells = [_cell(phase, index, task, 'custom', condition, parent)
                 for index, task in enumerate(development + outside, 1)]
    return dict(kind='portable_evaluation_schedule_not_admission', phase=phase,
        candidate_sha256=fingerprint(document), manifest_sha256=MANIFEST_SHA256,
        intended=len(cells), cells=cells, primary_comparator='terminus-2',
        secondary_comparator='openhands', parallel_trials=1,
        attempts_per_registered_cell=1, automatic_task_replay=False,
        official_task_limits_unchanged=True,
        diagnostic_kind=selection['diagnostic']['kind'] if phase == 'diagnostic' else None,
        paid_launch_ready=False, full_benchmark_win_claimed=False)


def validate_schedule(value, document, manifest):
    if not isinstance(value, dict):
        raise ValueError('Exact evaluation schedule required')
    expected = schedule(document, manifest, value.get('phase'))
    if fingerprint(value) != fingerprint(expected):
        raise ValueError('Evaluation scope, candidate, order or attempt identity changed')
    return expected

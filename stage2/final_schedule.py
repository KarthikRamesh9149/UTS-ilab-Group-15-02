"""Fresh final cells with deterministic task ordering and rotated harness order."""
import re


def schedule(task_ids, *, custom_condition, custom_parent=None):
    if len(task_ids) != 89 or len(set(task_ids)) != 89:
        raise ValueError('Exactly 89 unique benchmark tasks required')
    if any(not isinstance(task, str) or not re.fullmatch(r'[a-z0-9][a-z0-9.-]{0,90}', task) for task in task_ids):
        raise ValueError('Unsafe task identity')
    if custom_condition not in {'C0', 'C1', 'C2'}:
        raise ValueError('Registered frozen custom condition required')
    if (custom_condition == 'C2' and custom_parent not in {'C0', 'C1'}) or (custom_condition != 'C2' and custom_parent is not None):
        raise ValueError('Invalid frozen parent')
    roles = ['terminus-2', 'openhands', 'custom']
    cells = []
    for index, task in enumerate(sorted(task_ids)):
        offset = index % 3
        for role in roles[offset:] + roles[:offset]:
            cells.append({'trial_id': f'final-{role}-{index:02d}-{task}',
                          'task_id': task, 'stage': 'final', 'role': role,
                          'harness': custom_condition if role == 'custom' else role,
                          'parent': custom_parent if role == 'custom' else None})
    return cells

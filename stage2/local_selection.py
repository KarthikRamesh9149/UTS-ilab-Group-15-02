"""Outcome-independent protocol and outcome-based dev selection stay separate."""
import math

VARIANTS = ('C0', 'C1', 'C2', 'C3', 'C4')


def validate_block(records, task_ids, *, harness, protocol_sha256):
    if len(task_ids) != 20 or len(set(task_ids)) != 20:
        raise ValueError('Frozen development set required')
    if len(records) != 20 or {r['task_id'] for r in records} != set(task_ids):
        raise ValueError('Missing/duplicate/unexpected development tasks')
    for row in records:
        if row.get('harness') != harness or row.get('protocol_sha256') != protocol_sha256:
            raise ValueError('Different harness or protocol')
        if row.get('stage') != 'development' or row.get('repetition') != 0:
            raise ValueError('Do not mix development with confirmation/final outcomes')
        if row.get('infrastructure_valid') is not True or row.get('cleanup_verified') is not True:
            raise ValueError('Infrastructure/cleanup evidence missing')
        if type(row.get('reward')) not in (int, float) or row['reward'] not in (0, 1):
            raise ValueError('Binary official verifier reward required')
        if type(row.get('output_tokens')) is not int or row['output_tokens'] < 0:
            raise ValueError('Observed token usage required')
        value = row.get('agent_seconds')
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError('Observed agent runtime required')
    return records


def choose(blocks, task_ids, *, protocol_sha256, retained_features):
    if not blocks or set(blocks) != set(retained_features) or not set(blocks) <= set(VARIANTS):
        raise ValueError('Unregistered variant or missing complexity record')
    scores = {}
    for harness, records in blocks.items():
        validate_block(records, task_ids, harness=harness, protocol_sha256=protocol_sha256)
        features = retained_features[harness]
        if type(features) is not int or not 0 <= features <= 4:
            raise ValueError('Invalid retained feature count')
        scores[harness] = (-sum(r['reward'] for r in records), sum(r['output_tokens'] for r in records),
                           features, sum(r['agent_seconds'] for r in records), harness)
    winner = min(scores, key=scores.get)
    return {'selected': winner, 'ranking': sorted(scores, key=scores.get),
            'selection_only_not_confirmed_win': True}

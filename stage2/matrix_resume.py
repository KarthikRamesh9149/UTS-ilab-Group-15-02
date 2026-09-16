"""Read and reaudit completed cells; never replay an existing attempt."""
import json
from pathlib import Path
import re

from scored_accounting import audit_trial


def completed_cell(root, cell, settings):
    identifier = cell['trial_id']
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', identifier):
        raise ValueError('Invalid trial identity')
    if cell['stage'] not in {'development', 'final'} or cell['harness'] not in {'terminus-2', 'openhands', 'C0', 'C1', 'C2'}:
        raise ValueError('Unregistered cell')
    if (cell['harness'] == 'C2' and cell.get('parent') not in {'C0', 'C1'}) or (cell['harness'] != 'C2' and cell.get('parent') is not None):
        raise ValueError('Invalid custom parent')
    runtime = Path(root) / '.runtime/stage2'
    attempt = runtime / 'scored-trials' / identifier
    if attempt.is_symlink():
        raise ValueError('Unsafe attempt path')
    if not attempt.exists():
        return None
    path = attempt / 'result.json'
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Interrupted attempt requires audit, not replay: ' + identifier)
    result = json.loads(path.read_text())
    if any(result.get(key) != cell[key] for key in ('trial_id', 'task_id', 'stage', 'harness')):
        raise ValueError('Existing attempt identity mismatch')
    if result.get('model_protocol_sha256') != settings.fingerprint():
        raise ValueError('Existing attempt model protocol mismatch')
    if cell['harness'] == 'C2' and (result.get('agent_context') or {}).get('metadata', {}).get('custom_parent') != cell.get('parent'):
        raise ValueError('Existing custom parent mismatch')
    if result.get('status') != 'verified' or not all(result.get(key) is True for key in
            ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
        raise RuntimeError('Unverified attempt requires inspection, not replay: ' + identifier)
    reward = (result.get('verifier_result') or {}).get('rewards', {}).get('reward')
    if type(reward) not in (int, float) or reward not in (0, 1):
        raise ValueError('Completed cell lacks a binary verifier reward')
    result['billing'] = audit_trial(runtime, identifier, cell['stage'])
    if result['billing'].get('billing_verified') is not True or result['billing'].get('model_protocol_sha256') != settings.fingerprint():
        raise RuntimeError('Billing not verified; cell cannot be resumed')
    return result

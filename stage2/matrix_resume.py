"""Read and reaudit completed cells; never replay an existing attempt."""
from copy import deepcopy
import json
from pathlib import Path
import re

from scored_accounting import audit_trial
from historical_hold import validate_historical_hold


HELD_TERMINAL = 'historical_accounting_hold_terminal'


def _held_view(result, hold):
    """Annotate the immutable failure without inventing complete billing."""
    if (result.get('status') != 'billing_unresolved'
            or (result.get('billing') or {}).get('billing_verified') is not False
            or type((result.get('verifier_result') or {}).get('rewards', {}).get('reward')) not in (int, float)
            or result['verifier_result']['rewards']['reward'] != 0):
        raise ValueError('Historical hold must retain the original unresolved zero')
    if not all(result.get(key) is True for key in
               ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
        raise ValueError('Historical hold cleanup or revocation unverified')
    if any(result.get(key) != hold[key] for key in
           ('trial_id', 'task_id', 'stage', 'harness', 'model_protocol_sha256')):
        raise ValueError('Historical hold identity mismatch')
    view = deepcopy(result)
    view['resume_disposition'] = HELD_TERMINAL
    view['historical_hold_sha256'] = hold['sidecar_sha256']
    view['original_result_sha256'] = hold['original_result_sha256']
    view['billing'].update(billing_verified=False, accounting_bounded=True,
        model_protocol_sha256=hold['model_protocol_sha256'],
        charged_usd=None, prompt_tokens=None, completion_tokens=None, requests=None,
        budget_stop_count=hold['budget_stop_count'],
        budget_stop_classification=hold['budget_stop_classification'],
        capacity_budget_stop_count=hold['capacity_budget_stop_count'],
        retained_reservation_nanodollars=hold['reserved_nanodollars'])
    return view


def validated_held_cell(runtime, row, protocol_sha256):
    """Only the exact evidence-bound historical view can use the amendment."""
    if row.get('resume_disposition') != HELD_TERMINAL:
        return None
    if runtime is None:
        raise ValueError('Historical hold requires canonical runtime evidence')
    runtime = Path(runtime)
    hold = validate_historical_hold(runtime)
    if hold is None or hold['model_protocol_sha256'] != protocol_sha256:
        raise ValueError('Historical hold missing or model protocol changed')
    original = json.loads((runtime / 'scored-trials' / hold['trial_id'] / 'result.json').read_text())
    if json.dumps(row, sort_keys=True) != json.dumps(_held_view(original, hold), sort_keys=True):
        raise ValueError('Historical held result view differs from immutable evidence')
    return hold


def completed_cell(root, cell, settings):
    identifier = cell['trial_id']
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', identifier):
        raise ValueError('Invalid trial identity')
    if cell['stage'] not in {'development', 'final'} or cell['harness'] not in {'terminus-2', 'openhands', 'C0', 'C1', 'C2'}:
        raise ValueError('Unregistered cell')
    if (cell['harness'] == 'C2' and cell.get('parent') not in {'C0', 'C1'}) or (cell['harness'] != 'C2' and cell.get('parent') is not None):
        raise ValueError('Invalid custom parent')
    runtime = Path(root) / '.runtime/stage2'
    hold = validate_historical_hold(runtime)
    if hold is not None:
        if hold['model_protocol_sha256'] != settings.fingerprint():
            raise ValueError('Historical hold model protocol mismatch')
        same_cell = all(cell.get(key) == hold[key] for key in ('task_id', 'stage', 'harness'))
        if same_cell and identifier != hold['trial_id']:
            raise ValueError('Historical held cell cannot be replayed under a substitute trial identity')
    attempt = runtime / 'scored-trials' / identifier
    if attempt.is_symlink():
        raise ValueError('Unsafe attempt path')
    if not attempt.exists():
        if hold is not None and identifier == hold['trial_id']:
            raise ValueError('Historical held attempt is missing; replay forbidden')
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
    if hold is not None and identifier == hold['trial_id']:
        return _held_view(result, hold)
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

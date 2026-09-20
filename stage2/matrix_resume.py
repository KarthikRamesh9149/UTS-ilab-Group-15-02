"""Read and reaudit completed cells; never replay an existing attempt."""
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re

from scored_accounting import audit_trial
from historical_hold import hold_entries, hold_for_trial, validate_historical_hold
from deferred_billing import validate_deferrals, validate_terminal_deferral


HELD_TERMINAL = 'historical_accounting_hold_terminal'
DEFERRED_TERMINAL = 'billing_deferred_terminal'


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
    registry = validate_historical_hold(runtime)
    if registry is None or registry['model_protocol_sha256'] != protocol_sha256:
        raise ValueError('Historical hold missing or model protocol changed')
    hold = hold_for_trial(registry, row.get('trial_id'))
    if hold is None:
        raise ValueError('Historical held trial is not registered')
    raw = (runtime / 'scored-trials' / hold['trial_id'] / 'result.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != hold['original_result_sha256']:
        raise ValueError('Historical result changed after validation')
    original = json.loads(raw)
    if json.dumps(row, sort_keys=True) != json.dumps(_held_view(original, hold), sort_keys=True):
        raise ValueError('Historical held result view differs from immutable evidence')
    return hold


def _deferred_view(result, entry):
    """Keep the official terminal outcome and explicitly unknown full billing."""
    reward = (result.get('verifier_result') or {}).get('rewards', {}).get('reward')
    if (result.get('status') != 'billing_unresolved'
            or (result.get('billing') or {}).get('billing_verified') is not False
            or type(reward) not in (int, float) or reward not in (0, 1)):
        raise ValueError('Billing deferral requires an unresolved binary terminal outcome')
    if (not all(result.get(key) is True for key in
                ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed'))
            or result.get('cleanup_errors') or result.get('verifier_error_type')):
        raise ValueError('Deferred trial cleanup, revocation or verifier unverified')
    if any(result.get(key) != entry[key] for key in
           ('trial_id', 'task_id', 'stage', 'harness', 'model_protocol_sha256')):
        raise ValueError('Deferred trial identity mismatch')
    view = deepcopy(result)
    view.update(resume_disposition=DEFERRED_TERMINAL, billing_deferred=True,
                deferred_billing_sha256=entry['sidecar_sha256'],
                billing_deferral_policy_sha256=entry['policy_sha256'],
                original_result_sha256=entry['result_sha256'])
    view['billing'].update(billing_verified=False, accounting_bounded=True,
        model_protocol_sha256=entry['model_protocol_sha256'],
        charged_usd=None, prompt_tokens=None, completion_tokens=None, requests=None,
        known_billed_subtotal_usd=str(Decimal(entry['known_charged_nanodollars']) / 1_000_000_000),
        budget_stop_count=entry['budget_stop_count'],
        retained_reservation_nanodollars=entry['retained_liability_nanodollars'],
        hard_reserved_nanodollars=entry['reserved_nanodollars'])
    return view


def validated_deferred_cell(runtime, row, protocol_sha256):
    """Revalidate the registration and exact derived view, never trust flags."""
    if row.get('resume_disposition') != DEFERRED_TERMINAL:
        return None
    identifier = row.get('trial_id')
    if runtime is None or not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', identifier):
        raise ValueError('Deferred billing requires canonical runtime and trial identity')
    path = Path(runtime) / 'scored-trials' / identifier / 'result.json'
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise ValueError('Deferred terminal result missing or unsafe')
    raw = path.read_bytes()
    original = json.loads(raw)
    entry = validate_terminal_deferral(runtime, identifier, original)
    if entry is None or entry['model_protocol_sha256'] != protocol_sha256:
        raise ValueError('Deferred billing registration missing or model changed')
    if hashlib.sha256(raw).hexdigest() != entry['result_sha256']:
        raise ValueError('Deferred terminal result changed after validation')
    if json.dumps(row, sort_keys=True) != json.dumps(_deferred_view(original, entry), sort_keys=True):
        raise ValueError('Deferred billing result view differs from immutable evidence')
    return entry


def completed_cell(root, cell, settings):
    identifier = cell['trial_id']
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', identifier):
        raise ValueError('Invalid trial identity')
    if cell['stage'] not in {'development', 'final'} or cell['harness'] not in {'terminus-2', 'openhands', 'C0', 'C1', 'C2'}:
        raise ValueError('Unregistered cell')
    if (cell['harness'] == 'C2' and cell.get('parent') not in {'C0', 'C1'}) or (cell['harness'] != 'C2' and cell.get('parent') is not None):
        raise ValueError('Invalid custom parent')
    runtime = Path(root) / '.runtime/stage2'
    registry = validate_historical_hold(runtime)
    deferred = validate_deferrals(runtime)
    if registry is not None:
        if registry['model_protocol_sha256'] != settings.fingerprint():
            raise ValueError('Historical hold model protocol mismatch')
    for hold in hold_entries(registry):
        same_cell = all(cell.get(key) == hold[key] for key in ('task_id', 'stage', 'harness'))
        if same_cell and identifier != hold['trial_id']:
            raise ValueError('Historical held cell cannot be replayed under a substitute trial identity')
    for entry in deferred:
        if entry['model_protocol_sha256'] != settings.fingerprint():
            raise ValueError('Deferred billing model protocol mismatch')
        same_cell = all(cell.get(key) == entry[key] for key in ('task_id', 'stage', 'harness'))
        if same_cell and identifier != entry['trial_id']:
            raise ValueError('Deferred terminal cell cannot be replayed under a substitute trial identity')
    hold = hold_for_trial(registry, identifier)
    attempt = runtime / 'scored-trials' / identifier
    if attempt.is_symlink():
        raise ValueError('Unsafe attempt path')
    if not attempt.exists():
        if hold is not None or any(entry['trial_id'] == identifier for entry in deferred):
            raise ValueError('Historical held attempt is missing; replay forbidden')
        return None
    path = attempt / 'result.json'
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('Interrupted attempt requires audit, not replay: ' + identifier)
    raw = path.read_bytes()
    if hold is not None and hashlib.sha256(raw).hexdigest() != hold['original_result_sha256']:
        raise ValueError('Historical result changed after validation')
    result = json.loads(raw)
    if any(result.get(key) != cell[key] for key in ('trial_id', 'task_id', 'stage', 'harness')):
        raise ValueError('Existing attempt identity mismatch')
    if result.get('model_protocol_sha256') != settings.fingerprint():
        raise ValueError('Existing attempt model protocol mismatch')
    if cell['harness'] == 'C2' and (result.get('agent_context') or {}).get('metadata', {}).get('custom_parent') != cell.get('parent'):
        raise ValueError('Existing custom parent mismatch')
    if hold is not None:
        return _held_view(result, hold)
    entry = validate_terminal_deferral(runtime, identifier, result)
    if entry is not None:
        if hashlib.sha256(raw).hexdigest() != entry['result_sha256']:
            raise ValueError('Deferred terminal result changed after validation')
        return _deferred_view(result, entry)
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

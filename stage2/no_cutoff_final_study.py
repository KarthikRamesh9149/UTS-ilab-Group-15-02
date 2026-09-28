"""Locked host admission for the measured C0-NC finalist's exact final89.

The dispatcher freshly authenticates the completed 100-outcome lineage before
taking ancestor locks. Under those locks this module rechecks its bytes and
the real final qualification. Saved metadata alone is not dispatch authority.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
import math
from pathlib import Path

import no_cutoff_final_evidence as evidence
import no_cutoff_final_policy as policy
import no_cutoff_final_runtime as runtime_identity
from credit_only_accounting import summarise as billing_summary
from credit_only_experiment import coverage, cleanup_complete, digest
from custom_dispatch_stop import BoundaryStop
from no_cutoff_custom_contract import EXECUTION_POLICY_VERSION
from retry_runtime import private_read
from scored_gateway import durable_json, private_directory

_DISPATCH = ContextVar('no_cutoff_final_dispatch', default=None)


def read_candidate(root):
    document = private_read(Path(root) / '.runtime/stage2' / policy.CANDIDATE_FILE)
    policy.candidate_execution(document)
    return document


def qualified(root):
    """Under-lock verification, not a substitute for fresh authentication."""
    rt = Path(root) / '.runtime/stage2'
    if BoundaryStop(rt).requested():
        raise ValueError('Persistent operator stop forbids final admission')
    policy.require_policy(rt)
    document = read_candidate(root)
    manifest = private_read(rt / policy.MANIFEST_FILE)
    authenticated = private_read(rt / policy.AUTHENTICATION_FILE)
    proof = policy.validate_qualification(document, manifest, private_read(rt / policy.QUALIFICATION_FILE))
    if policy.fingerprint(authenticated) != proof['finalist_authentication_sha256']:
        raise ValueError('Final qualification authentication binding changed')
    evidence.recheck(root, document, authenticated)
    runtime_identity.verify_current(root, document, proof, private_read(rt / policy.RUNTIME_FILE))
    return proof


def audited(root):
    rt = Path(root) / '.runtime/stage2'
    path = rt / policy.REGISTRATION_FILE
    block = policy.require_block(rt) if path.exists() or path.is_symlink() else None
    complete, partial = coverage(rt, block['cells'] if block else [])
    for name, result in complete.items():
        policy.require_trial(rt, name, 'final')
        proof = private_read(rt / policy.QUALIFICATION_FILE)
        expected = dict(stage='final', custom_study=policy.EXPERIMENT, harness=policy.CONDITION,
            model_revoked=True, custom_registration_sha256=policy.fingerprint(block),
            gateway_image_id=proof['gateway_image'], model_protocol_sha256=policy.SETTINGS.fingerprint(),
            accounting_mode='provider-credit-only')
        if any(policy.fingerprint(result.get(k)) != policy.fingerprint(v) for k, v in expected.items()):
            raise ValueError('Retained final outcome identity or revocation differs')
        if not cleanup_complete(result):
            raise ValueError('Retained final outcome needs cleanup')
        metadata = (result.get('agent_context') or {}).get('metadata', {})
        if metadata:
            actual = dict(custom_version=policy.CANDIDATE_VERSION, custom_condition=policy.CONDITION,
                custom_parent='C0', custom_base_parent=None, custom_design_lever=EXECUTION_POLICY_VERSION,
                custom_execution_contract=policy.execution_contract())
            if any(policy.fingerprint(metadata.get(k)) != policy.fingerprint(v) for k, v in actual.items()):
                raise ValueError('Executed final behaviour differs from the measured revision')
    return complete, partial


def register(root, authenticated):
    """One immutable matrix, called after the runner's fresh audit and locks."""
    rt = Path(root) / '.runtime/stage2'
    document = read_candidate(root)
    proof = qualified(root)
    evidence.recheck(root, document, authenticated)
    if policy.fingerprint(authenticated) != proof['finalist_authentication_sha256']:
        raise ValueError('Fresh finalist audit differs from qualified lineage')
    _, partial = audited(root)
    if partial:
        raise ValueError('Started final attempt cannot be replayed')
    block = policy.registration(document, private_read(rt / policy.MANIFEST_FILE), proof)
    path = rt / policy.REGISTRATION_FILE
    private_directory(rt)
    if path.exists() or path.is_symlink():
        if policy.fingerprint(private_read(path)) != policy.fingerprint(block):
            raise ValueError('Final89 registration is immutable')
    else:
        durable_json(path, block)
    policy.require_block(rt)
    return block


@contextmanager
def dispatch_permit(root, block, authenticated):
    """Internal scope after actual authenticate(), under all ancestor locks."""
    root = Path(root).resolve()
    evidence.recheck(root, read_candidate(root), authenticated)
    recorded = policy.require_block(root / '.runtime/stage2')
    if (policy.fingerprint(block) != policy.fingerprint(recorded)
            or block['finalist_authentication_sha256'] != policy.fingerprint(authenticated)):
        raise ValueError('Final dispatch must bind the fresh audit and exact registration')
    token = _DISPATCH.set((root, policy.fingerprint(block)))
    try:
        yield
    finally:
        _DISPATCH.reset(token)


def admit_trial(root, *, trial_id, task_id, stage, factory, settings, gateway_image, guard_image,
                setup_timeout_seconds):
    rt = Path(root) / '.runtime/stage2'
    block = policy.require_trial(rt, trial_id, stage)
    if _DISPATCH.get() != (Path(root).resolve(), policy.fingerprint(block)):
        raise ValueError('Use the freshly authenticated, locked C0-NC final dispatcher')
    proof = qualified(root)
    row = next(c for c in block['cells'] if c['trial_id'] == trial_id)
    expected = dict(harness=policy.CONDITION, custom_parent='C0', custom_base_parent=None,
        custom_version=policy.CANDIDATE_VERSION, custom_design_lever=EXECUTION_POLICY_VERSION,
        python_runtime_sha256=policy.PYTHON_SHA256, model_protocol_sha256=policy.SETTINGS.fingerprint())
    if (row['task_id'] != task_id or settings != policy.SETTINGS
            or any(getattr(factory, k, None) != v for k, v in expected.items())
            or gateway_image != proof['gateway_image'] or guard_image != proof['guard_image']
            or setup_timeout_seconds != proof['setup_timeout_seconds']
            or policy.fingerprint(proof) != block['qualification_sha256']):
        raise ValueError('Final factory, model, task or runtime differs from the measured finalist')
    return policy.fingerprint(block)


def require_task_image(root, task_id, actual_image):
    recorded = private_read(Path(root) / '.runtime/stage2' / policy.RUNTIME_FILE)
    row = recorded['task_inventory'].get(task_id)
    if not row or row['image_id'] != actual_image:
        raise ValueError('Started final container differs from its qualified original image')


def summary(root):
    rt = Path(root) / '.runtime/stage2'
    block = policy.require_block(rt)
    complete, partial = audited(root)
    rows = []
    for cell in block['cells']:
        name = cell['trial_id']
        if name not in complete:
            continue
        result = complete[name]
        reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Invalid final verifier result')
        seconds = result.get('phase_seconds', {}).get('agent')
        if seconds is not None and (type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0):
            raise ValueError('Invalid observed final runtime')
        bill = billing_summary(rt, name)
        rows.append(dict(cell, reward=reward, agent_seconds=seconds,
            result_sha256=digest(rt / 'scored-trials' / name / 'result.json'),
            **{k: bill[k] for k in ('requests', 'unknown_cost_requests', 'known_charged_usd', 'charged_usd')}))
    known = sum((Decimal(r['known_charged_usd']) for r in rows), Decimal(0))
    return dict(condition=policy.CONDITION, parent='C0', base_parent=None, intended=89,
        attempted=len(rows), passes=sum(r['reward'] == 1 for r in rows),
        failures=sum(r['reward'] == 0 for r in rows), no_verifier_result=sum(r['reward'] is None for r in rows),
        started_without_result=partial, known_charged_usd=str(known),
        charged_usd=str(known) if len(rows) == 89 and all(r['charged_usd'] is not None for r in rows) else None,
        unknown_cost_requests=sum(r['unknown_cost_requests'] for r in rows),
        agent_seconds=sum(r['agent_seconds'] for r in rows) if len(rows) == 89 and all(r['agent_seconds'] is not None for r in rows) else None,
        original_score_inherited=False, efficiency_win_claimed=False, full_benchmark_win_claimed=False,
        confirmation60_status='deferred_not_run', diagnostic20_status='deferred_not_run', rows=rows)

"""One fresh repeat of every failed timeout with a recorded HTTP 429.

This is a selected-failure diagnostic, never a replacement benchmark score or
a causal estimate. No task instructions, solutions or model text are analysed.
"""
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from credit_only_accounting import call_records
from credit_only_experiment import coverage, digest
from retry_policy import SETTINGS

EXPERIMENT = 'timeout-rate-limit-diagnostic-20260925'
PARENT = Path('/opt/uts-capstone-corrected-20260923')
DEPLOYMENT = Path('/opt/uts-capstone-timeout-diagnostic-20260925')
REGISTRATION = 'timeout-diagnostic-matrix.json'
QUALIFICATION = 'timeout-diagnostic-qualification.json'
EXPECTED = {'terminus-2': 11, 'openhands': 19}
ADDED = ('timeout_diagnostic.py', 'run_timeout_diagnostic.py', 'test_timeout_diagnostic.py')
POLICY = dict(experiment=EXPERIMENT, attempts_per_selected_cell=1, parallel_trials=1,
    selection='original reward zero AND agent TimeoutError AND recorded HTTP 429',
    model_protocol=SETTINGS.document(), official_time_and_resources='unchanged',
    api_retry_policy='unchanged; honour cooldown; no fallback or rate-limit bypass',
    original_scores_replaced=False, repeated_until_pass=False,
    custom_tuning_from_this_diagnostic=False, financial_caps=None, reserve_usd='0',
    automatic_top_up=False, engine_stage='final',
    reporting_scope='diagnostic only; engine stage permits the original 89-task manifest',
    interpretation='observed repeat recovery, not the unknowable outcome of the original run without delays')


def select(rows):
    """Select every eligible cell, with strict original-coverage validation."""
    if len(rows) != 178 or Counter(r['harness'] for r in rows) != {'terminus-2': 89, 'openhands': 89}:
        raise ValueError('Complete original 178-cell baseline required')
    keys = [(r['harness'], r['task_id']) for r in rows]
    if len(set(keys)) != 178 or len({r['trial_id'] for r in rows}) != 178:
        raise ValueError('Duplicate original identity')
    if any(type(r['reward']) is not int or r['reward'] not in (0, 1) for r in rows):
        raise ValueError('Binary original rewards required')
    if any(type(r['http_429_requests']) is not int or r['http_429_requests'] < 0 for r in rows):
        raise ValueError('Exact recorded rate-limit counts required')
    chosen = [r for r in rows if r['reward'] == 0 and r['agent_error_type'] == 'TimeoutError'
              and r['http_429_requests'] > 0]
    if Counter(r['harness'] for r in chosen) != EXPECTED:
        raise ValueError('The authorised cohort is exactly 11 Terminus and 19 OpenHands cells')
    return [dict(trial_id='timeoutdiag1-' + r['trial_id'].removeprefix('corrected1-'),
                 task_id=r['task_id'], harness=r['harness'], original_trial_id=r['trial_id'],
                 original_result_sha256=r['result_sha256'], original_http_429_requests=r['http_429_requests'])
            for r in sorted(chosen, key=lambda r: (r['task_id'], r['harness']))]


def parent_rows(parent=PARENT):
    """Read outcome/error metadata only. Preserve all 178 original result hashes."""
    runtime = parent / '.runtime/stage2'
    registration = json.loads((runtime / 'corrected-matrix.json').read_text())
    completed, partial = coverage(runtime, registration['cells'])
    if len(completed) != 178 or partial:
        raise ValueError('The parent baseline must be complete')
    rows = []
    for cell in registration['cells']:
        result = completed[cell['trial_id']]
        rewards = (result.get('verifier_result') or {}).get('rewards') or {}
        if result.get('verifier_error_type') or result.get('model_revoked') is not True:
            raise ValueError('Parent verification or revocation incomplete')
        error_files = (runtime / 'scored-attempts' / cell['trial_id']).glob('*.transport-error.json')
        rate_limits = sum(json.loads(p.read_text()).get('http_status') == 429 for p in error_files)
        reward = rewards.get('reward')
        if type(reward) not in (int, float) or reward not in (0, 1):
            raise ValueError('Missing parent reward')
        rows.append(dict(cell, reward=int(reward), agent_error_type=result.get('agent_error_type') or '',
                         http_429_requests=rate_limits,
                         result_sha256=digest(runtime / 'scored-trials' / cell['trial_id'] / 'result.json')))
    return rows


def observe(runtime, cell, result):
    """Metadata-only view; absence of an error file alone is not proof of clean API use."""
    evidence = Path(runtime) / 'scored-attempts' / cell['trial_id']
    calls = call_records(evidence)
    errors = [json.loads(p.read_text()) for p in evidence.glob('*.transport-error.json')]
    retries = list(evidence.glob('*.retry.json'))
    missing = sum(not (evidence / (r['prefix'] + '.outcome.json')).is_file() for r in calls)
    reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    if type(reward) not in (int, float) or reward not in (0, 1):
        reward = None
    api_clean = bool(calls) and not errors and not retries and not missing \
        and all(r.get('accepted_for_agent') is True for r in calls)
    known = [Decimal(r['cost_usd']) for r in calls if r['cost_usd'] is not None]
    unknown = len(calls) - len(known)
    cost = str(sum(known, Decimal(0)))
    return dict(cell, reward=reward, agent_error_type=result.get('agent_error_type') or '',
        verifier_error_type=result.get('verifier_error_type') or '',
        model_requests=len(calls), http_429_requests=sum(e.get('http_status') == 429 for e in errors),
        transport_error_requests=len(errors), retry_records=len(retries), missing_call_outcomes=missing,
        no_recorded_api_errors=api_clean, known_cost_usd=cost,
        total_cost_usd=None if unknown else cost, unknown_cost_requests=unknown,
        phase_seconds=result.get('phase_seconds'), model_protocol_sha256=result.get('model_protocol_sha256'),
        result_sha256=digest(Path(runtime) / 'scored-trials' / cell['trial_id'] / 'result.json'))


def summarise(rows, intended=30):
    if len({r['trial_id'] for r in rows}) != len(rows) or len(rows) > intended:
        raise ValueError('Duplicate or excess diagnostic results')
    clean = [r for r in rows if r['no_recorded_api_errors']]
    return dict(intended=intended, completed=len(rows), remaining=intended-len(rows),
        passed=sum(r['reward'] == 1 for r in rows), failed=sum(r['reward'] == 0 for r in rows),
        no_verifier_result=sum(r['reward'] is None for r in rows),
        passed_without_recorded_api_errors=sum(r['reward'] == 1 for r in clean),
        failed_without_recorded_api_errors=sum(r['reward'] == 0 for r in clean),
        repeated_with_http_429=sum(r['http_429_requests'] > 0 for r in rows),
        other_nonclean_attempts=sum(not r['no_recorded_api_errors'] and not r['http_429_requests'] for r in rows),
        additional_original_passes_established=None,
        known_cost_usd=str(sum((Decimal(r['known_cost_usd']) for r in rows), Decimal(0))),
        unknown_cost_requests=sum(r['unknown_cost_requests'] for r in rows),
        caution='Fresh stochastic attempts of selected failures; do not add recovered passes to the original 89-task scores.')

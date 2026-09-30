"""Baseline phase evidence with original timing and truthful absence semantics.

This is a separate reader, not a custom-harness alias or a native admission.
The archived custom phase reader remains byte-identical and is never patched.
"""
from collections import Counter
from datetime import datetime, timezone

import local_trace
from no_cutoff_final_phase_audit import _error, _number, PHASES, MODEL


def read(result, events, lifecycle, timings, requests, limits):
    """Evidence semantics, never authority to collect, back up or dispatch."""
    if (result.get('harness') not in ('terminus-2', 'openhands')
            or result.get('model_protocol_sha256') != MODEL):
        raise ValueError('Exact original baseline identity and model required')
    identity = {k: result[k] for k in ('trial_id', 'task_id', 'harness', 'model_protocol_sha256')}
    for event in events:
        local_trace.validate(event)
        _number(event['metrics'].get('duration_seconds'))
        if (event['trial_id'] != identity['trial_id'] or event['task_id'] != identity['task_id']
                or event['harness'] != identity['harness'] or event['protocol_sha256'] != MODEL):
            raise ValueError('Trace identity differs from retained baseline result')
    if sorted(e['sequence'] for e in events) != list(range(len(events))):
        raise ValueError('Complete unique phase event sequence required')
    phase = {k: [e for e in events if e['kind'] == k] for k in ('trial', 'cleanup', *PHASES)}
    if any(len(phase[k]) != 1 for k in ('trial', 'cleanup', 'setup')):
        raise ValueError('Required trial, setup or cleanup event missing or duplicated')
    trial = phase['trial'][0]
    if any(not trial['started_ns'] <= e['started_ns'] <= e['ended_ns'] <= trial['ended_ns'] for e in events):
        raise ValueError('Phase event outside actual trial lifetime')
    if phase['cleanup'][0]['status'] != 'ok' or any(result.get(k) is not True for k in
            ('model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed')):
        raise ValueError('Retained revocation and cleanup required')
    if result.get('cleanup_errors') != [] or result.get('trace_errors'):
        raise ValueError('Incomplete cleanup or trace cannot be reported as complete')
    for k in ('error_type', 'revocation_error_type', 'teardown_error_type', 'bridge_error_type'):
        if result.get(k) is not None:
            raise ValueError('Unexpected outer lifecycle failure requires separate review')
    seconds = result.get('phase_seconds')
    if not isinstance(seconds, dict):
        raise ValueError('Actual measured phase durations required')
    error = _error(result.get('agent_error_type')); verifier_error = _error(result.get('verifier_error_type'))
    setup_only = result.get('status') == 'setup_failed'
    if setup_only:
        if (not error or verifier_error or result.get('verifier_result') is not None or set(seconds) != {'setup'}
                or len(events) != 3 or phase['agent'] or phase['verifier'] or requests or timings or lifecycle is not None):
            raise ValueError('Setup-only absence must be proven by actual phase, request and deadline evidence')
        reward = None
        expected_status = 'timeout' if error == 'TimeoutError' else 'error'
        if phase['setup'][0]['status'] != expected_status or trial['status'] != 'error':
            raise ValueError('Setup failure status differs from its trace')
        if error == 'TimeoutError' and _number(seconds['setup']) < 900 - .1:
            raise ValueError('Setup timeout did not consume its qualified allowance')
    else:
        if set(seconds) != set(PHASES) or any(len(phase[k]) != 1 for k in PHASES):
            raise ValueError('Missing executed-phase evidence is not a not-run phase')
        if result.get('status') not in ('verified', 'verifier_failed') or phase['setup'][0]['status'] != 'ok':
            raise ValueError('Unsupported retained lifecycle requires separate review')
        verified = result.get('verifier_result')
        if verified is not None and (not isinstance(verified, dict)
                or verified.get('rewards') is not None and not isinstance(verified['rewards'], dict)):
            raise ValueError('Actual verifier result object required')
        reward = ((verified or {}).get('rewards') or {}).get('reward')
        if reward is not None and (type(reward) not in (int, float) or reward not in (0, 1)):
            raise ValueError('Only an actual binary verifier outcome may be reported')
        if (result['status'] == 'verified' and (verifier_error or not isinstance(verified, dict))
                or result['status'] == 'verifier_failed' and (not verifier_error or verified is not None)
                or phase['verifier'][0]['reward'] != reward
                or phase['agent'][0]['status'] != ('timeout' if error == 'TimeoutError' else 'error' if error else 'ok')
                or phase['verifier'][0]['status'] != ('timeout' if verifier_error == 'TimeoutError' else 'error' if verifier_error else 'ok')
                or trial['status'] != ('ok' if result['status'] == 'verified' else 'error')):
            raise ValueError('Retained verifier and phase statuses disagree')
        if (not isinstance(lifecycle, dict) or lifecycle.get('trial_id') != result['trial_id']
                or lifecycle.get('model_protocol_sha256') != MODEL
                or not isinstance(lifecycle.get('boot_id'), str) or not lifecycle['boot_id']):
            raise ValueError('Actual original agent deadline record required')
        _number(lifecycle.get('deadline_monotonic'), positive=True)
        deadline = _number(lifecycle.get('deadline_utc'), positive=True)
        if abs(deadline - phase['agent'][0]['started_ns'] / 1e9 - limits['agent_timeout_seconds']) >= .1:
            raise ValueError('Agent deadline differs from the official allowance')
        if error == 'TimeoutError' and _number(seconds['agent']) < limits['agent_timeout_seconds'] - .1:
            raise ValueError('Agent timeout did not consume its official allowance')
        if verifier_error == 'TimeoutError' and _number(seconds['verifier']) < limits['verifier_timeout_seconds'] - .1:
            raise ValueError('Verifier timeout did not consume its official allowance')
    for kind, value in seconds.items():
        duration = phase[kind][0]['metrics'].get('duration_seconds')
        _number(value); _number(duration)
        if type(value) is not type(duration) or value != duration:
            raise ValueError('Recorded monotonic duration differs from its phase trace')
    ordered = [phase[k][0] for k in (('setup', 'cleanup') if setup_only else (*PHASES, 'cleanup'))]
    if any(a['ended_ns'] > b['started_ns'] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('Sequential native phases overlap or are out of order')
    generations = [e for e in events if e['kind'] == 'generation']
    def timing_key(value):
        return (value['started_ns'], value['ended_ns'], value['status'], value['seconds'])
    for timing in timings:
        if (any(type(timing.get(k)) is not int for k in ('started_ns', 'ended_ns'))
                or not trial['started_ns'] <= timing['started_ns'] <= timing['ended_ns'] <= trial['ended_ns']
                or timing.get('status') not in ('ok', 'error', 'timeout', 'interrupted')):
            raise ValueError('Actual model timing lies outside retained lifecycle')
        _number(timing.get('seconds'))
    traced = [dict(started_ns=e['started_ns'], ended_ns=e['ended_ns'], status=e['status'],
        seconds=e['metrics'].get('duration_seconds')) for e in generations]
    if Counter(map(timing_key, timings)) != Counter(map(timing_key, traced)) or len(timings) > requests:
        raise ValueError('Actual model timing and generation trace evidence disagree')
    summary = result.get('trace', {})
    billing = result.get('billing', {})
    if not isinstance(summary, dict) or not isinstance(billing, dict):
        raise ValueError('Actual trace and accounting summaries required')
    counts = dict(events=len(events), generations=len(generations), missing_generation_timings=requests - len(timings))
    if (summary.get('status') != 'metadata_spool_not_cloud_export'
            or any(type(summary.get(k)) is not int or summary[k] != v for k, v in counts.items())
            or type(summary.get('unknown_cost_requests')) is not int
            or not 0 <= summary['unknown_cost_requests'] <= requests
            or type(billing.get('requests')) is not int or billing['requests'] != requests
            or type(billing.get('unknown_cost_requests')) is not int
            or billing['unknown_cost_requests'] != summary['unknown_cost_requests']
            or type(trial['metrics'].get('requests')) is not int or trial['metrics']['requests'] != requests):
        raise ValueError('Actual trace and physical request counts disagree')
    row = {k: result[k] for k in ('trial_id', 'task_id', 'harness', 'status')}
    row.update(reward=int(reward) if reward is not None else None, agent_error_type=error,
        verifier_error_type=verifier_error, phase_observation={k: 'measured' if k in seconds else 'not_run_setup_failed' for k in PHASES},
        **{k + '_seconds': seconds.get(k) for k in PHASES}, setup_timeout_seconds=900,
        official_agent_timeout_seconds=limits['agent_timeout_seconds'],
        official_verifier_timeout_seconds=limits['verifier_timeout_seconds'], model_requests=requests,
        generation_timings=len(timings), missing_generation_timings=requests - len(timings),
        completed_utc=datetime.fromtimestamp(trial['ended_ns'] / 1e9, timezone.utc).isoformat())
    return row

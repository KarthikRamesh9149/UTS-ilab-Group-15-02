"""One-shot sequential dispatcher inside a real same-task prerequisite session.

There is deliberately no CLI, saved-receipt mode, caller factory or callback.
The native service must open its own fresh authenticated session and await run
inside that scope. Service wiring and native qualification remain separate.
"""
import asyncio
from datetime import datetime, timezone
import os
import threading
import weakref

import no_cutoff_recovery_policy as policy
import no_cutoff_recovery_session as session
import no_cutoff_recovery_study as study
from no_cutoff_recovery_files import check as check_files, capture, extend
from custom_dispatch_stop import BoundaryStop
from retry_runtime import Clock, Cooldown
from no_cutoff_recovery_files import save as durable_json
from no_cutoff_recovery_qualification import verify as verify_qualification
from scored_trial import docker, run_trial

INTENT = 'no-cutoff-recovery-dispatch.json'
RESULT = 'no-cutoff-recovery-dispatch-result.json'
FAILURE = 'no-cutoff-recovery-dispatch-failure.json'
_CONSUMED = weakref.WeakSet()


def _error(exc):
    return type(exc).__name__ if type(exc) in (ValueError, RuntimeError, TimeoutError,
        OSError, asyncio.CancelledError, SystemExit, KeyboardInterrupt) else 'OtherException'


def _utc():
    return datetime.now(timezone.utc).isoformat()


def _counts(values):
    rewards = [((value.get('verifier_result') or {}).get('rewards') or {}).get('reward')
        for value in values]
    return dict(completed=len(rewards), passes=rewards.count(1), failures=rewards.count(0),
        missing_verifier_results=rewards.count(None))


def _stops(root, block):
    """Read private markers, never acknowledge, remove or reinterpret a stop."""
    names = ['operator-stop-request.json', 'provider-stop.json']
    names += [folder + '/' + cell['trial_id'] + '/provider-stop.json'
        for folder in ('scored-trials', 'scored-attempts') for cell in block['cells']]
    found, bindings = [], {}
    for name in names:
        path = root / '.runtime/stage2' / name
        if path.exists() or path.is_symlink():
            _, bound = study._private(root, name)
            found.append(name); bindings.update(bound)
    return found, bindings


def _checkpoint(permit, expected):
    """Retained metadata only, including a stop at the just-finished boundary.

    Observing a provider stop here cannot admit another task. All admission
    paths keep their strict stop refusal. This is not the completed trace,
    official-limit, cost or off-server-backup audit.
    """
    _, state = study._state(permit)
    root, block = state['root'], state['block']
    check_files(root, state['files'], state['identities'])
    complete, partial, retained = study._attempts(root, block, observe_provider_stops=True)
    study._images(root, state['proof'], complete)
    if partial or set(complete) != expected:
        raise ValueError('Exactly the dispatched prefix must be durably retained; no replay')
    if any(retained.get(name) != sha for name, sha in state['retained'].items()):
        raise ValueError('Previously retained repeat bytes changed during the next task')
    check_files(root, state['retained'], state['retained_identities'])
    stops, stop_files = _stops(root, block)
    check_files(root, dict(state['files'], **retained, **stop_files))
    state['retained'] = retained
    state['retained_identities'] = extend(root, retained, state['retained_identities'])
    ordered = [complete[cell['trial_id']] for cell in block['cells'] if cell['trial_id'] in complete]
    return dict(kind='recovery_retained_dispatch_metadata_not_completed_audit',
        experiment=policy.EXPERIMENT, condition=policy.CONDITION, intended=3,
        **_counts(ordered), original_full89_denominator=89, separate_recovery_denominator=3,
        original_results_replaced=False, recovery_merged_into_original89=False,
        retained_files=retained, stop_files=stop_files, stop_markers=stops,
        completed_audit_verified=False, off_server_backup_verified=False,
        paid_launch_ready=False)


async def _cooldown(runtime, stop):
    # Wait only for the real shared Retry-After expiry, before starting the
    # next task's official clock. No thread/task receives the live session.
    # The loop exists only at this dispatch boundary; it is not a watcher.
    clock = Clock()
    while True:
        if stop.requested():
            return
        current = Cooldown(runtime, clock)
        remaining = current.until - clock.monotonic()
        if remaining <= 0:
            return
        await asyncio.sleep(min(1., remaining))


def _owned_resources_clear():
    for args in (('ps', '-aq', '--filter', 'name=uts-scored-'),
            ('network', 'ls', '-q', '--filter', 'name=uts-scored-'),
            ('volume', 'ls', '-q', '--filter', 'name=uts-scored-')):
        if docker(*args):
            raise ValueError('Retained owned scored resources require inspection before dispatch')


async def run(active):
    """Consume one live session once; never automatically resume a prior run.

    A retained launch intent, terminal record or any earlier attempt requires
    operator inspection, not a retry through this function. The caller keeps
    all session/ancestor locks until this coroutine and its scope have exited.
    """
    live = session._live(active)
    if threading.current_thread() is not threading.main_thread():
        raise ValueError('The native dispatcher must own cooperative signals on the main thread')
    if active in _CONSUMED:
        raise ValueError('A fresh authenticated session is required for each operation')
    _CONSUMED.add(active)
    root = live['root']; runtime = root / '.runtime/stage2'
    for name in (INTENT, RESULT, FAILURE):
        path = runtime / name
        if path.exists() or path.is_symlink():
            raise ValueError('Retained dispatch intent/result forbids automatic restart')
    # The real session has already audited before locks and holds them now.
    # register/dispatch_permit verify the actual qualification and producers.
    block = study.register(active)
    with study.dispatch_permit(active) as permit, BoundaryStop(runtime) as stop:
        current = _checkpoint(permit, set())
        if stop.requested() or current['stop_markers']:
            raise ValueError('Persistent stop forbids a new dispatch')
        _owned_resources_clear()
        intent = dict(kind='single_recovery_dispatch_intent', schema_version=1,
            experiment=policy.EXPERIMENT, condition=policy.CONDITION, pid=os.getpid(),
            started_utc=_utc(), intended=3, automatic_resume=False,
            registration_sha256=policy.fingerprint(block),
            qualification_sha256=block['qualification_sha256'],
            sources_sha256=block['sources_sha256'])
        durable_json(runtime / INTENT, intent)
        _, intent_files = study._private(root, INTENT)
        intent_identities = capture(root, intent_files)[1]
        expected = set(); retained_errors = {}; last_requested = None
        try:
            factory = study.agent_factory(permit)
            for cell in block['cells']:
                if stop.requested():
                    break
                await _cooldown(runtime, stop)
                if stop.requested():
                    break
                check_files(root, intent_files, intent_identities)
                _, state = study._state(permit)
                proof = state['proof']
                last_requested = cell['trial_id']
                try:
                    await run_trial(root=root, trial_id=last_requested, task_id=cell['task_id'], stage='final',
                        agent_factory=factory, gateway_image=proof['gateway_image'],
                        guard_image=proof['guard_image'], setup_timeout_seconds=900,
                        model_settings=policy.SETTINGS, accounting_mode='provider-credit-only',
                        recovery=policy.EXPERIMENT)
                except Exception as exc:
                    # A genuine retained failure may advance the matrix. An
                    # absent/partial/unsafe result or invalid scope cannot.
                    # Never persist exception text or raw model/tool exchanges.
                    retained_errors[last_requested] = _error(exc)
                _, state = study._state(permit)
                if state['issued'] is None or state['issued']['trial_id'] != last_requested:
                    raise ValueError('The real scored admission did not issue this next key')
                expected.add(last_requested)
                stop.requested()  # Persist even a signal received in the final cell.
                current = _checkpoint(permit, expected)
                check_files(root, intent_files, intent_identities)
                if current['stop_markers']:
                    break
            stop.requested()
            current = _checkpoint(permit, expected)
            if not current['stop_markers']:
                # No collector/relocking: re-read live qualification, current
                # libraries/host and actual producers before terminal success.
                verify_qualification(active)
            _owned_resources_clear()
            stop.requested()
            current = _checkpoint(permit, expected)
            check_files(root, intent_files, intent_identities)
            if not current['stop_markers'] and current['completed'] != 3:
                raise ValueError('A short dispatch without a persistent stop is not complete')
            result = dict(current, status='stopped' if current['stop_markers'] else 'complete',
                finished_utc=_utc(), dispatch_intent_sha256=next(iter(intent_files.values())),
                automatic_resume=False, retained_exception_types=retained_errors)
            durable_json(runtime / RESULT, result)
            return result
        except BaseException as exc:
            # Cancellation/SystemExit is not a completed failure or a retry.
            # The scored runner retains its own cleanup evidence independently.
            stop.requested()
            durable_json(runtime / FAILURE, dict(kind='recovery_dispatch_failure_requires_inspection',
                experiment=policy.EXPERIMENT, condition=policy.CONDITION, failed_utc=_utc(),
                dispatch_intent_sha256=next(iter(intent_files.values())), last_requested_trial_id=last_requested,
                previously_checked_completed=current['completed'], error_type=_error(exc),
                automatic_resume=False, paid_launch_ready=False))
            raise

"""Shared agent/verifier lifecycle for the three scored harnesses.

The caller starts and audits the isolated environment, creates the appropriate
native agent and owns the host orchestration lock. This module never starts a
model service, creates credit or retries a trial. Results are verifier-derived.
"""
import asyncio
import math
import sys
import time

from harbor.models.agent.context import AgentContext
from harbor.verifier.verifier import Verifier


async def execute_phases(*, agent, environment, task, paths, revoke_model,
                         setup_timeout_seconds, verifier_factory=Verifier, cleanup_timeout_seconds=60,
                         phase_observer=None, prepare_environment=None, retained_result=None):
    limits = [setup_timeout_seconds, task.config.agent.timeout_sec, task.config.verifier.timeout_sec, cleanup_timeout_seconds]
    for value in limits:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Explicit positive phase timeouts required')
    if retained_result is not None and (type(retained_result) is not dict or retained_result):
        raise ValueError('Phase evidence sink must be an empty dict')
    result = retained_result if retained_result is not None else {}
    result.update(status='started', agent_error_type=None, verifier_error_type=None,
        model_revoked=False, verifier_result=None, cleanup_errors=[], phase_seconds={})
    if phase_observer is not None and not callable(phase_observer):
        raise ValueError('Phase observer must be callable')
    trial_started_ns, trial_started = time.time_ns(), time.monotonic()

    def phase_status(error=None):
        if isinstance(sys.exc_info()[1], asyncio.CancelledError):
            return 'interrupted'
        return 'timeout' if error == 'TimeoutError' else 'error' if error else 'ok'

    def observe(kind, started_ns, seconds, status='ok', reward=None):
        if phase_observer is None:
            return
        try:
            phase_observer(kind=kind, started_ns=started_ns, ended_ns=time.time_ns(),
                           seconds=seconds, status=status, reward=reward)
        except Exception as exc:
            # Observability cannot change the agent/verifier outcome. Missing
            # trace evidence is explicit and must prevent evidence admission.
            result.setdefault('trace_errors', []).append(kind + ':' + type(exc).__name__)
    context = AgentContext()
    ready = False
    revoked = False
    async def revoke():
        nonlocal revoked
        if not revoked:
            await asyncio.wait_for(revoke_model(), timeout=cleanup_timeout_seconds)
            revoked = True
            result['model_revoked'] = True
    try:
        started, started_ns = time.monotonic(), time.time_ns()
        try:
            async def setup_phase():
                if prepare_environment is not None:
                    result['environment_preparation'] = await prepare_environment(environment)
                with environment.with_default_user(task.config.agent.user):
                    await agent.setup(environment)
            await asyncio.wait_for(setup_phase(), timeout=setup_timeout_seconds)
            ready = True
        except Exception as exc:
            result.update(status='setup_failed', agent_error_type=type(exc).__name__)
        finally:
            result['phase_seconds']['setup'] = time.monotonic() - started
            observe('setup', started_ns, result['phase_seconds']['setup'], phase_status(result['agent_error_type']))
        if ready:
            started, started_ns = time.monotonic(), time.time_ns()
            try:
                with environment.with_default_user(task.config.agent.user):
                    await asyncio.wait_for(agent.run(task.instruction, environment, context),
                                           timeout=task.config.agent.timeout_sec)
            except Exception as exc:
                # An agent timeout/budget stop is not an excuse to discard its
                # work or replay it. The unchanged verifier still evaluates it.
                result['agent_error_type'] = type(exc).__name__
            finally:
                result['phase_seconds']['agent'] = time.monotonic() - started
                observe('agent', started_ns, result['phase_seconds']['agent'], phase_status(result['agent_error_type']))
        try:
            await revoke()
        except Exception as exc:
            result.update(status='revocation_failed', revocation_error_type=type(exc).__name__)
        if ready and revoked:
            started, started_ns = time.monotonic(), time.time_ns()
            try:
                # Remove only this trial's previous verifier outputs. No tests
                # are uploaded or exposed until model access is revoked.
                async def verify_phase():
                    await environment.empty_dirs(['/logs/verifier'], chmod=True)
                    with environment.with_default_user(task.config.verifier.user):
                        verifier = verifier_factory(task, paths, environment)
                        return await verifier.verify()
                verified = await asyncio.wait_for(verify_phase(), timeout=task.config.verifier.timeout_sec)
                result['verifier_result'] = verified.model_dump(mode='json')
                result['status'] = 'verified'
            except Exception as exc:
                result.update(status='verifier_failed', verifier_error_type=type(exc).__name__)
            finally:
                result['phase_seconds']['verifier'] = time.monotonic() - started
                rewards = (result['verifier_result'] or {}).get('rewards')
                reward = rewards.get('reward') if isinstance(rewards, dict) else None
                observe('verifier', started_ns, result['phase_seconds']['verifier'],
                        phase_status(result['verifier_error_type']), reward=reward)
    finally:
        cleanup_started, cleanup_started_ns = time.monotonic(), time.time_ns()
        # Cancellation also reaches this block. Never leave an authorised
        # model service or task container behind because one cleanup failed.
        if not revoked:
            try:
                await revoke()
            except Exception as exc:
                result['cleanup_errors'].append('revocation:' + type(exc).__name__)
        cleanup = getattr(agent, 'cleanup_after_verification', None)
        if cleanup is not None:
            try:
                await asyncio.wait_for(cleanup(), timeout=cleanup_timeout_seconds)
            except Exception as exc:
                result['cleanup_errors'].append('agent:' + type(exc).__name__)
        try:
            await asyncio.wait_for(environment.stop(delete=True), timeout=cleanup_timeout_seconds)
        except Exception as exc:
            result['cleanup_errors'].append('environment:' + type(exc).__name__)
        result['agent_context'] = context.model_dump(mode='json', exclude={'rollout_details'})
        if result['cleanup_errors']:
            result['status'] = 'cleanup_failed'
        observe('cleanup', cleanup_started_ns, time.monotonic() - cleanup_started,
                'error' if result['cleanup_errors'] else 'ok')
        observe('trial', trial_started_ns, time.monotonic() - trial_started,
                phase_status(None if result['status'] == 'verified' else result['status']))
    return result

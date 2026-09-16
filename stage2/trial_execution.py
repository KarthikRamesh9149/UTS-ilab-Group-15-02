"""Shared agent/verifier lifecycle for the three scored harnesses.

The caller starts and audits the isolated environment, creates the appropriate
native agent and owns the host orchestration lock. This module never starts a
model service, creates credit or retries a trial. Results are verifier-derived.
"""
import asyncio
import math
import time

from harbor.models.agent.context import AgentContext
from harbor.verifier.verifier import Verifier


async def execute_phases(*, agent, environment, task, paths, revoke_model,
                         setup_timeout_seconds, verifier_factory=Verifier, cleanup_timeout_seconds=60):
    limits = [setup_timeout_seconds, task.config.agent.timeout_sec, task.config.verifier.timeout_sec, cleanup_timeout_seconds]
    for value in limits:
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Explicit positive phase timeouts required')
    result = {'status': 'started', 'agent_error_type': None, 'verifier_error_type': None,
              'model_revoked': False, 'verifier_result': None, 'cleanup_errors': [], 'phase_seconds': {}}
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
        started = time.monotonic()
        try:
            with environment.with_default_user(task.config.agent.user):
                await asyncio.wait_for(agent.setup(environment), timeout=setup_timeout_seconds)
            ready = True
        except Exception as exc:
            result.update(status='setup_failed', agent_error_type=type(exc).__name__)
        finally:
            result['phase_seconds']['setup'] = time.monotonic() - started
        if ready:
            started = time.monotonic()
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
        try:
            await revoke()
        except Exception as exc:
            result.update(status='revocation_failed', revocation_error_type=type(exc).__name__)
        if ready and revoked:
            started = time.monotonic()
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
    finally:
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
    return result

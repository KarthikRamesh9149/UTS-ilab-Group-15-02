"""One sequential, source-bound final89 of the measured C0-NC revision.

No paid probe, implicit selection, extra baseline matrix or task replay. Final
native qualification and the actual completed-revision freeze are prerequisites.
"""
import argparse
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import threading

import no_cutoff_final_evidence as evidence
from no_cutoff_custom_agent import agent_factory
from no_cutoff_final_policy import EXPERIMENT, SETTINGS, fingerprint
from no_cutoff_final_runtime import DEPLOYMENT
from no_cutoff_final_study import (read_candidate, qualified, register, audited, summary, dispatch_permit)
from run_no_cutoff_custom import lock_all as inherited_locks
from run_credit_only import hold, pending_stops
from credit_only_experiment import cleanup_complete
from custom_dispatch_stop import BoundaryStop
from retry_runtime import Clock, Cooldown, private_read
from scored_trial import docker, run_trial


def lock_all(stack, root):
    if Path(root).resolve() == evidence.CURRENT.resolve():
        raise ValueError('Do not run the final in the measured revision deployment')
    inherited_locks(stack, root)
    for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
        hold(stack, evidence.CURRENT / '.runtime/stage2', name)


async def dispatch(root, block, *, stop=None):
    runtime = Path(root) / '.runtime/stage2'
    stop = stop if stop is not None else BoundaryStop(runtime)
    if stop.requested():
        return
    completed, partial = audited(root)
    if partial:
        raise ValueError('A started final attempt is retained, never replayed')
    if pending_stops(runtime, completed):
        raise ValueError('Actual provider stop needs inspection before another final attempt')
    for cell in block['cells']:
        if stop.requested():
            return
        name = cell['trial_id']
        if name in completed:
            continue
        proof = qualified(root)
        if fingerprint(proof) != block['qualification_sha256']:
            raise ValueError('Final native qualification changed')
        cooldown = Cooldown(runtime, Clock())
        if cooldown.until > cooldown.clock.monotonic():
            await asyncio.to_thread(cooldown.wait, cooldown.until + 1, threading.Event())
        if stop.requested():
            return
        print(json.dumps(dict(status='starting', condition=block['condition'],
            completed=len(completed), intended=89, trial_id=name)), flush=True)
        try:
            result = await run_trial(root=root, trial_id=name, task_id=cell['task_id'], stage='final',
                agent_factory=agent_factory(root, 'C0'), gateway_image=proof['gateway_image'],
                guard_image=proof['guard_image'], setup_timeout_seconds=proof['setup_timeout_seconds'],
                model_settings=SETTINGS, accounting_mode='provider-credit-only', custom_study=EXPERIMENT)
        except Exception:
            path = runtime / 'scored-trials' / name / 'result.json'
            if not path.exists():
                raise
            result = private_read(path)
            if not cleanup_complete(result):
                raise
        if not cleanup_complete(result) or result.get('model_revoked') is not True:
            raise ValueError('Retained final outcome lacks cleanup or model revocation')
        completed, partial = audited(root)
        if partial or name not in completed:
            raise ValueError('Final result was not durably retained')
        current = summary(root)
        print(json.dumps(dict(status='complete' if current['attempted'] == 89 else 'running',
            **{k: v for k, v in current.items() if k != 'rows'})), flush=True)
        # Also persists a signal arriving during the last cell. No watcher or
        # forced interruption is used for an ordinary cooperative boundary stop.
        if stop.requested() or pending_stops(runtime, completed):
            return


async def run(root):
    root = Path(root).resolve()
    if root != DEPLOYMENT:
        raise ValueError('Use only the separate qualified C0-NC final deployment')
    if BoundaryStop(root / '.runtime/stage2').requested():
        raise ValueError('Persistent operator stop forbids automatic final resume')
    # Its unchanged collector holds the ancestor locks internally. Complete
    # the actual audit first, then recheck its bytes while holding those locks.
    authenticated = evidence.authenticate(root, read_candidate(root))
    with ExitStack() as stack:
        lock_all(stack, root)
        evidence.recheck(root, read_candidate(root), authenticated)
        if docker('ps', '-aq', '--filter', 'name=uts-scored-'):
            raise ValueError('An owned task container still exists')
        block = register(root, authenticated)
        with dispatch_permit(root, block, authenticated), BoundaryStop(root / '.runtime/stage2') as stop:
            await dispatch(root, block, stop=stop)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'report'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT:
        raise SystemExit('Use only the separately qualified C0-NC final native deployment')
    os.umask(0o077)
    if args.action == 'run':
        asyncio.run(run(root))
    else:
        print(json.dumps(summary(root)))

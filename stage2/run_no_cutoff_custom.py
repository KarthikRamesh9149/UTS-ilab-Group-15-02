"""One separately registered, sequential C0-NC fixed20 validation."""
import argparse
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import threading

import direct_final_evidence as original
from no_cutoff_custom_agent import agent_factory
from no_cutoff_custom_policy import EXPERIMENT, SETTINGS, fingerprint
from no_cutoff_custom_runtime import DEPLOYMENT
from no_cutoff_custom_study import (read_candidate, qualified, register, audited, summary, dispatch_permit)
from run_deadline_custom import lock_all as inherited_locks
from run_credit_only import hold, pending_stops
from credit_only_experiment import cleanup_complete
from custom_dispatch_stop import BoundaryStop
from retry_runtime import Clock, Cooldown, private_read
from scored_trial import docker, run_trial


def lock_all(stack, root):
    if Path(root).resolve() in {p.resolve() for p in original.ROOTS.values()}:
        raise ValueError('Do not run the revision in an original deployment')
    inherited_locks(stack, root)
    # C3 r2 is additional to the portable/C3 r1 and older ancestor chain.
    for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
        hold(stack, original.CURRENT / '.runtime/stage2', name)


async def dispatch(root, block, *, stop=None):
    runtime = Path(root) / '.runtime/stage2'
    stop = stop if stop is not None else BoundaryStop(runtime)
    if stop.requested():
        return
    completed, partial = audited(root)
    if partial:
        raise ValueError('A started revision attempt is retained, never replayed')
    if pending_stops(runtime, completed):
        raise ValueError('Actual provider stop needs inspection before another attempt')
    for cell in block['cells']:
        if stop.requested():
            return
        name = cell['trial_id']
        if name in completed:
            continue
        proof = qualified(root)
        if fingerprint(proof) != block['qualification_sha256']:
            raise ValueError('No-cutoff qualification changed')
        cooldown = Cooldown(runtime, Clock())
        if cooldown.until > cooldown.clock.monotonic():
            await asyncio.to_thread(cooldown.wait, cooldown.until + 1, threading.Event())
        if stop.requested():
            return
        print(json.dumps(dict(status='starting', condition=block['condition'],
            completed=len(completed), intended=20, trial_id=name)), flush=True)
        try:
            result = await run_trial(root=root, trial_id=name, task_id=cell['task_id'], stage='development',
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
            raise ValueError('Retained no-cutoff outcome lacks cleanup or model revocation')
        completed, partial = audited(root)
        if partial or name not in completed:
            raise ValueError('Revision result was not durably retained')
        current = summary(root)
        print(json.dumps(dict(status='complete' if current['attempted'] == 20 else 'running',
            **{k: v for k, v in current.items() if k != 'rows'})), flush=True)
        # Persist a cooperative signal even if it arrived during the final
        # task. The previous signal-only final-cell persistence edge is absent.
        if stop.requested() or pending_stops(runtime, completed):
            return


async def run(root):
    root = Path(root)
    if BoundaryStop(root / '.runtime/stage2').requested():
        raise ValueError('Persistent operator stop forbids automatic resume')
    # The unchanged original collector holds ancestor locks internally. It
    # must finish before we hold them; then recheck every bound file under lock.
    authenticated = original.authenticate(root, read_candidate(root))
    with ExitStack() as stack:
        lock_all(stack, root)
        original.recheck(root, read_candidate(root), authenticated)
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
        raise SystemExit('Use only the separately qualified C0-NC native deployment')
    os.umask(0o077)
    if args.action == 'run':
        asyncio.run(run(root))
    else:
        print(json.dumps(summary(root)))

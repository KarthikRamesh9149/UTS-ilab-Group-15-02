"""Sequential uncapped custom dev20 blocks. Never launch at import time."""
import argparse
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import threading

from deadline_custom_agent import agent_factory
from deadline_custom_policy import EXPERIMENT, SETTINGS, fingerprint
from deadline_custom_study import (DEPLOYMENT, register, qualified, audited, summary)
from credit_only_experiment import cleanup_complete
from retry_experiment import ANCESTORS, DEPLOYMENT as BASELINE
from retry_runtime import Clock, Cooldown, private_read
from run_credit_only import hold, pending_stops
from scored_trial import run_trial, docker
from custom_dispatch_stop import BoundaryStop
from deadline_custom_parent import PREVIOUS

DIAGNOSTIC = Path('/opt/uts-capstone-timeout-diagnostic-20260925')
STOPPED_CUSTOM = Path('/opt/uts-capstone-custom-development-20260926')
PRIOR_REHEARSAL = Path('/opt/uts-capstone-custom-deadline-20260927')


def lock_all(stack, root):
    # The old deployments stay untouched except their existing lock files.
    # Every scored process must hold the shared ancestor lock too.
    for base in (*ANCESTORS, BASELINE, DIAGNOSTIC, STOPPED_CUSTOM, PREVIOUS, PRIOR_REHEARSAL, Path(root)):
        hold(stack, base / '.runtime/stage2', 'matrix.lock')
        if base != Path(root):
            for name in ('scored.lock', 'gateway.lock'):
                hold(stack, base / '.runtime/stage2', name)


async def dispatch(root, block, *, stop=None):
    runtime = Path(root) / '.runtime/stage2'
    stop = stop if stop is not None else BoundaryStop(runtime)
    if stop.requested():
        print(json.dumps(dict(status='operator_stopped_before_dispatch')), flush=True)
        return
    completed, partial = audited(root)
    if partial:
        raise ValueError('Started custom attempt is retained and cannot be replayed')
    if pending_stops(runtime, completed):
        raise ValueError('Actual provider credit/auth/identity stop needs inspection')
    for cell in block['cells']:
        if stop.requested():
            print(json.dumps(dict(status='operator_stopped_at_boundary')), flush=True)
            return
        name = cell['trial_id']
        if name in completed:
            continue
        proof = qualified(root)
        if block['qualification_sha256'] != fingerprint(proof):
            raise ValueError('Custom qualification changed')
        cooldown = Cooldown(runtime, Clock())
        if cooldown.until > cooldown.clock.monotonic():
            await asyncio.to_thread(cooldown.wait, cooldown.until + 1, threading.Event())
        if stop.requested():
            print(json.dumps(dict(status='operator_stopped_before_attempt')), flush=True)
            return
        print(json.dumps(dict(status='starting', condition=block['condition'],
            completed=sum(c['trial_id'] in completed for c in block['cells']), intended=20,
            trial_id=name)), flush=True)
        try:
            result = await run_trial(root=root, trial_id=name, task_id=cell['task_id'], stage='development',
                agent_factory=agent_factory(root, block['parent'], base_parent=block['base_parent']),
                gateway_image=proof['gateway_image'], guard_image=proof['guard_image'],
                setup_timeout_seconds=proof['setup_timeout_seconds'], model_settings=SETTINGS,
                accounting_mode='provider-credit-only', custom_study=EXPERIMENT)
        except Exception:
            path = runtime / 'scored-trials' / name / 'result.json'
            if not path.exists():
                raise
            result = private_read(path)
            if not cleanup_complete(result):
                raise
        if not cleanup_complete(result) or result.get('model_revoked') is not True:
            raise ValueError('Custom cleanup/revocation incomplete')
        completed, partial = audited(root)
        if partial or name not in completed:
            raise ValueError('Custom result not durably recorded')
        current = summary(root)
        print(json.dumps(dict(status='complete' if current['attempted'] == 20 else 'running',
            **{k: v for k, v in current.items() if k != 'rows'})), flush=True)
        if pending_stops(runtime, completed):
            return


async def run(root):
    with ExitStack() as stack:
        lock_all(stack, root)
        if docker('ps', '-q', '--filter', 'name=uts-scored-'):
            raise ValueError('Another owned task is active')
        block = register(root)
        with BoundaryStop(Path(root) / '.runtime/stage2') as stop:
            await dispatch(root, block, stop=stop)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'report'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT:
        raise SystemExit('Use only the separate qualified native custom deployment')
    os.umask(0o077)
    if args.action == 'run':
        asyncio.run(run(root))
    else:
        print(json.dumps(summary(root)))

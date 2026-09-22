"""Exactly 89 tasks per baseline, once each, no financial admission or reserve."""
import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import threading

from credit_only_policy import MODE
from model_protocol import freeze_protocol
from recovery_agents import agent_factory
from retry_policy import EXPERIMENT, SETTINGS, POLICY, require_policy
from retry_runtime import Clock, Cooldown
from retry_experiment import (DEPLOYMENT, ANCESTORS, CLOSED_THIRD, ORIGINAL,
    REGISTRATION, cells, sources, digest, coverage, cleanup_complete, validate_qualification)
from run_credit_only import hold, counts, pending_stops
from scored_gateway import durable_json, private_directory
from scored_trial import run_trial, docker


async def run(root):
    import host_environment
    if root != DEPLOYMENT: raise ValueError('Use the separate corrected deployment')
    runtime = private_directory(root / '.runtime/stage2')
    require_policy(runtime)
    with ExitStack() as stack:
        for base in (*ANCESTORS, root): hold(stack, base / '.runtime/stage2', 'matrix.lock')
        for base in ANCESTORS:
            for name in ('scored.lock', 'gateway.lock'): hold(stack, base / '.runtime/stage2', name)
        proof = validate_qualification(root)
        if host_environment.snapshot() != proof['host_environment']: raise ValueError('Host changed')
        if docker('ps', '-q', '--filter', 'name=uts-scored-'): raise ValueError('Existing trial still active')
        previous_registration = CLOSED_THIRD / '.runtime/stage2/credit-only-matrix.json'
        previous = json.loads(previous_registration.read_text())
        old, partial = coverage(CLOSED_THIRD / '.runtime/stage2', previous['cells'])
        if partial or len(old) != 178: raise ValueError('Previous closed experiment must be preserved complete')
        parent = json.loads((ORIGINAL / '.runtime/stage2/baseline-matrix.json').read_text())
        freeze_protocol(runtime, SETTINGS)
        manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
        intended = cells(manifest['all_task_ids'])
        # A separately recorded one-prompt connection check must have succeeded
        # before spending any of the 178 one-shot benchmark cells.
        preflight = runtime / 'provider-check.json'
        checked = json.loads(preflight.read_text())
        if (checked.get('status') != 'passed' or checked.get('sources') != sources(root)
                or checked.get('model_protocol_sha256') != SETTINGS.fingerprint()):
            raise ValueError('Current real-provider connection check required')
        descriptor = dict(experiment=EXPERIMENT, policy=POLICY, cells=intended,
            sources=sources(root), gateway_image=proof['gateway_image'], guard_image=proof['guard_image'],
            model_protocol_sha256=SETTINGS.fingerprint(), parallel_trials=1, attempts_per_cell=1,
            provider_check_sha256=digest(preflight), original_results_replaced=False,
            predecessor_registration_sha256=digest(previous_registration),
            predecessor_results_sha256={name: digest(CLOSED_THIRD / '.runtime/stage2/scored-trials' / name / 'result.json') for name in sorted(old)})
        path = runtime / REGISTRATION
        if not path.exists(): durable_json(path, descriptor)
        if json.loads(path.read_text()) != descriptor: raise ValueError('Frozen registration drift')
        completed, partial = coverage(runtime, intended)
        if partial: raise ValueError('Interrupted attempts require audit, never automatic replay: ' + ','.join(partial))
        if pending_stops(runtime, completed): raise ValueError('Provider stop requires inspection')
        for cell in intended:
            trial_id = cell['trial_id']
            if trial_id in completed: continue
            if sources(root) != descriptor['sources']: raise ValueError('Frozen source drift')
            cooldown = Cooldown(runtime, Clock())
            if cooldown.until > cooldown.clock.monotonic():
                print(json.dumps(dict(status='provider_cooldown', completed=len(completed), intended=178)), flush=True)
                # Wait before opening a new task; do not charge the next task's
                # official clock for a prior task's provider cooldown.
                await asyncio.to_thread(cooldown.wait, cooldown.until + 1, threading.Event())
            print(json.dumps(dict(status='starting', completed=len(completed), intended=178, trial_id=trial_id)), flush=True)
            try:
                result = await run_trial(root=root, trial_id=trial_id, task_id=cell['task_id'], stage='final',
                    agent_factory=agent_factory(cell['harness'], root), model_settings=SETTINGS,
                    gateway_image=proof['gateway_image'], guard_image=proof['guard_image'],
                    setup_timeout_seconds=parent['admission']['setup_timeout_seconds'], accounting_mode=MODE)
            except Exception:
                path = runtime / 'scored-trials' / trial_id / 'result.json'
                if not path.exists(): raise
                result = json.loads(path.read_text())
                if not cleanup_complete(result): raise
            if not cleanup_complete(result): raise RuntimeError('Cleanup incomplete')
            completed[trial_id] = result
            stop = runtime / 'scored-attempts' / trial_id / 'provider-stop.json'
            if stop.exists():
                print(json.dumps(dict(status='provider_stopped', completed=len(completed), intended=178,
                    trial_id=trial_id, reason=json.loads(stop.read_text())['reason'])), flush=True)
                return
            print(json.dumps(dict(status='complete' if len(completed) == 178 else 'running',
                completed=len(completed), intended=178, trial_id=trial_id, scores=counts(completed))), flush=True)


if __name__ == '__main__':
    os.umask(0o077)
    asyncio.run(run(Path(__file__).resolve().parents[1]))

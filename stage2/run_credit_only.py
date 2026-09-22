"""178 new sequential baseline attempts; only the provider enforces credit.

No monetary admission checks or receipt gates. Existing terminal attempts are
never replayed. A real insufficient-credit response stops new dispatches until
the operator confirms a manually funded top-up. No automatic purchase exists.
"""
import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path

from credit_only_experiment import (ORIGINAL, PREDECESSOR, DEPLOYMENT, REGISTRATION,
    cells, coverage, cleanup_complete, digest, sources, validate_qualification)
from credit_only_policy import EXPERIMENT, MODE, POLICY, require_policy
from model_protocol import ModelSettings, freeze_protocol
from native_agents import agent_factory
from scored_gateway import durable_json, private_directory
from scored_trial import run_trial, docker


def hold(stack, runtime, name):
    fd = os.open(Path(runtime) / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    handle = stack.enter_context(os.fdopen(fd, 'r+'))
    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)


def counts(completed):
    summary = {}
    for harness in ('terminus-2', 'openhands'):
        rows = [r for r in completed.values() if r['harness'] == harness]
        rewards = [((r.get('verifier_result') or {}).get('rewards') or {}).get('reward') for r in rows]
        summary[harness] = dict(attempted=len(rows), passed=sum(r == 1 for r in rewards),
            failed=sum(r == 0 for r in rewards), no_verifier_result=sum(r not in (0, 1) for r in rewards))
    return summary


def pending_stops(runtime, completed):
    result = []
    for trial_id in completed:
        stop = Path(runtime) / 'scored-attempts' / trial_id / 'provider-stop.json'
        if not stop.exists():
            continue
        checksum = digest(stop)
        acknowledgement = Path(runtime) / 'manual-top-up-acknowledgements' / (checksum + '.json')
        if acknowledgement.exists():
            value = json.loads(acknowledgement.read_text())
            if (value.get('provider_stop_sha256') != checksum or value.get('trial_id') != trial_id
                    or value.get('user_confirmed_manual_top_up') is not True
                    or json.loads(stop.read_text()).get('reason') != 'provider_credit_exhausted'):
                raise ValueError('Provider-stop acknowledgement mismatch')
        else:
            result.append((trial_id, stop, json.loads(stop.read_text())))
    return result


async def run(confirm_manual_top_up=None):
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT:
        raise ValueError('Run only in the separate registered native deployment')
    os.umask(0o077)
    runtime = private_directory(root / '.runtime/stage2')
    require_policy(runtime)
    with ExitStack() as stack:
        # The active predecessor owns ORIGINAL/matrix.lock, so handoff cannot
        # race it. No waiting in a shell, duplicate service or overlapping run.
        for base in (ORIGINAL, PREDECESSOR, root):
            hold(stack, base / '.runtime/stage2', 'matrix.lock')
        for base in (ORIGINAL, PREDECESSOR):
            for name in ('scored.lock', 'gateway.lock'):
                hold(stack, base / '.runtime/stage2', name)
        proof = validate_qualification(root)
        import host_environment
        if host_environment.snapshot() != proof['host_environment']:
            raise ValueError('Qualified execution host changed')
        previous_registration = PREDECESSOR / '.runtime/stage2/baseline-repeat-matrix.json'
        previous = json.loads(previous_registration.read_text())
        previous_completed, partial = coverage(PREDECESSOR / '.runtime/stage2', previous['cells'])
        if partial:
            raise ValueError('Predecessor has unfinished attempts; preserve and clean them before handoff')
        # Old cleanup flags are checked above; verify no scored containers are
        # still alive on this dedicated study host before authorising handoff.
        if docker('ps', '-q', '--filter', 'name=uts-scored-'):
            raise ValueError('A predecessor model/task container is still active')
        parent = json.loads((ORIGINAL / '.runtime/stage2/baseline-matrix.json').read_text())
        settings = ModelSettings(**parent['admission']['settings'])
        if settings.fingerprint() != proof['model_protocol_sha256']:
            raise ValueError('Frozen model protocol mismatch')
        freeze_protocol(runtime, settings)
        manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
        intended = cells(manifest['all_task_ids'])
        descriptor = dict(experiment=EXPERIMENT, policy=POLICY, cells=intended, sources=sources(root),
            gateway_image=proof['gateway_image'], guard_image=proof['guard_image'],
            model_protocol_sha256=settings.fingerprint(),
            predecessor_registration_sha256=digest(previous_registration),
            predecessor_completed=len(previous_completed), predecessor_intended=178,
            predecessor_status='complete' if len(previous_completed) == 178 else 'terminal_partial',
            predecessor_results_sha256={name: digest(PREDECESSOR / '.runtime/stage2/scored-trials' / name / 'result.json')
                                       for name in sorted(previous_completed)},
            original_results_replaced=False, parallel_trials=1, attempts_per_cell=1)
        registration = runtime / REGISTRATION
        if not registration.exists():
            durable_json(registration, descriptor)
        if json.loads(registration.read_text()) != descriptor:
            raise ValueError('Immutable provider-credit-only registration drift')
        completed, partial = coverage(runtime, intended)
        if partial:
            raise ValueError('Interrupted attempts retained, never automatically replayed: ' + ','.join(partial))
        stops = pending_stops(runtime, completed)
        if confirm_manual_top_up is not None:
            matching = [item for item in stops if item[0] == confirm_manual_top_up]
            if len(matching) != 1 or matching[0][2]['reason'] != 'provider_credit_exhausted':
                raise ValueError('Explicit credit-stop identity required after a user-confirmed manual top-up')
            from openrouter_transport import OpenRouter, load_key
            balance = Decimal(OpenRouter(load_key(root / '.env')).balance())
            if not balance.is_finite() or balance <= 0:
                raise ValueError('Provider still reports no available credit after the confirmed top-up')
            trial_id, stop_path, _ = matching[0]
            acknowledgement = private_directory(runtime / 'manual-top-up-acknowledgements')
            durable_json(acknowledgement / (digest(stop_path) + '.json'), dict(
                trial_id=trial_id, provider_stop_sha256=digest(stop_path),
                user_confirmed_manual_top_up=True, observed_balance_usd=str(balance),
                checked_utc=datetime.now(timezone.utc).isoformat()))
            stops = pending_stops(runtime, completed)
        if stops:
            print(json.dumps(dict(status='provider_stopped', completed=len(completed), intended=178,
                reasons=[{'trial_id': name, 'reason': value['reason']} for name, _, value in stops])), flush=True)
            return
        for cell in intended:
            trial_id = cell['trial_id']
            if trial_id in completed:
                continue
            if sources(root) != descriptor['sources']:
                raise ValueError('Execution source drift')
            print(json.dumps(dict(status='starting', completed=len(completed), intended=178, trial_id=trial_id)), flush=True)
            try:
                result = await run_trial(root=root, trial_id=trial_id, task_id=cell['task_id'], stage='final',
                    agent_factory=agent_factory(cell['harness'], settings), model_settings=settings,
                    gateway_image=proof['gateway_image'], guard_image=proof['guard_image'],
                    setup_timeout_seconds=parent['admission']['setup_timeout_seconds'], accounting_mode=MODE)
            except Exception:
                # An already-started infrastructure failure stays a failure.
                # Do not turn an unknown cleanup outcome into permission to run.
                path = runtime / 'scored-trials' / trial_id / 'result.json'
                if not path.exists():
                    raise
                result = json.loads(path.read_text())
                if not cleanup_complete(result):
                    raise
            if not cleanup_complete(result):
                raise RuntimeError('Attempt cleanup failed: ' + trial_id)
            completed[trial_id] = result
            stop = runtime / 'scored-attempts' / trial_id / 'provider-stop.json'
            if stop.exists():
                print(json.dumps(dict(status='provider_stopped', completed=len(completed), intended=178,
                    trial_id=trial_id, reason=json.loads(stop.read_text())['reason'])), flush=True)
                return
            print(json.dumps(dict(status='complete' if len(completed) == 178 else 'running',
                completed=len(completed), intended=178, trial_id=trial_id, scores=counts(completed))), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-manual-top-up', metavar='STOPPED_TRIAL_ID',
        help='Use only after the user confirms a manually funded top-up; never retries the stopped task')
    asyncio.run(run(parser.parse_args().confirm_manual_top_up))

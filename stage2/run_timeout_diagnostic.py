"""Qualify/run exactly 30 separately labelled timeout diagnostic attempts."""
import argparse
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import threading
import unittest

from credit_only_policy import MODE
from model_protocol import freeze_protocol
from recovery_agents import agent_factory
from retry_experiment import (ANCESTORS, sources, validate_qualification, digest,
                              coverage, cleanup_complete, ORIGINAL)
from retry_policy import SETTINGS, require_policy
from retry_runtime import Clock, Cooldown
from run_credit_only import hold, pending_stops
from scored_gateway import durable_json, private_directory
from scored_trial import run_trial, docker
from timeout_diagnostic import (EXPERIMENT, PARENT, DEPLOYMENT, REGISTRATION, QUALIFICATION,
                                ADDED, POLICY, select, parent_rows, observe, summarise)


def bindings(root):
    return dict(sources(root), **{name: digest(root / 'stage2' / name) for name in ADDED})


def lock_all(stack, root):
    for base in (*ANCESTORS, PARENT, root):
        hold(stack, base / '.runtime/stage2', 'matrix.lock')
        if base != root:
            for name in ('scored.lock', 'gateway.lock'):
                hold(stack, base / '.runtime/stage2', name)


def parent_binding(root):
    import host_environment
    proof = validate_qualification(root)
    original_proof = validate_qualification(PARENT)
    if proof != original_proof or proof['host_environment'] != host_environment.snapshot():
        raise ValueError('Inherited qualification/host drift')
    reg_path = PARENT / '.runtime/stage2/corrected-matrix.json'
    reg = json.loads(reg_path.read_text())
    if reg['sources'] != sources(PARENT) or sources(root) != reg['sources']:
        raise ValueError('Unchanged baseline runtime required')
    rows = parent_rows()
    return dict(parent_registration_sha256=digest(reg_path),
        parent_results_sha256={r['trial_id']: r['result_sha256'] for r in rows},
        cells=select(rows), sources=bindings(root), gateway_image=proof['gateway_image'],
        guard_image=proof['guard_image'], host_environment=proof['host_environment'],
        model_protocol_sha256=SETTINGS.fingerprint())


def qualify(root):
    from retry_runtime_probe import probe
    runtime = private_directory(root / '.runtime/stage2')
    with ExitStack() as stack:
        lock_all(stack, root)
        if docker('ps', '-q', '--filter', 'name=uts-scored-'):
            raise ValueError('Another trial is active')
        require_policy(runtime)
        identity = parent_binding(root)
        freeze_protocol(runtime, SETTINGS)
        log = io.StringIO()
        result = unittest.TextTestRunner(stream=log).run(
            unittest.defaultTestLoader.loadTestsFromNames(['test_timeout_diagnostic',
                'test_retry_experiment', 'test_retry_gateway', 'test_rate_limit_candidate']))
        if not result.wasSuccessful() or result.skipped:
            raise ValueError('Diagnostic offline tests failed: ' + log.getvalue()[-2500:])
        checks = []
        for harness in ('terminus-2', 'openhands'):
            check = asyncio.run(probe(root, identity['gateway_image'], identity['guard_image'], harness))
            if check['status'] != 'passed':
                raise ValueError('Fresh isolated synthetic fixture failed: ' + harness)
            checks.append(check)
            print(json.dumps(dict(status='synthetic_passed', harness=harness, live_api_calls=0)), flush=True)
        if parent_binding(root) != identity:
            raise ValueError('Sources or original evidence changed during qualification')
        proof = dict(identity, experiment=EXPERIMENT, policy=POLICY, status='passed',
            live_api_calls=0, offline_tests=result.testsRun, synthetic=checks,
            qualified_utc=datetime.now(timezone.utc).isoformat())
        durable_json(runtime / QUALIFICATION, proof)
        return dict(status='qualified', intended=len(identity['cells']), offline_tests=result.testsRun,
                    live_api_calls=0, qualification_sha256=digest(runtime / QUALIFICATION))


def qualified(root):
    runtime = root / '.runtime/stage2'
    proof = json.loads((runtime / QUALIFICATION).read_text())
    identity = parent_binding(root)
    if (proof.get('experiment') != EXPERIMENT or proof.get('policy') != POLICY
            or proof.get('status') != 'passed' or proof.get('live_api_calls') != 0
            or any(proof.get(k) != v for k, v in identity.items())):
        raise ValueError('Current diagnostic qualification required')
    checks = proof.get('synthetic', [])
    if (len(checks) != 2 or {c.get('harness') for c in checks} != {'terminus-2', 'openhands'}
            or any(c.get('status') != 'passed' or c.get('live_api_calls') != 0
                   or not c.get('checks') or not all(v is True for v in c['checks'].values()) for c in checks)
            or not isinstance(proof.get('offline_tests'), int) or proof['offline_tests'] < 60):
        raise ValueError('Both real harness fixtures and offline tests must pass')
    return identity


async def dispatch(root, descriptor):
    runtime = root / '.runtime/stage2'
    intended = descriptor['cells']
    completed, partial = coverage(runtime, intended)
    if partial:
        raise ValueError('Interrupted diagnostic retained, not automatically replayed')
    if any(r.get('model_revoked') is not True or r.get('model_protocol_sha256') != SETTINGS.fingerprint()
           for r in completed.values()):
        raise ValueError('Existing diagnostic revocation/protocol needs inspection')
    if pending_stops(runtime, completed):
        raise ValueError('Provider stop requires inspection, no automatic funding')
    parent = json.loads((ORIGINAL / '.runtime/stage2/baseline-matrix.json').read_text())
    for cell in intended:
        name = cell['trial_id']
        if name in completed:
            continue
        identity = qualified(root)
        if any(descriptor.get(k) != v for k, v in identity.items()):
            raise ValueError('Diagnostic registration drift')
        if digest(runtime / QUALIFICATION) != descriptor['qualification_sha256']:
            raise ValueError('Diagnostic qualification changed')
        cooldown = Cooldown(runtime, Clock())
        if cooldown.until > cooldown.clock.monotonic():
            await asyncio.to_thread(cooldown.wait, cooldown.until + 1, threading.Event())
        print(json.dumps(dict(status='starting', completed=len(completed), intended=30, trial_id=name)), flush=True)
        try:
            result = await run_trial(root=root, trial_id=name, task_id=cell['task_id'], stage='final',
                agent_factory=agent_factory(cell['harness'], root), model_settings=SETTINGS,
                gateway_image=descriptor['gateway_image'], guard_image=descriptor['guard_image'],
                setup_timeout_seconds=parent['admission']['setup_timeout_seconds'], accounting_mode=MODE)
        except Exception:
            path = runtime / 'scored-trials' / name / 'result.json'
            if not path.exists():
                raise
            result = json.loads(path.read_text())
            if not cleanup_complete(result):
                raise
        if (not cleanup_complete(result) or result.get('model_revoked') is not True
                or result.get('model_protocol_sha256') != SETTINGS.fingerprint()):
            raise RuntimeError('Diagnostic cleanup incomplete')
        if not (runtime / 'scored-trials' / name / 'result.json').is_file():
            raise RuntimeError('No durable diagnostic result')
        completed[name] = result
        rows = [observe(runtime, c, completed[c['trial_id']]) for c in intended if c['trial_id'] in completed]
        print(json.dumps(dict(status='complete' if len(completed) == 30 else 'running', **summarise(rows))), flush=True)
        if (runtime / 'scored-attempts' / name / 'provider-stop.json').exists():
            print(json.dumps(dict(status='provider_stopped', trial_id=name)), flush=True)
            return


async def run(root):
    runtime = private_directory(root / '.runtime/stage2')
    with ExitStack() as stack:
        lock_all(stack, root)
        if docker('ps', '-q', '--filter', 'name=uts-scored-'):
            raise ValueError('Another trial is active')
        identity = qualified(root)
        descriptor = dict(identity, experiment=EXPERIMENT, policy=POLICY,
                          qualification_sha256=digest(runtime / QUALIFICATION))
        path = runtime / REGISTRATION
        if not path.exists():
            if any((runtime / folder).exists() for folder in ('scored-trials', 'scored-attempts')):
                raise ValueError('Unregistered existing diagnostic work')
            durable_json(path, descriptor)
        if json.loads(path.read_text()) != descriptor:
            raise ValueError('Immutable diagnostic registration mismatch')
        await dispatch(root, descriptor)


def report(root):
    runtime = root / '.runtime/stage2'
    descriptor = json.loads((runtime / REGISTRATION).read_text())
    identity = qualified(root)
    if any(descriptor.get(k) != v for k, v in identity.items()):
        raise ValueError('Report identity drift')
    completed, partial = coverage(runtime, descriptor['cells'])
    rows = [observe(runtime, c, completed[c['trial_id']]) for c in descriptor['cells'] if c['trial_id'] in completed]
    return dict(experiment=EXPERIMENT, policy=POLICY, registration_sha256=digest(runtime / REGISTRATION),
        checked_utc=datetime.now(timezone.utc).isoformat(), summary=summarise(rows),
        conditions={h: summarise([r for r in rows if r['harness'] == h], intended=n)
                    for h, n in (('terminus-2', 11), ('openhands', 19))},
        started_without_result=partial, rows=rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['qualify', 'run', 'report'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT:
        raise SystemExit('Use only the separate diagnostic deployment')
    os.umask(0o077)
    if args.action == 'run':
        asyncio.run(run(root))
    else:
        print(json.dumps(qualify(root) if args.action == 'qualify' else report(root)))

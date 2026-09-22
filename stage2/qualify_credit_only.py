"""Native offline qualification, then a locked synthetic lifecycle. No paid calls."""
import argparse
import asyncio
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import subprocess
import unittest

from credit_only_experiment import (ORIGINAL, PREDECESSOR, DEPLOYMENT, QUALIFICATION,
    digest, sources, source_invariants)
from credit_only_policy import EXPERIMENT, POLICY, POLICY_FILE, require_policy
from scored_gateway import durable_json, private_directory


def command(*args):
    return subprocess.check_output(args, text=True, stderr=subprocess.PIPE, timeout=180)


def offline(root):
    import host_environment
    root = Path(root)
    current, parent = source_invariants(root)
    runtime = private_directory(root / '.runtime/stage2')
    # Build derives from the existing immutable qualified gateway, not a new
    # dependency installation. The tag is private to this build, never active.
    tag = 'uts-credit-only-parent:20260922'
    command('docker', 'tag', parent['gateway_image'], tag)
    image = command('docker', 'build', '--quiet', '--pull=false', '--network=none',
        '--build-arg', 'PARENT=' + tag, '-f', str(root / 'stage2/fixtures/Dockerfile.credit-only'), str(root / 'stage2')).strip()
    old, new = json.loads(command('docker', 'inspect', parent['gateway_image'], image))
    if new['RootFS']['Layers'][:len(old['RootFS']['Layers'])] != old['RootFS']['Layers']:
        raise ValueError('Qualified parent layers changed')
    expected_config = dict(old['Config'], Entrypoint=['python', '/study/stage2/credit_only_gateway.py'])
    if new['Config'] != expected_config:
        raise ValueError('Unexpected gateway runtime configuration change')
    image_names = ['gateway_http.py', 'credit_only_policy.py', 'credit_only_gateway.py',
                   'credit_only_accounting.py', 'credit_only_runtime_probe.py', 'test_credit_only_gateway.py']
    code = 'import pathlib,hashlib,json;print(json.dumps({n:hashlib.sha256((pathlib.Path("/study/stage2")/n).read_bytes()).hexdigest() for n in ' + repr(image_names) + '}))'
    installed = json.loads(command('docker', 'run', '--rm', '--network=none', '--read-only',
        '--entrypoint', 'python', image, '-c', code))
    if installed != {name: current[name] for name in image_names}:
        raise ValueError('Image/host gateway source mismatch')
    image_test = command('docker', 'run', '--rm', '--network=none', '--read-only',
        '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m', '--entrypoint', 'python', '-w', '/study/stage2', image,
        '-c', 'import unittest,json,sys; r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromName("test_credit_only_gateway")); print(json.dumps(dict(tests_run=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped))));sys.exit(not r.wasSuccessful())')
    image_tests = json.loads(image_test.strip().splitlines()[-1])
    if image_tests['tests_run'] < 17 or image_tests['errors'] or image_tests['failures'] or image_tests['skipped']:
        raise ValueError('Image gateway test suite incomplete')
    durable_json(runtime / 'credit-only-image-tests.json', dict(image_tests, sources=current, gateway_image=image,
        parent_gateway=parent['gateway_image'], image_sources_match=True, live_api_calls=0))
    output = io.StringIO()
    suite = unittest.defaultTestLoader.discover(str(root / 'stage2'), pattern='test_*.py')
    result = unittest.TextTestRunner(stream=output, verbosity=1).run(suite)
    # Full suite owns fake APIs only. Preserve diagnostic output privately;
    # avoid exposing source task text or secret-bearing exception prose.
    with (runtime / 'credit-only-offline-tests.log').open('x') as handle:
        handle.write(output.getvalue())
    skips = [{'test': test.id(), 'reason': reason} for test, reason in result.skipped]
    allowed_skips = all('spending_checkpoint' in item['test'] for item in skips)
    passed = result.wasSuccessful() and allowed_skips and result.testsRun > 0 and sources(root) == current
    proof = dict(status='passed' if passed else 'failed', tests_run=result.testsRun,
        failures=len(result.failures), errors=len(result.errors), skipped=skips,
        sources=current, host_environment=host_environment.snapshot(), gateway_image=image,
        parent_gateway=parent['gateway_image'], live_api_calls=0)
    durable_json(runtime / 'credit-only-offline-tests.json', proof)
    if not passed:
        raise ValueError('Native offline suite did not qualify; preserve evidence and correct before scoring')
    return proof


async def runtime_check(root):
    from run_credit_only import hold
    from credit_only_runtime_probe import probe
    root = Path(root)
    runtime = root / '.runtime/stage2'
    current, parent = source_invariants(root)
    offline_proof = json.loads((runtime / 'credit-only-offline-tests.json').read_text())
    image_proof = json.loads((runtime / 'credit-only-image-tests.json').read_text())
    if (offline_proof['status'] != 'passed' or offline_proof['sources'] != current
            or image_proof['sources'] != current or image_proof['gateway_image'] != offline_proof['gateway_image']):
        raise ValueError('Current native offline and image tests required')
    with ExitStack() as stack:
        for base in (ORIGINAL, PREDECESSOR, root):
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                hold(stack, base / '.runtime/stage2', name)
        transition = json.loads((ORIGINAL / '.runtime/stage2/accounting-runtime-transition-v1.json').read_text())
        synthetic = await probe(root, offline_proof['gateway_image'], transition['guard_image'])
        if synthetic['status'] != 'passed' or not all(synthetic['checks'].values()):
            raise ValueError('Synthetic lifecycle did not qualify; no paid calls admitted')
        policy = runtime / POLICY_FILE
        if not policy.exists(): durable_json(policy, POLICY)
        require_policy(runtime)
        proof = dict(experiment=EXPERIMENT, policy=POLICY, sources=current,
            gateway_image=offline_proof['gateway_image'], parent_gateway=parent['gateway_image'],
            guard_image=transition['guard_image'], host_environment=synthetic['host_environment'],
            model_protocol_sha256=synthetic['model_protocol_sha256'], live_api_calls=0,
            offline_passed=True, synthetic_passed=True, image_sources_match=True,
            evidence_sha256={name: digest(runtime / name) for name in (
                'credit-only-offline-tests.json', 'credit-only-image-tests.json', 'credit-only-synthetic.json')})
        durable_json(runtime / QUALIFICATION, proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['offline', 'runtime'])
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT:
        raise SystemExit('Qualify only the separate native deployment')
    os.umask(0o077)
    proof = offline(root) if args.phase == 'offline' else asyncio.run(runtime_check(root))
    print(json.dumps(dict(status='passed', phase=args.phase, live_api_calls=0,
                         gateway_image=proof['gateway_image'])))

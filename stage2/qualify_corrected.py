"""No paid calls: native tests, frozen gateway build, both real baseline agents."""
import asyncio
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

from credit_only_policy import POLICY as FINANCIAL, POLICY_FILE as FINANCIAL_FILE
from qualify_credit_only import command
from retry_policy import EXPERIMENT, SETTINGS, POLICY, POLICY_FILE
from retry_experiment import DEPLOYMENT, ANCESTORS, QUALIFICATION, digest, source_invariants
from run_credit_only import hold
from scored_gateway import durable_json, private_directory


def qualify(root):
    from retry_runtime_probe import probe
    import host_environment
    current, parent = source_invariants(root)
    runtime = private_directory(root / '.runtime/stage2')
    if (runtime / QUALIFICATION).exists(): raise ValueError('Preserve completed qualification')
    folder = Path(tempfile.mkdtemp(prefix='qualification-', dir=runtime))
    with ExitStack() as stack:
        for base in (*ANCESTORS, root):
            for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
                hold(stack, base / '.runtime/stage2', name)
        tag = 'uts-corrected-parent:20260923'
        command('docker', 'tag', parent['gateway_image'], tag)
        image = command('docker', 'build', '--quiet', '--pull=false', '--network=none',
            '--build-arg', 'PARENT=' + tag, '-f', str(root / 'stage2/fixtures/Dockerfile.corrected'), str(root / 'stage2')).strip()
        old, new = json.loads(command('docker', 'inspect', parent['gateway_image'], image))
        if (new['RootFS']['Layers'][:len(old['RootFS']['Layers'])] != old['RootFS']['Layers'] or
                new['Config'] != dict(old['Config'], Entrypoint=['python', '/study/stage2/retry_gateway.py'])):
            raise ValueError('Unexpected gateway base/config change')
        names = ['retry_policy.py', 'retry_runtime.py', 'retry_transport.py', 'retry_gateway.py',
                 'rate_limit_candidate.py', 'retry_runtime_probe.py', 'test_retry_gateway.py', 'test_rate_limit_candidate.py']
        code = 'import pathlib,hashlib,json;print(json.dumps({n:hashlib.sha256((pathlib.Path("/study/stage2")/n).read_bytes()).hexdigest() for n in ' + repr(names) + '}))'
        installed = json.loads(command('docker', 'run', '--rm', '--network=none', '--read-only', '--entrypoint', 'python', image, '-c', code))
        if installed != {name: current[name] for name in names}: raise ValueError('Image source mismatch')
        result = command('docker', 'run', '--rm', '--network=none', '--read-only',
            '--tmpfs', '/tmp:rw,nosuid,nodev,size=32m', '--entrypoint', 'python', '-w', '/study/stage2', image,
            '-c', 'import unittest,json,sys;r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromNames(["test_retry_gateway","test_rate_limit_candidate","test_credit_only_gateway"]));print(json.dumps(dict(tests=r.testsRun,passed=r.wasSuccessful(),skipped=len(r.skipped))));sys.exit(not r.wasSuccessful())')
        tested = json.loads(result.strip().splitlines()[-1])
        if tested['tests'] < 60 or not tested['passed'] or tested['skipped']: raise ValueError('Image tests incomplete')
        durable_json(folder / 'image.json', dict(tested, gateway_image=image, image_sources_match=True))
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.discover(str(root / 'stage2'), pattern='test_*.py'))
        with (folder / 'offline.log').open('x') as handle: handle.write(output.getvalue())
        passed = result.wasSuccessful() and all('spending_checkpoint' in t.id() for t, _ in result.skipped)
        durable_json(folder / 'offline.json', dict(tests=result.testsRun, passed=passed,
            errors=len(result.errors), failures=len(result.failures), skipped=len(result.skipped)))
        if not passed: raise ValueError('Native offline tests failed; inspect private log')
        print(json.dumps(dict(status='offline_passed', tests=result.testsRun, gateway_image=image)), flush=True)
        checks = []
        for harness in ('terminus-2', 'openhands'):
            evidence = asyncio.run(probe(root, image, parent['guard_image'], harness))
            durable_json(folder / (harness + '.json'), evidence)
            checks.append(evidence)
            print(json.dumps(evidence), flush=True)
        durable_json(folder / 'synthetic.json', checks)
        if not all(v['status'] == 'passed' for v in checks): raise ValueError('Native synthetic integration failed')
        if source_invariants(root)[0] != current: raise ValueError('Source changed during qualification')
        for name, value in ((POLICY_FILE, POLICY), (FINANCIAL_FILE, FINANCIAL)):
            if not (runtime / name).exists(): durable_json(runtime / name, value)
            if json.loads((runtime / name).read_text()) != value: raise ValueError('Policy drift')
        proof = dict(status='passed', experiment=EXPERIMENT, policy=POLICY, sources=current,
            gateway_image=image, parent_gateway=parent['gateway_image'], guard_image=parent['guard_image'],
            host_environment=host_environment.snapshot(), model_protocol_sha256=SETTINGS.fingerprint(),
            live_api_calls=0, evidence_folder=folder.name,
            evidence_sha256={name: digest(folder / name) for name in ('offline.json', 'image.json', 'synthetic.json')})
        durable_json(runtime / QUALIFICATION, proof)
        return proof


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT: raise SystemExit('Use the distinct registered Linux deployment')
    os.umask(0o077)
    proof = qualify(root)
    print(json.dumps(dict(status=proof['status'], live_api_calls=0, gateway_image=proof['gateway_image'])))

"""Source-bound native custom qualification, exclusively synthetic model calls."""
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import unittest

from corrected_custom_policy import POLICY, POLICY_FILE, QUALIFICATION, fingerprint
from corrected_custom_study import (DEPLOYMENT, identity, TEST_MODULES, PROBE_CASES, qualified)
from corrected_custom_probe import probe
from qualify_credit_only import command
from retry_experiment import DEPLOYMENT as BASELINE
from retry_runtime import private_read
from run_corrected_custom import lock_all
from scored_gateway import durable_json, private_directory
from scored_trial import docker

IMAGE_FILES = ('credit_only_gateway.py', 'retry_gateway.py', 'corrected_custom_policy.py',
    'corrected_custom_gateway.py', 'corrected_custom_probe.py', 'custom_control.py')


def qualify(root):
    import host_environment
    root = Path(root)
    runtime = private_directory(root / '.runtime/stage2')
    if (runtime / QUALIFICATION).exists() or (runtime / QUALIFICATION).is_symlink():
        raise ValueError('Preserve existing qualification; do not repeat it')
    with ExitStack() as stack:
        lock_all(stack, root)
        if docker('ps', '-q', '--filter', 'name=uts-scored-'):
            raise ValueError('Another task is active')
        current, host = identity(root), host_environment.snapshot()
        # Read only already completed baseline configuration, not its answers.
        parent = private_read(BASELINE / '.runtime/stage2/corrected-qualification.json')
        tag = 'uts-custom-corrected-parent:20260926'
        command('docker', 'tag', parent['gateway_image'], tag)
        image = command('docker', 'build', '--quiet', '--pull=false', '--network=none',
            '--build-arg', 'PARENT=' + tag, '-f', str(root / 'stage2/fixtures/Dockerfile.custom-corrected'),
            str(root / 'stage2')).strip()
        old, new = json.loads(command('docker', 'inspect', parent['gateway_image'], image))
        if (new['RootFS']['Layers'][:len(old['RootFS']['Layers'])] != old['RootFS']['Layers']
                or new['Config'] != dict(old['Config'], Entrypoint=['python', '/study/stage2/corrected_custom_gateway.py'])):
            raise ValueError('Unexpected custom gateway base/config change')
        code = ('import pathlib,hashlib,json;print(json.dumps({n:hashlib.sha256('
                '(pathlib.Path("/study/stage2")/n).read_bytes()).hexdigest() for n in ' + repr(IMAGE_FILES) + '}))')
        installed = json.loads(command('docker', 'run', '--rm', '--network=none', '--read-only',
            '--entrypoint', 'python', image, '-c', code))
        if installed != {n: current['sources'][n] for n in IMAGE_FILES}:
            raise ValueError('Custom gateway source mismatch')
        output = io.StringIO()
        result = unittest.TextTestRunner(stream=output).run(unittest.defaultTestLoader.loadTestsFromNames(TEST_MODULES))
        offline = dict(tests=result.testsRun, passed=result.wasSuccessful(), skipped=len(result.skipped),
            errors=len(result.errors), failures=len(result.failures), modules=list(TEST_MODULES))
        if not result.wasSuccessful() or result.skipped:
            raise ValueError('Native offline tests failed: ' + output.getvalue()[-2500:])
        print(json.dumps(dict(status='offline_passed', **offline)), flush=True)
        checks = []
        for condition, parent_condition in PROBE_CASES:
            evidence = asyncio.run(probe(root, image, parent['guard_image'], condition, parent_condition))
            checks.append(evidence)
            print(json.dumps(dict(status=evidence['status'], condition=condition, parent=parent_condition,
                checks=evidence['checks'], live_api_calls=0)), flush=True)
            if evidence['status'] != 'passed':
                raise ValueError('Native custom fixture failed')
        if identity(root) != current or host_environment.snapshot() != host:
            raise ValueError('Custom source or environment changed during qualification')
        policy_path = runtime / POLICY_FILE
        if not policy_path.exists():
            durable_json(policy_path, POLICY)
        if private_read(policy_path) != POLICY:
            raise ValueError('Explicit custom policy changed')
        proof = dict(current, status='passed', live_api_calls=0, offline=offline, synthetic=checks,
            gateway_image=image, guard_image=parent['guard_image'], image_sources_match=True,
            host_environment=host, setup_timeout_seconds=900,
            qualified_utc=datetime.now(timezone.utc).isoformat())
        durable_json(runtime / QUALIFICATION, proof)
        qualified(root)
        return dict(status='qualified', qualification_sha256=fingerprint(proof), live_api_calls=0,
            offline_tests=result.testsRun, native_cases=len(checks))


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    if root != DEPLOYMENT:
        raise SystemExit('Use only the separate native custom deployment')
    os.umask(0o077)
    print(json.dumps(qualify(root)))

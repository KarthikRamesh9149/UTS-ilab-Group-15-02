"""Produce C0-NC native evidence with an isolated fake model, never paid calls."""
import asyncio
from contextlib import ExitStack
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import tempfile
import unittest

import direct_final_evidence as original
import no_cutoff_custom_policy as policy
import no_cutoff_custom_runtime as identity
from no_cutoff_custom_probe import probe
from no_cutoff_custom_study import read_candidate, qualified
from custom_dispatch_stop import BoundaryStop
from credit_only_experiment import digest
from qualify_credit_only import command
from retry_experiment import DEPLOYMENT as BASELINE
from retry_runtime import private_read
from run_no_cutoff_custom import lock_all
from scored_gateway import durable_json, private_directory
from scored_trial import docker

IMAGE_FILES = ('credit_only_gateway.py', 'retry_gateway.py', 'portable_custom_policy.py',
    'portable_final_selection.py', 'portable_custom_probe.py', 'custom_control.py',
    'deadline_custom_contract.py', 'deadline_custom_policy.py', 'deadline_final_selection.py',
    'direct_final_candidate.py', 'no_cutoff_custom_contract.py', 'no_cutoff_custom_policy.py',
    'no_cutoff_custom_gateway.py', 'no_cutoff_custom_probe.py')


def save_once(path, value):
    if path.exists() or path.is_symlink():
        if policy.fingerprint(private_read(path)) != policy.fingerprint(value):
            raise ValueError('Preserve existing, different qualification input')
    else:
        durable_json(path, value)


def build_gateway(root, sources):
    parent = private_read(BASELINE / '.runtime/stage2/corrected-qualification.json')
    tag = 'uts-custom-no-cutoff-parent:20260928'
    command('docker', 'tag', parent['gateway_image'], tag)
    image = command('docker', 'build', '--quiet', '--pull=false', '--network=none',
        '--build-arg', 'PARENT=' + tag, '-f', str(root / 'stage2/fixtures/Dockerfile.custom-no-cutoff'),
        str(root / 'stage2')).strip()
    old, new = json.loads(command('docker', 'inspect', parent['gateway_image'], image))
    entrypoint = ['python', '/study/stage2/no_cutoff_custom_gateway.py']
    if (new['RootFS']['Layers'][:len(old['RootFS']['Layers'])] != old['RootFS']['Layers']
            or new['Config'] != dict(old['Config'], Entrypoint=entrypoint)):
        raise ValueError('Unexpected gateway base or configuration change')
    script = ('import pathlib,hashlib,json;print(json.dumps({n:hashlib.sha256('
        '(pathlib.Path("/study/stage2")/n).read_bytes()).hexdigest() for n in ' + repr(IMAGE_FILES) + '}))')
    installed = json.loads(command('docker', 'run', '--rm', '--network=none', '--read-only',
        '--entrypoint', 'python', image, '-c', script))
    if installed != {name: sources[name] for name in IMAGE_FILES}:
        raise ValueError('Gateway image does not contain the qualified source')
    # Exercise both entry-point imports inside the real lean gateway image.
    command('docker', 'run', '--rm', '--network=none', '--read-only', '--entrypoint', 'python',
        image, '-c', 'import no_cutoff_custom_gateway, no_cutoff_custom_probe')
    return image, parent['guard_image']


def regression(folder):
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output).run(
        unittest.defaultTestLoader.loadTestsFromNames(policy.TEST_MODULES))
    report = dict(tests=result.testsRun, passed=result.wasSuccessful(), skipped=len(result.skipped),
        errors=len(result.errors), failures=len(result.failures), modules=list(policy.TEST_MODULES))
    durable_json(folder / 'regression.json', report)
    # Private diagnostic output, including failures, is retained, not printed.
    with (folder / 'regression.txt').open('x') as stream:
        stream.write(output.getvalue())
    if not result.wasSuccessful() or result.skipped:
        raise ValueError('Native regression failed; private report retained')
    return report


def qualify(root):
    root = Path(root)
    if root.resolve() != identity.DEPLOYMENT:
        raise ValueError('Use only the separate C0-NC deployment')
    rt = private_directory(root / '.runtime/stage2')
    if (rt / policy.QUALIFICATION).exists() or (rt / policy.QUALIFICATION).is_symlink():
        raise ValueError('Preserve completed qualification; do not repeat it')
    if BoundaryStop(rt).requested():
        raise ValueError('Persistent stop forbids automatic qualification')
    for name in (policy.BLOCKS, 'scored-trials', 'scored-attempts'):
        path = rt / name
        if path.is_symlink() or path.exists() and any(path.iterdir()):
            raise ValueError('Do not qualify over a registered or started deployment')
    document = read_candidate(root)
    # The original collector locks its ancestors; authenticate before taking
    # those same locks, then recheck the exact evidence under our locks.
    authenticated = original.authenticate(root, document)
    with ExitStack() as stack:
        lock_all(stack, root)
        original.recheck(root, document, authenticated)
        if docker('ps', '-aq', '--filter', 'name=uts-scored-'):
            raise ValueError('An owned task container still exists')
        current = identity.inspect(root, document)
        for name, value in ((policy.AUTHENTICATION_FILE, authenticated),
                (policy.RUNTIME_FILE, current), (policy.POLICY_FILE, policy.POLICY)):
            save_once(rt / name, value)
        folder = Path(tempfile.mkdtemp(prefix='native-no-cutoff-qualification-', dir=rt))
        image, guard = build_gateway(root, current['sources'])
        offline = regression(folder)
        print(json.dumps(dict(status='offline_passed', **offline)), flush=True)
        native = []
        for mode in policy.PROBE_MODES:
            evidence = asyncio.run(probe(root, image, guard, document, mode))
            native.append(evidence)
            print(json.dumps(dict(status=evidence['status'], condition=policy.CONDITION,
                mode=mode, checks=evidence['checks'], live_api_calls=0)), flush=True)
            if evidence['status'] != 'passed':
                raise ValueError('Native no-cutoff fixture failed; evidence retained')
        original.recheck(root, document, authenticated)
        if policy.fingerprint(identity.inspect(root, document)) != policy.fingerprint(current):
            raise ValueError('Source, dependencies, images or host changed during qualification')
        # Bind actual producer output as well as source and runtime. These
        # files are private evidence, not an alternate paid admission route.
        evidence_paths = [folder / 'regression.json', folder / 'regression.txt']
        for case in native:
            fixture = root / case['runtime_path']
            evidence_paths.append(fixture / 'evidence.json')
            evidence_paths.append(fixture / '.runtime/stage2/scored-trials' /
                ('synthetic-nc-' + case['mode']) / 'result.json')
        bound = {str(path.relative_to(root)): digest(path) for path in evidence_paths}
        proof = dict(kind='native_no_cutoff_development_qualification', experiment=policy.EXPERIMENT,
            status='passed', condition=policy.CONDITION, parent='C0', base_parent=None,
            candidate_version=policy.CANDIDATE_VERSION, original_candidate_sha256=policy.fingerprint(document),
            original_authentication_sha256=policy.fingerprint(authenticated),
            runtime_identity_sha256=policy.fingerprint(current), policy_sha256=policy.fingerprint(policy.POLICY),
            model_protocol_sha256=policy.SETTINGS.fingerprint(), input_manifest_sha256=policy.INPUT_SHA256,
            execution_contract=policy.execution_contract(), sources=current['sources'],
            sources_sha256=current['sources_sha256'], source_transition=policy.source_transition(document, current['sources']),
            dependencies=current['dependencies'], python_runtime=current['python_runtime'],
            host_environment=current['host_environment'], setup_timeout_seconds=900, live_api_calls=0,
            offline=offline, synthetic=native, evidence_files=bound,
            regression_path=str(folder.relative_to(root)),
            gateway_image=image, guard_image=guard, image_sources_match=True,
            qualified_utc=datetime.now(timezone.utc).isoformat())
        policy.validate_qualification(document, proof)
        durable_json(rt / policy.QUALIFICATION, proof)
        qualified(root)
        return dict(status='qualified', qualification_sha256=policy.fingerprint(proof),
            live_api_calls=0, offline_tests=offline['tests'], native_cases=len(native))


if __name__ == '__main__':
    os.umask(0o077)
    print(json.dumps(qualify(Path(__file__).resolve().parents[1])))

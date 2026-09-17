"""One PBS-only trusted Harbor fixture check; no model or benchmark execution.

Requires the pinned Harbor Python 3.12 environment on the CETUS controller.
Creates/stops only its own uniquely named offline instance. Retains evidence.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import tempfile

from harbor.models.task.task import Task
from harbor.models.task.config import NetworkMode, NetworkPolicy
from harbor.models.trial.paths import TrialPaths
from cetus_apptainer_qualification import FLAGS
from cetus_instance_transport import InstanceTransport, run_process
from cetus_harbor_environment import CetusAttachedEnvironment
from local_trace import PhaseRecorder, TraceSpool
from local_observation import DetailObserver
from trial_execution import execute_phases


class TrustedFixtureAgent:
    async def setup(self, environment):
        result = await environment.exec("test ! -e /shared/homes && test -z \"${UTS_FAKE_CONTROLLER_SECRET:-}\"")
        if result.return_code:
            raise RuntimeError('Fixture isolation check failed')

    async def run(self, instruction, environment, context):
        # Fixed synthetic command, never a model-generated command or solution
        # to an official benchmark task. Paired with fixtures/lifecycle/tests.
        result = await environment.exec("python3 -c \"from pathlib import Path; Path('/tmp/uts-lifecycle-result').write_text('UTS_LIFECYCLE_OK')\"")
        if result.return_code:
            raise RuntimeError('Fixture command failed')


async def check(output):
    job = os.environ.get('PBS_JOBID', '')
    if not re.fullmatch(r'[0-9]+\.[A-Za-z0-9.-]+', job):
        raise RuntimeError('Submit through PBS; no login-node execution')
    os.umask(0o077)
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    report = dict(scope='trusted_harbor_fixture_not_benchmark', job=job, complete=False,
                  scored_trials=0, model_requests=0, external_inference_requests=0)
    name = 'uts-harbor-' + job.split('.')[0] + '-fixture'
    start_attempted = stopped = False
    async def stop_instance():
        nonlocal stopped
        result = await run_process(['apptainer', 'instance', 'stop', name], timeout=30)
        report['stop_exit'] = result.return_code
        if result.return_code:
            raise RuntimeError('Instance cleanup failed')
        stopped = True

    try:
        scratch = Path(tempfile.mkdtemp(prefix='uts-harbor-check-', dir='/scratch'))
        report['scratch_retained'] = str(scratch)
        for key, subdir in [('APPTAINER_CACHEDIR', 'cache'), ('APPTAINER_TMPDIR', 'tmp')]:
            (scratch / subdir).mkdir(mode=0o700)
            os.environ[key] = str(scratch / subdir)
        os.environ['UTS_FAKE_CONTROLLER_SECRET'] = 'synthetic-only'
        image = scratch / 'fixture.sif'
        pull = await run_process(['apptainer', 'pull', str(image), 'docker://python:3.12-slim-bookworm'], timeout=180)
        report['pull_exit'] = pull.return_code
        if pull.return_code:
            raise RuntimeError('Fixture image preparation failed')
        digest = hashlib.sha256()
        with image.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                digest.update(chunk)
        report['fixture_image_sha256'] = digest.hexdigest()
        start_attempted = True
        started = await run_process(['apptainer', 'instance', 'start'] + FLAGS + ['--fakeroot', str(image), name], timeout=45)
        report['start_exit'] = started.return_code
        if started.return_code:
            raise RuntimeError('Fixture instance start failed')
        task = Task(Path(__file__).parent / 'fixtures/lifecycle')
        paths = TrialPaths(output / 'trial')
        recorder = PhaseRecorder(TraceSpool(output / 'traces'), trial_id='fixture-' + job.split('.')[0],
            task_id='fixture', harness='terminus-2', protocol_sha256='0' * 64)
        # Harness label here is for schema compatibility, not a Terminus run.
        report['agent'] = 'TrustedFixtureAgent'
        details = DetailObserver(recorder)
        environment = CetusAttachedEnvironment(environment_dir=task.paths.environment_dir,
            environment_name='trusted-fixture', session_id=name, trial_paths=paths,
            task_env_config=task.config.environment, network_policy=NetworkPolicy(network_mode=NetworkMode.NO_NETWORK),
            transport=InstanceTransport(name), stop_instance=stop_instance, detail_observer=details)
        await environment.start()
        async def revoke():
            report['synthetic_model_revocation'] = True
        report['lifecycle'] = await execute_phases(agent=TrustedFixtureAgent(), environment=environment,
            task=task, paths=paths, revoke_model=revoke, setup_timeout_seconds=30, phase_observer=recorder)
        report['trace_errors'] = details.errors
        rejected = await run_process(['apptainer', 'exec', 'instance://' + name, 'true'], timeout=10)
        report['stopped_rejects_exec'] = rejected.return_code != 0
        lifecycle = report['lifecycle']
        report['complete'] = (lifecycle['status'] == 'verified' and
            lifecycle['verifier_result']['rewards'].get('reward') == 1 and
            not lifecycle.get('trace_errors') and not details.errors and stopped and report['stopped_rejects_exec'])
    except Exception as error:
        report['error_type'] = type(error).__name__
    finally:
        if start_attempted and not stopped:
            try:
                await stop_instance()
            except Exception as error:
                report['cleanup_error_type'] = type(error).__name__
                report['complete'] = False
        (output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    async def bounded():
        task = asyncio.current_task()
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGTERM, task.cancel)
        return await check(args.output)
    result = asyncio.run(bounded())
    print(json.dumps({'complete': result['complete'], 'scored_trials': 0, 'output': str(args.output)}))
    return 0 if result['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

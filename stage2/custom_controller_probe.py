"""Disposable real-container qualification of custom control and job lifecycle."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import uuid

from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths
from langchain_core.messages import AIMessage
from custom_backend import HarborSandbox
from custom_control import Condition
from custom_jobs import ContainerJobs
from custom_runner import CustomRunner
from custom_runner_tests import SequenceModel, completion


async def main(label):
    root = Path(__file__).resolve().parents[1]
    if not label.isalnum():
        raise ValueError('Alphanumeric evidence label required')
    output = root / ('stage2/custom_controller_probe_' + label + '.json')
    if output.exists():
        raise ValueError('Preserve previous evidence')
    trial = Path(tempfile.mkdtemp(prefix='custom-controller-', dir=root / '.runtime/stage2'))
    name = 'uts-controller-fixture-' + uuid.uuid4().hex[:10]
    environment = DockerEnvironment(environment_dir=root / 'stage2/fixtures', environment_name=name,
        session_id=name, trial_paths=TrialPaths(trial_dir=trial),
        task_env_config=EnvironmentConfig(docker_image='sha256:f5a99e8abc07be76fa4a1bcc11618e055592213648f27366eeef523db8721f25', cpus=2, memory_mb=1024),
        extra_docker_compose=[root / 'stage2/fixtures/docker-compose-isolation.yaml'])
    evidence = {'kind': 'actual_custom_controller_scripted_model_not_scored', 'live_api_calls': 0,
                'time_utc': datetime.now(timezone.utc).isoformat(), 'checks': {}}
    jobs = None
    try:
        await environment.start(force_build=False)
        backend = HarborSandbox(environment, identifier=name)
        noisy = await backend.aexecute("python3 -c 'print(\"x\" * 2000000)'", timeout=10)
        evidence['checks']['container_side_output_bound'] = noisy.truncated and len(noisy.output) == 64000 and noisy.exit_code == 0
        jobs = ContainerJobs(backend)
        job = await jobs.start('printf JOB_OK', 5)
        for _ in range(50):
            observed = jobs.poll(job['job_id'])
            if observed['status'] == 'finished':
                break
            await asyncio.sleep(.1)
        evidence['checks']['start_poll_result'] = observed.get('output') == 'JOB_OK' and observed.get('exit_code') == 0
        long = await jobs.start('sleep 30', 35)
        interrupted = await jobs.interrupt(long['job_id'])
        evidence['checks']['interrupt_process_group'] = interrupted['status'] == 'finished' and interrupted['exit_code'] != 0
        try:
            await jobs.interrupt('not-a-handle')
        except KeyError:
            evidence['checks']['foreign_handle_rejected'] = True
        else:
            evidence['checks']['foreign_handle_rejected'] = False
        clean = await jobs.start('sleep 30', 35)
        await jobs.close()
        evidence['checks']['cleanup_stops_running_job'] = jobs.poll(clean['job_id'])['status'] == 'finished'
        jobs = None

        model = SequenceModel()
        checks = [{'criterion': 'File contains expected text', 'observation': 'Command output CONTROL_OK', 'satisfied': True}]
        model._sequence = [AIMessage(content='Premature final'),
            AIMessage(content='', tool_calls=[{'name': 'execute', 'id': 'execute-fixture',
                'args': {'command': 'printf CONTROL_OK > /tmp/controller-result; cat /tmp/controller-result'}}]),
            completion('Created and read the required file', checks)]
        runner = CustomRunner(model, backend, Condition('C2', 'C1'), max_model_calls=5)
        result = await runner.run('Create /tmp/controller-result containing CONTROL_OK and read it.', timeout_seconds=30)
        read = await environment.exec('cat /tmp/controller-result', timeout_sec=5)
        evidence['checks'].update(graph_created_file=read.stdout == 'CONTROL_OK',
            explicit_repair_count=result['repair_cycles'] == 1,
            agent_report_not_score=result['outcome'] == 'agent_reported_complete' and result['benchmark_success'] is None,
            exactly_three_model_calls=len(model._calls) == 3,
            no_delegation='task' not in model._tool_names)
        evidence['controller_outcome'] = result
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    except Exception as exc:
        evidence.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1000])
    finally:
        try:
            if jobs is not None:
                await jobs.close()
        finally:
            await environment.stop(delete=True)
    evidence['limitations'] = ['Scripted model, no benchmark tasks or paid inference.',
        'Container is the isolation boundary; command records are not tamper-proof within that task.',
        'Polling returns output after completion, not a live stream.',
        'Full production runtime, budget qualification and experiment freeze remain outstanding.']
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2)
        handle.write('\n')
    print(json.dumps(evidence, indent=2))
    if evidence['status'] != 'passed':
        raise RuntimeError('Controller fixture failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', default='v1')
    asyncio.run(main(parser.parse_args().label))

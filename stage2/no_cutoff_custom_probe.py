"""Actual Harbor lifecycle and C0-NC graph, using a networkless fake model.

The fixture is not a benchmark task. Its scripted provider asserts tool results,
not task answers. No real credential or external model transport is available.
"""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import signal
import shlex
import tempfile
import tomllib
from unittest.mock import patch

from gateway_policy import MODEL, ENDPOINT
from openrouter_transport import TransportError, error_diagnostic
from no_cutoff_custom_policy import SETTINGS
from portable_custom_probe import SyntheticProvider as PreviousProvider

PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII='
PREPARE = ("printf '%s' " + PNG + " | base64 -d > /tmp/uts-fixture.png; "
    "python3 -c \"from pathlib import Path; Path('/tmp/uts-long.txt').write_text(''.join('row-%05d\\n'%i for i in range(16000)))\"; "
    "(while :; do sleep 3600; done) & echo $! > /tmp/uts-background.pid; printf BACKGROUND_READY")
EXPECTED_LOGICAL = 24
FIXTURE_FILE = 'no-cutoff-isolated-fixture.json'
FIXTURE_KIND = 'isolated-synthetic-no-cutoff-not-paid-admission'
PROCESS_CHILD = (
    "import os,signal; from pathlib import Path; p=os.getppid(); "
    "a=Path('/proc/'+str(p)+'/cmdline').read_bytes(); "
    "matched=b'uts_nc_owned_capture_match_fixture' in a; "
    "os.kill(p,signal.SIGTERM) if matched else None; "
    "print('NC_CAPTURE_MATCHED' if matched else 'NC_CAPTURE_UNMATCHED')")
PROCESS_COMMAND = 'exec python3 -c ' + shlex.quote(PROCESS_CHILD)
LARGE_COMMAND = 'python3 -c ' + shlex.quote(
    "assert len(" + repr('x' * 32768) + ") == 32768; print('NC_LARGE_COMMAND_OK')")


def isolated_fixture(runtime, trial, stage):
    from retry_runtime import private_read
    value = private_read(Path(runtime) / FIXTURE_FILE)
    expected = dict(kind=FIXTURE_KIND, paid_launch_ready=False, live_api_calls=0,
        stage='development', condition='C0-NC', trial_id=trial,
        model_protocol_sha256=SETTINGS.fingerprint())
    if (stage != 'development' or trial not in
            {'synthetic-nc-tools', 'synthetic-nc-cancel_setup', 'synthetic-nc-boundary_stop'}
            or value != expected):
        raise ValueError('Only an isolated synthetic fixture is admitted')
    return value


def require_network_isolation():
    if {p.name for p in Path('/sys/class/net').iterdir()} != {'lo'}:
        raise ValueError('Synthetic gateway must have Docker network=none')


from retry_gateway import RetrySession


class FixtureRetrySession(RetrySession):
    """Separate fake-only route; never creates a production qualification."""
    def require_session_policy(self):
        if type(self.client) is not SyntheticProvider:
            raise ValueError('No external provider transport in native rehearsal')
        require_network_isolation()
        isolated_fixture(self.runtime, self.trial_id, self.stage)

    def require_recovery_policy(self):
        self.require_session_policy()


class SyntheticProvider(PreviousProvider):
    """Script actual tools; no external provider/network capability."""
    def complete(self, request, *, on_response_headers):
        assert not any('[Task time remaining]' in (m.get('content') or '')
            for m in request['messages'])
        if self.calls < 10:
            response=super().complete(request, on_response_headers=on_response_headers)
            if self.calls==2:
                # This no-cutoff fixture deliberately takes over a minute. A service
                # must live until verification, not expire on a fixture timer.
                response['choices'][0]['message']['tool_calls'][0]['function']['arguments']=json.dumps({'command':PREPARE})
            return response
        assert request['max_tokens'] == SETTINGS.max_output_tokens
        assert request['temperature'] == request['top_p'] == 1.
        assert request['reasoning'] == {'effort':'high'}
        assert request['provider']['only'] == [ENDPOINT]
        assert request['provider']['allow_fallbacks'] is False
        assert 'max_price' not in request['provider']
        assert all(m.get('content') is None or isinstance(m['content'],str) for m in request['messages'])
        self.calls += 1
        self.last_failure=None
        on_response_headers(error_diagnostic(status=200))
        step=self.calls-2
        tools=[m for m in request['messages'] if m['role']=='tool']
        last=tools[-1]['content'] if tools else ''
        if step==9:
            commands=[('execute',{'command':'sleep 61; printf LONG_COMMAND_OK'})]
        elif step==10:
            assert 'LONG_COMMAND_OK' in last
            commands=[('start_command',{'command':f'sleep 2; printf JOB_{i}'}) for i in range(8)]
        elif step==11:
            self.handles=[json.loads(m['content'])['job_id'] for m in tools[-8:]]
            assert len(set(self.handles))==8
            commands=[('start_command',{'command':f'printf JOB_{i}'}) for i in range(8,73)]
        elif step==12:
            self.handles += [json.loads(m['content'])['job_id'] for m in tools[-65:]]
            assert len(set(self.handles))==73
            commands=[('execute',{'command':'sleep 5; printf JOBS_WAITED'})]
        elif step==13:
            commands=[('poll_command',{'job_id':identifier}) for identifier in self.handles]
        elif step==14:
            assert all(json.loads(m['content']).get('exit_code')==0 for m in tools[-73:])
            commands=[('execute', {'command':PROCESS_COMMAND})]
        elif step==15:
            assert 'NC_CAPTURE_UNMATCHED' in last
            commands=[('execute', {'command':LARGE_COMMAND})]
        elif step==16:
            assert 'NC_LARGE_COMMAND_OK' in last
            commands=[('complete_task',{'summary':''})]
        elif 17 <= step <= 22:
            assert json.loads(last)['status']=='repair_requested'
            assert json.loads(last)['terminal'] is False
            commands=[('complete_task',{'summary':''})]
        elif step==23:
            assert json.loads(last)['repair_number']==7
            commands=[('complete_task',dict(summary='Synthetic no-cutoff lifecycle complete.',
                checks=[dict(criterion='Fixture observations',observation='Long command, 73 jobs and seven repairs observed',satisfied=True)]))]
        else:
            raise ValueError('Unexpected extra synthetic request')
        allowed={t['function']['name'] for t in request['tools']}
        assert all(name in allowed for name,_ in commands)
        message=dict(role='assistant',content=None,tool_calls=[
            dict(id=f'call_{self.calls}_{index}',type='function',
                 function=dict(name=name,arguments=json.dumps(args)))
            for index,(name,args) in enumerate(commands)])
        return dict(id='gen-synthetic-no-cutoff-'+str(self.calls),model=MODEL,provider='DeepInfra',
            object='chat.completion',created=1,choices=[dict(index=0,finish_reason='tool_calls',message=message)],
            usage=dict(prompt_tokens=10,completion_tokens=4,total_tokens=14))


def gateway_fixture(trial, wait):
    require_network_isolation()
    from retry_gateway import serve
    serve('/study', trial, 'development', '/run/trial-token', '/run/openrouter.env',
        '/socket/private/model.sock', completion_wait_seconds=wait,
        client_factory=SyntheticProvider, session_factory=FixtureRetrySession)


async def probe(root, gateway_image, guard_image, document, mode):
    condition, parent, base_parent = 'C0-NC', 'C0', None
    import host_environment
    from no_cutoff_custom_agent import agent_factory, runtime_bundle
    from no_cutoff_custom_policy import (EXPERIMENT, fingerprint, PYTHON_SHA256, probe_checks)
    from no_cutoff_custom_runtime import sources
    from production_compose import compose_runtime
    from scored_gateway import durable_json, private_directory
    from scored_trial import run_trial, docker, audit_task
    from qualify_oracle import frozen_dataset
    from harbor.models.task.task import Task
    from custom_dispatch_stop import BoundaryStop
    from run_no_cutoff_custom import dispatch
    probe_checks(mode)
    root = Path(root)
    os.umask(0o077)
    before, host = sources(root, document), host_environment.snapshot()
    runtime = private_directory(root / '.runtime/stage2')
    fixture = Path(tempfile.mkdtemp(prefix='native-no-cutoff-' + condition + '-' + mode + '-', dir=runtime))
    (fixture / 'stage2').mkdir(mode=0o700)
    manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
    durable_json(fixture / 'stage2/input_manifest.json', dict(manifest,
        development_ids=['deadline-lifecycle'], all_task_ids=['deadline-lifecycle']))
    state = private_directory(fixture / '.runtime/stage2')
    # A private copy, not a writable link back into the qualified deployment.
    shutil.copyfile(runtime_bundle(root).path, runtime_bundle(fixture).path)
    bundle_proof = runtime_bundle(fixture).validate()
    cell = dict(trial_id='synthetic-nc-' + mode, task_id='deadline-lifecycle', harness=condition)
    # Not one of the registered benchmark keys, and not a completed proof.
    # Production require_trial/validate_qualification reject this record.
    fixture_record = dict(kind=FIXTURE_KIND, paid_launch_ready=False, live_api_calls=0,
        stage='development', condition=condition, trial_id=cell['trial_id'],
        model_protocol_sha256=SETTINGS.fingerprint())
    durable_json(state / FIXTURE_FILE, fixture_record)
    block = dict(kind=FIXTURE_KIND, cells=[cell], condition=condition)
    (fixture / '.env').write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
    task = Task(root / 'stage2/fixtures/deadline-lifecycle')
    assert 'build-pov-ray' in manifest['development_ids']
    metadata = tomllib.loads((frozen_dataset(root) / 'build-pov-ray/task.toml').read_text())['environment']
    task.config.environment.docker_image = docker('image', 'inspect', metadata['docker_image'], '--format', '{{.Id}}')
    audits, pythonless = [], []
    def audit(main, *args):
        audit_task(main, *args)
        audits.append(True)
        pythonless.append(docker('exec', main['Id'], 'sh', '-c',
            'if command -v python3 >/dev/null 2>&1; then echo present; else echo absent; fi') == 'absent')
    def compose(**kwargs):
        kwargs['tokenizer_dir'] = root / '.cache/stage2-tokenizer'
        result = compose_runtime(**kwargs)
        gateway = result['services']['model-gateway']
        gateway['entrypoint'] = ['python', '/study/stage2/no_cutoff_custom_probe.py']
        gateway['command'] = ['--gateway', '--trial', cell['trial_id'],
            '--completion-wait-seconds', str(kwargs['completion_wait_seconds'])]
        gateway.pop('networks')
        gateway['network_mode'] = 'none'
        return result
    prepared = asyncio.Event()
    created = []
    native_factory = agent_factory(fixture, parent)
    def create(**kwargs):
        agent = native_factory(**kwargs)
        created.append(agent)
        if mode == 'cancel_setup':
            original = agent.setup
            async def setup(environment):
                await original(environment)
                prepared.set()
                await asyncio.Event().wait()
            agent.setup = setup
        elif mode == 'boundary_stop':
            original_run = agent.run
            async def run(*args, **kw):
                # Signal during the active attempt; its verifier must finish.
                os.kill(os.getpid(), signal.SIGUSR1)
                return await original_run(*args, **kw)
            agent.run = run
        return agent
    create.__dict__.update(native_factory.__dict__)
    cancelled, no_next = False, False
    # All bypasses are local to a fake-key, networkless provider fixture.
    # There is no command-line flag bypassing real paid admission.
    with patch('scored_trial.frozen_dataset', return_value=root / 'stage2/fixtures'), \
         patch('harbor.models.task.task.Task', return_value=task), \
         patch('scored_trial.compose_runtime', side_effect=compose), \
         patch('scored_trial.audit_task', side_effect=audit), \
         patch('no_cutoff_custom_study.admit_trial', return_value=fingerprint(fixture_record)), \
         patch('no_cutoff_custom_study.require_task_image', side_effect=lambda r,t,i:
             None if i == task.config.environment.docker_image else (_ for _ in ()).throw(ValueError('Fixture image changed'))), \
         BoundaryStop(state) as stop:
        execution = asyncio.create_task(run_trial(root=fixture, trial_id=cell['trial_id'],
            task_id=cell['task_id'], stage='development', agent_factory=create, model_settings=SETTINGS,
            gateway_image=gateway_image, guard_image=guard_image, setup_timeout_seconds=900,
            accounting_mode='provider-credit-only', custom_study=EXPERIMENT))
        if mode == 'cancel_setup':
            try:
                await asyncio.wait_for(prepared.wait(), 240)
            except BaseException:
                execution.cancel()
                await asyncio.gather(execution, return_exceptions=True)
                raise
            execution.cancel()
            try:
                await execution
            except asyncio.CancelledError:
                cancelled = True
            result = json.loads((state / 'scored-trials' / cell['trial_id'] / 'result.json').read_text())
        else:
            result = await execution
        if mode == 'boundary_stop':
            # Dispatch the actual remaining block. Any attempted audit/launch
            # here is a bug: the persisted boundary stop must win first.
            with patch('run_no_cutoff_custom.audited', side_effect=AssertionError('No next audit')), \
                 patch('run_no_cutoff_custom.run_trial', side_effect=AssertionError('No next launch')) as next_run:
                await dispatch(fixture, block, stop=stop)
                no_next = not next_run.called
    billing = result.get('billing', {})
    attempts = state / 'scored-attempts' / cell['trial_id']
    logical = [json.loads(p.read_text()) for p in attempts.glob('logical-*.json')]
    is_cancel = mode == 'cancel_setup'
    expected_requests = 0 if is_cancel else EXPECTED_LOGICAL + 1
    reward = (result.get('verifier_result') or {}).get('rewards', {}).get('reward')
    checks = dict(model_revoked=result.get('model_revoked') is True,
        expected_status=result['status'] == ('interrupted' if is_cancel else 'verified'),
        expected_verifier_result=reward is None if is_cancel else reward == 1,
        actual_pythonless_image=pythonless == [True],
        runtime_archive_bound=bool(created) and created[0].runtime_proof is not None
            and created[0].runtime_proof.get('sha256') == PYTHON_SHA256,
        all_physical_requests_accounted=billing.get('requests') == expected_requests,
        unknown_costs_retained=billing.get('unknown_cost_requests') == expected_requests
            and (billing.get('charged_usd') == '0' if is_cancel else billing.get('charged_usd') is None),
        no_receipt_or_credit_block=billing.get('provider_stop') is None,
        traces_recorded=result.get('trace', {}).get('generations') == expected_requests,
        containers_removed=result.get('containers_removed') is True,
        networks_removed=result.get('networks_removed') is True, volumes_removed=result.get('volumes_removed') is True,
        sources_unchanged=sources(root, document) == before, host_unchanged=host_environment.snapshot() == host,
        fixture_resources_audited=audits == [True],
        images_unchanged=all(docker('image', 'inspect', image, '--format', '{{.Id}}') == image for image in (gateway_image, guard_image)))
    if is_cancel:
        checks['cancelled_setup_evidence'] = cancelled and 'setup' in result.get('phase_seconds', {}) and not logical
    else:
        accepted = len(logical) == EXPECTED_LOGICAL and all(v['accepted_for_agent'] for v in logical)
        checks.update(actual_custom_tool_roundtrip=accepted,
            recovered_one_transient=len(list(attempts.glob('*.retry.json'))) == 1,
            # The synthetic provider fails the next request unless these real
            # tool outputs satisfy its assertions. The verifier is independent.
            media_tool_text_only=accepted, long_read_and_tail=accepted and reward == 1,
            timeout_exit_124=accepted and reward == 1, background_service_alive=reward == 1,
            no_dynamic_time_advice=accepted,
            encoded_capture_process_matching=accepted, sizeable_command_capture=accepted,
            more_than_two_repairs=accepted and created[0].runner.control.repairs_used==7,
            no_command_count_quota=accepted and len(created[0].runner.jobs.jobs)==74,
            command_passed_sixty_seconds=accepted and result['phase_seconds']['agent']>=61)
    if mode == 'boundary_stop':
        checks.update(cooperative_stop_persisted=BoundaryStop(state).requested(),
            no_next_dispatch=no_next and len(list((state / 'scored-trials').iterdir())) == 1)
    assert set(checks) == probe_checks(mode)
    evidence = dict(status='passed' if all(checks.values()) else 'failed', condition=condition, parent=parent, base_parent=base_parent,
        mode=mode, kind='actual_harbor_no_cutoff_graph_synthetic_provider_not_benchmark_score', live_api_calls=0,
        checks=checks, host_environment=host, model_protocol_sha256=SETTINGS.fingerprint(),
        runtime_path=str(fixture.relative_to(root)))
    durable_json(fixture / 'evidence.json', evidence)
    return evidence


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', action='store_true')
    parser.add_argument('--trial', required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    if not args.gateway:
        raise SystemExit('Host qualifier owns execution')
    gateway_fixture(args.trial, args.completion_wait_seconds)

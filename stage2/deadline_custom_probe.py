"""Actual Harbor lifecycle and C3 graph, using a networkless fake model.

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
import tempfile
import tomllib
from unittest.mock import patch

from gateway_policy import MODEL, ENDPOINT
from openrouter_transport import TransportError, error_diagnostic
from deadline_custom_policy import SETTINGS
from portable_custom_probe import SyntheticProvider as PreviousProvider

PNG = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jWZkAAAAASUVORK5CYII='
PREPARE = ("printf '%s' " + PNG + " | base64 -d > /tmp/uts-fixture.png; "
    "python3 -c \"from pathlib import Path; Path('/tmp/uts-long.txt').write_text(''.join('row-%05d\\n'%i for i in range(16000)))\"; "
    "sleep 110 & echo $! > /tmp/uts-background.pid; printf BACKGROUND_READY")
EXPECTED_LOGICAL = 22


class SyntheticProvider(PreviousProvider):
    """Script actual tools; no external provider/network capability."""
    def complete(self, request, *, on_response_headers):
        assert any('[Task time remaining]' in (m.get('content') or '')
            for m in request['messages'])
        if self.calls < 10:
            return super().complete(request, on_response_headers=on_response_headers)
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
            commands=[('complete_task',{'summary':''})]
        elif 15 <= step <= 20:
            assert json.loads(last)['status']=='repair_requested'
            assert json.loads(last)['terminal'] is False
            commands=[('complete_task',{'summary':''})]
        elif step==21:
            assert json.loads(last)['repair_number']==7
            commands=[('complete_task',dict(summary='Synthetic C3 lifecycle complete.',
                checks=[dict(criterion='Fixture observations',observation='Long command, 73 jobs and seven repairs observed',satisfied=True)]))]
        else:
            raise ValueError('Unexpected extra synthetic request')
        allowed={t['function']['name'] for t in request['tools']}
        assert all(name in allowed for name,_ in commands)
        message=dict(role='assistant',content=None,tool_calls=[
            dict(id=f'call_{self.calls}_{index}',type='function',
                 function=dict(name=name,arguments=json.dumps(args)))
            for index,(name,args) in enumerate(commands)])
        return dict(id='gen-synthetic-deadline-'+str(self.calls),model=MODEL,provider='DeepInfra',
            object='chat.completion',created=1,choices=[dict(index=0,finish_reason='tool_calls',message=message)],
            usage=dict(prompt_tokens=10,completion_tokens=4,total_tokens=14))


def gateway_fixture(trial, wait):
    from deadline_custom_gateway import DeadlineRetrySession
    from retry_gateway import serve
    serve('/study', trial, 'development', '/run/trial-token', '/run/openrouter.env',
        '/socket/private/model.sock', completion_wait_seconds=wait,
        client_factory=SyntheticProvider, session_factory=DeadlineRetrySession)


async def probe(root, gateway_image, guard_image, parent, base_parent, mode):
    condition='C3'
    import host_environment
    from deadline_custom_agent import agent_factory, runtime_bundle
    from deadline_custom_policy import (EXPERIMENT, POLICY, POLICY_FILE, QUALIFICATION,
        fingerprint, cells, block_path, INPUT_SHA256, CANDIDATE_VERSION, PYTHON_SHA256,
        PARENT_FILE, execution_contract)
    from deadline_custom_study import sources, probe_checks
    from production_compose import compose_runtime
    from scored_gateway import durable_json, private_directory
    from scored_trial import run_trial, docker, audit_task
    from qualify_oracle import frozen_dataset
    from harbor.models.task.task import Task
    from custom_dispatch_stop import BoundaryStop
    from run_deadline_custom import dispatch
    probe_checks(mode)
    root = Path(root)
    os.umask(0o077)
    before, host = sources(root), host_environment.snapshot()
    runtime = private_directory(root / '.runtime/stage2')
    fixture = Path(tempfile.mkdtemp(prefix='native-deadline-' + condition + '-' + mode + '-', dir=runtime))
    (fixture / 'stage2').mkdir(mode=0o700)
    manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
    durable_json(fixture / 'stage2/input_manifest.json', manifest)
    state = private_directory(fixture / '.runtime/stage2')
    # A private copy, not a writable link back into the qualified deployment.
    shutil.copyfile(runtime_bundle(root).path, runtime_bundle(fixture).path)
    bundle_proof = runtime_bundle(fixture).validate()
    durable_json(state / POLICY_FILE, POLICY)
    proof = dict(experiment=EXPERIMENT, status='passed', sources_sha256=fingerprint(before),
        candidate_version=CANDIDATE_VERSION, python_runtime=bundle_proof,
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        kind='synthetic-probe-only-not-paid-admission')
    parent_evidence=json.loads((runtime/PARENT_FILE).read_text())
    durable_json(state/PARENT_FILE,parent_evidence)
    proof.update(parent_evidence_sha256=fingerprint(parent_evidence),execution_contract=execution_contract())
    # The fixture proof is private and unreachable from the paid entry point.
    durable_json(state / QUALIFICATION, proof)
    scheduled = cells(manifest['development_ids'])
    cell = scheduled[0]
    block = dict(experiment=EXPERIMENT, stage='development', condition=condition, parent=parent, base_parent=base_parent,
        parent_evidence_sha256=fingerprint(parent_evidence),execution_contract=execution_contract(),
        candidate_version=CANDIDATE_VERSION, python_runtime_sha256=PYTHON_SHA256,
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, development_ids=manifest['development_ids'],
        primary_comparator='terminus-2', secondary_comparator='openhands', cells=scheduled,
        sources_sha256=fingerprint(before), qualification_sha256=fingerprint(proof))
    path = block_path(state)
    private_directory(path.parent)
    durable_json(path, block)
    (fixture / '.env').write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
    task = Task(root / 'stage2/fixtures/portable-lifecycle')
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
        gateway['entrypoint'] = ['python', '/study/stage2/deadline_custom_probe.py']
        gateway['command'] = ['--gateway', '--trial', cell['trial_id'],
            '--completion-wait-seconds', str(kwargs['completion_wait_seconds'])]
        gateway.pop('networks')
        gateway['network_mode'] = 'none'
        return result
    prepared = asyncio.Event()
    created = []
    native_factory = agent_factory(fixture, parent, base_parent=base_parent)
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
         patch('deadline_custom_study.admit_trial', return_value=fingerprint(block)), BoundaryStop(state) as stop:
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
            with patch('run_deadline_custom.audited', side_effect=AssertionError('No next audit')), \
                 patch('run_deadline_custom.run_trial', side_effect=AssertionError('No next launch')) as next_run:
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
        sources_unchanged=sources(root) == before, host_unchanged=host_environment.snapshot() == host,
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
            deadline_context_observed=accepted,
            more_than_two_repairs=accepted and created[0].runner.control.repairs_used==7,
            no_command_count_quota=accepted and len(created[0].runner.jobs.jobs)==74,
            command_passed_sixty_seconds=accepted and result['phase_seconds']['agent']>=61)
    if mode == 'boundary_stop':
        checks.update(cooperative_stop_persisted=BoundaryStop(state).requested(),
            no_next_dispatch=no_next and len(list((state / 'scored-trials').iterdir())) == 1)
    assert set(checks) == probe_checks(mode)
    evidence = dict(status='passed' if all(checks.values()) else 'failed', condition=condition, parent=parent, base_parent=base_parent,
        mode=mode, kind='actual_harbor_deadline_graph_synthetic_provider_not_benchmark_score', live_api_calls=0,
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

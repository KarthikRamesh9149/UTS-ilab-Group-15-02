"""Native harnesses, synthetic tools and a real 429, without an API credential."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch


def gateway_fixture(harness, wait):
    from retry_gateway import serve
    from retry_policy import SETTINGS
    from gateway_policy import MODEL, ENDPOINT
    from openrouter_transport import TransportError, error_diagnostic
    class SyntheticProvider:
        def __init__(self, key, *, clock, **kwargs):
            if key != 'synthetic-not-a-real-key': raise ValueError('Synthetic key required')
            self.clock, self.calls = clock, 0
        def complete(self, request, *, on_response_headers):
            assert request['max_tokens'] == SETTINGS.max_output_tokens
            assert request['provider']['only'] == [ENDPOINT]
            assert 'max_price' not in request['provider']
            assert request['temperature'] == 1.
            assert request['reasoning'] == {'effort': 'high'}
            self.calls += 1
            if self.calls == 1:
                diagnostic = error_diagnostic(status=429)
                self.last_failure = dict(http_status=429, retry_after_values=['1'], diagnostic=diagnostic,
                    observed_at_utc=datetime.fromtimestamp(self.clock.wall(), timezone.utc),
                    now_monotonic=self.clock.monotonic())
                on_response_headers(diagnostic)
                raise TransportError('synthetic-rate-limit', diagnostic=diagnostic)
            self.last_failure = None
            on_response_headers(error_diagnostic(status=200))
            command = 'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result'
            if harness == 'terminus-2':
                answer = dict(analysis='Synthetic fixture.', plan='Write marker then finish.',
                    commands=[dict(keystrokes=command + '\n', duration=.1)] if self.calls == 2 else [],
                    task_complete=self.calls > 2)
                message = dict(role='assistant', content=json.dumps(answer))
                finish = 'stop'
            else:
                name = 'execute_bash' if self.calls == 2 else 'finish'
                assert name in {t['function']['name'] for t in request['tools']}
                args = {'command': command} if self.calls == 2 else {'message': 'Fixture complete.'}
                message = dict(role='assistant', content=None, tool_calls=[dict(
                    id='call_' + str(self.calls), type='function',
                    function=dict(name=name, arguments=json.dumps(args)))])
                finish = 'tool_calls'
            return dict(id='gen-synthetic-recovery-' + str(self.calls), model=MODEL, provider='DeepInfra',
                object='chat.completion', created=1,
                choices=[dict(index=0, finish_reason=finish, message=message)],
                usage=dict(prompt_tokens=10, completion_tokens=4, total_tokens=14))
    serve('/study', 'synthetic-' + harness, 'final', '/run/trial-token', '/run/openrouter.env',
        '/socket/private/model.sock', completion_wait_seconds=wait, client_factory=SyntheticProvider)


async def probe(root, gateway_image, guard_image, harness):
    from credit_only_policy import MODE, POLICY as FINANCIAL, POLICY_FILE as FINANCIAL_FILE
    from retry_policy import SETTINGS, POLICY, POLICY_FILE
    from retry_experiment import sources
    from recovery_agents import agent_factory
    from production_compose import compose_runtime
    from scored_gateway import durable_json, private_directory
    from scored_trial import run_trial, docker
    from qualify_oracle import frozen_dataset
    from harbor.models.task.task import Task
    import host_environment
    root = Path(root)
    os.umask(0o077)
    before, host = sources(root), host_environment.snapshot()
    runtime = private_directory(root / '.runtime/stage2')
    fixture = Path(tempfile.mkdtemp(prefix='native-recovery-' + harness + '-', dir=runtime))
    (fixture / 'stage2').mkdir(mode=0o700)
    durable_json(fixture / 'stage2/input_manifest.json', {'all_task_ids': ['lifecycle'], 'development_ids': ['lifecycle']})
    # This fixture never receives the real credential, even though task setup
    # can install public packages. The fake provider has no network interface.
    (fixture / '.env').write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
    state = private_directory(fixture / '.runtime/stage2')
    durable_json(state / FINANCIAL_FILE, FINANCIAL)
    durable_json(state / POLICY_FILE, POLICY)
    # Reproduce the resource/image configuration of the first failed OpenHands
    # startup without reading its instruction, tests, solution or reward.
    base = Task(frozen_dataset(root) / 'adaptive-rejection-sampler')
    task = Task(root / 'stage2/fixtures/lifecycle')
    task.config.environment.docker_image = base.config.environment.docker_image
    task.config.environment.cpus = base.config.environment.cpus
    task.config.environment.memory_mb = base.config.environment.memory_mb
    task.config.agent.timeout_sec = base.config.agent.timeout_sec
    def compose(**kwargs):
        kwargs['tokenizer_dir'] = root / '.cache/stage2-tokenizer'
        result = compose_runtime(**kwargs)
        gateway = result['services']['model-gateway']
        gateway['entrypoint'] = ['python', '/study/stage2/retry_runtime_probe.py']
        gateway['command'] = ['--gateway', '--harness', harness, '--completion-wait-seconds', str(kwargs['completion_wait_seconds'])]
        gateway.pop('networks')
        gateway['network_mode'] = 'none'
        return result
    factory = agent_factory(harness, fixture)
    original = factory
    def diagnostic_factory(**kwargs):
        agent = original(**kwargs)
        if harness == 'openhands':
            execute = agent.exec_as_agent
            async def debug(environment, command, env=None, **options):
                if env is not None and 'LLM_MODEL' in env:
                    env = dict(env, DEBUG='true', DEBUG_LLM='false')
                return await execute(environment, command=command, env=env, **options)
            agent.exec_as_agent = debug
        return agent
    diagnostic_factory.harness = harness
    diagnostic_factory.model_protocol_sha256 = SETTINGS.fingerprint()
    with patch('scored_trial.frozen_dataset', return_value=root / 'stage2/fixtures'), \
         patch('harbor.models.task.task.Task', return_value=task), \
         patch('scored_trial.compose_runtime', side_effect=compose):
        result = await run_trial(root=fixture, trial_id='synthetic-' + harness, task_id='lifecycle', stage='final',
            agent_factory=diagnostic_factory, model_settings=SETTINGS,
            gateway_image=gateway_image, guard_image=guard_image,
            setup_timeout_seconds=900, accounting_mode=MODE)
    billing = result.get('billing', {})
    attempts = state / 'scored-attempts' / ('synthetic-' + harness)
    retries = list(attempts.glob('*.retry.json'))
    logical = [json.loads(p.read_text()) for p in attempts.glob('logical-*.json')]
    checks = dict(verifier_reward_one=(result.get('verifier_result') or {}).get('rewards', {}).get('reward') == 1,
        model_revoked=result.get('model_revoked') is True, clean_status=result['status'] == 'verified',
        actual_native_tool_calls=len(logical) >= 2 and all(v['accepted_for_agent'] for v in logical),
        recovered_one_transient=len(retries) == 1,
        all_physical_requests_accounted=billing.get('requests') == len(logical) + 1,
        unknown_costs_retained=billing.get('unknown_cost_requests') == len(logical) + 1 and billing.get('charged_usd') is None,
        no_receipt_or_credit_block=billing.get('provider_stop') is None,
        traces_recorded=result.get('trace', {}).get('generations') == len(logical) + 1,
        containers_removed=result.get('containers_removed') is True,
        networks_removed=result.get('networks_removed') is True, volumes_removed=result.get('volumes_removed') is True,
        sources_unchanged=sources(root) == before, host_unchanged=host_environment.snapshot() == host,
        images_unchanged=all(docker('image', 'inspect', image, '--format', '{{.Id}}') == image for image in (gateway_image, guard_image)))
    return dict(status='passed' if all(checks.values()) else 'failed', harness=harness,
        kind='actual_native_harness_synthetic_provider_not_benchmark_score', live_api_calls=0,
        checks=checks, host_environment=host, model_protocol_sha256=SETTINGS.fingerprint(),
        runtime_path=str(fixture.relative_to(root)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', action='store_true')
    parser.add_argument('--harness', choices=['terminus-2', 'openhands'], required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    if not args.gateway: raise SystemExit('Host qualifier owns execution')
    gateway_fixture(args.harness, args.completion_wait_seconds)

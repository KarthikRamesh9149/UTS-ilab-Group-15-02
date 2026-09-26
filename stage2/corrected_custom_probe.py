"""Real custom graph + Docker task/verifier; isolated synthetic model, no API."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import tomllib
from unittest.mock import patch


def gateway_fixture(condition, trial, wait):
    from corrected_custom_gateway import CustomRetrySession
    from retry_gateway import serve
    from retry_policy import SETTINGS
    from gateway_policy import MODEL, ENDPOINT
    from openrouter_transport import TransportError, error_diagnostic
    class SyntheticProvider:
        def __init__(self, key, *, clock, **kwargs):
            if key != 'synthetic-not-a-real-key':
                raise ValueError('Synthetic key required')
            self.clock, self.calls = clock, 0
        def complete(self, request, *, on_response_headers):
            assert request['max_tokens'] == SETTINGS.max_output_tokens
            assert request['provider']['only'] == [ENDPOINT]
            assert request['provider']['allow_fallbacks'] is False
            assert 'max_price' not in request['provider']
            assert request['temperature'] == request['top_p'] == 1.
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
            if self.calls == 2:
                name, args = 'execute', {'command': 'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result; cat /tmp/uts-lifecycle-result'}
            else:
                name, args = 'complete_task', dict(summary='Created the fixture marker and read it back.',
                    checks=[dict(criterion='Fixture marker matches', observation='Read UTS_LIFECYCLE_OK', satisfied=True)])
            assert name in {t['function']['name'] for t in request['tools']}
            message = dict(role='assistant', content=None, tool_calls=[dict(id='call_' + str(self.calls),
                type='function', function=dict(name=name, arguments=json.dumps(args)))])
            return dict(id='gen-synthetic-custom-' + str(self.calls), model=MODEL, provider='DeepInfra',
                object='chat.completion', created=1,
                choices=[dict(index=0, finish_reason='tool_calls', message=message)],
                usage=dict(prompt_tokens=10, completion_tokens=4, total_tokens=14))
    serve('/study', trial, 'development', '/run/trial-token', '/run/openrouter.env',
        '/socket/private/model.sock', completion_wait_seconds=wait,
        client_factory=SyntheticProvider, session_factory=CustomRetrySession)


async def probe(root, gateway_image, guard_image, condition, parent):
    import host_environment
    from corrected_custom_agent import agent_factory
    from corrected_custom_policy import (EXPERIMENT, POLICY, POLICY_FILE, QUALIFICATION,
        fingerprint, cells, block_path, SETTINGS, INPUT_SHA256)
    from corrected_custom_study import sources
    from production_compose import compose_runtime
    from scored_gateway import durable_json, private_directory
    from scored_trial import run_trial, docker, audit_task
    from qualify_oracle import frozen_dataset
    from harbor.models.task.task import Task
    root = Path(root)
    os.umask(0o077)
    before, host = sources(root), host_environment.snapshot()
    runtime = private_directory(root / '.runtime/stage2')
    fixture = Path(tempfile.mkdtemp(prefix='native-custom-' + condition + '-', dir=runtime))
    (fixture / 'stage2').mkdir(mode=0o700)
    manifest = json.loads((root / 'stage2/input_manifest.json').read_text())
    durable_json(fixture / 'stage2/input_manifest.json', manifest)
    state = private_directory(fixture / '.runtime/stage2')
    durable_json(state / POLICY_FILE, POLICY)
    proof = dict(experiment=EXPERIMENT, status='passed', sources_sha256=fingerprint(before),
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        kind='synthetic-probe-only-not-paid-admission')
    durable_json(state / QUALIFICATION, proof)
    scheduled = cells(manifest['development_ids'], condition, parent)
    cell = scheduled[0]
    block = dict(experiment=EXPERIMENT, stage='development', condition=condition, parent=parent,
        policy_sha256=fingerprint(POLICY), model_protocol_sha256=SETTINGS.fingerprint(),
        input_manifest_sha256=INPUT_SHA256, development_ids=manifest['development_ids'],
        primary_comparator='terminus-2', secondary_comparator='openhands',
        cells=scheduled, sources_sha256=fingerprint(before), qualification_sha256=fingerprint(proof))
    path = block_path(state, condition)
    private_directory(path.parent)
    durable_json(path, block)
    (fixture / '.env').write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
    # Metadata IDs only. The real task is this repository's synthetic fixture,
    # never the corresponding benchmark instruction, test or solution.
    task = Task(root / 'stage2/fixtures/lifecycle')
    environment_metadata = tomllib.loads((frozen_dataset(root) /
        manifest['development_ids'][0] / 'task.toml').read_text())['environment']
    # Reuse a dev-set image, not FROM scratch or a held-out task answer.
    image_name = environment_metadata['docker_image']
    task.config.environment.docker_image = docker('image', 'inspect', image_name, '--format', '{{.Id}}')
    task.config.environment.cpus = 1
    task.config.environment.memory_mb = 2048
    audits = []
    def audit(*args):
        audit_task(*args)
        audits.append(True)
    def compose(**kwargs):
        kwargs['tokenizer_dir'] = root / '.cache/stage2-tokenizer'
        result = compose_runtime(**kwargs)
        gateway = result['services']['model-gateway']
        gateway['entrypoint'] = ['python', '/study/stage2/corrected_custom_probe.py']
        gateway['command'] = ['--gateway', '--condition', condition, '--trial', cell['trial_id'],
            '--completion-wait-seconds', str(kwargs['completion_wait_seconds'])]
        gateway.pop('networks')
        gateway['network_mode'] = 'none'
        return result
    # Qualification intentionally runs before paid admission exists. The
    # bypass is local to this fake-key/network-none fixture and never exposed
    # as a paid-run option. Full admission is separately regression-tested.
    with patch('scored_trial.frozen_dataset', return_value=root / 'stage2/fixtures'), \
         patch('harbor.models.task.task.Task', return_value=task), \
         patch('scored_trial.compose_runtime', side_effect=compose), \
         patch('scored_trial.audit_task', side_effect=audit), \
         patch('corrected_custom_study.admit_trial', return_value=fingerprint(block)):
        result = await run_trial(root=fixture, trial_id=cell['trial_id'], task_id=cell['task_id'], stage='development',
            agent_factory=agent_factory(fixture, condition, parent=parent), model_settings=SETTINGS,
            gateway_image=gateway_image, guard_image=guard_image, setup_timeout_seconds=900,
            accounting_mode='provider-credit-only', custom_study=EXPERIMENT)
    billing = result.get('billing', {})
    attempts = state / 'scored-attempts' / cell['trial_id']
    logical = [json.loads(p.read_text()) for p in attempts.glob('logical-*.json')]
    checks = dict(verifier_reward_one=(result.get('verifier_result') or {}).get('rewards', {}).get('reward') == 1,
        model_revoked=result.get('model_revoked') is True, clean_status=result['status'] == 'verified',
        actual_custom_tool_roundtrip=len(logical) == 2 and all(v['accepted_for_agent'] for v in logical),
        recovered_one_transient=len(list(attempts.glob('*.retry.json'))) == 1,
        all_physical_requests_accounted=billing.get('requests') == 3,
        unknown_costs_retained=billing.get('unknown_cost_requests') == 3 and billing.get('charged_usd') is None,
        no_receipt_or_credit_block=billing.get('provider_stop') is None,
        traces_recorded=result.get('trace', {}).get('generations') == 3,
        containers_removed=result.get('containers_removed') is True,
        networks_removed=result.get('networks_removed') is True, volumes_removed=result.get('volumes_removed') is True,
        sources_unchanged=sources(root) == before, host_unchanged=host_environment.snapshot() == host,
        official_resources_audited=audits == [True],
        images_unchanged=all(docker('image', 'inspect', image, '--format', '{{.Id}}') == image for image in (gateway_image, guard_image)))
    return dict(status='passed' if all(checks.values()) else 'failed', condition=condition, parent=parent,
        kind='actual_custom_graph_native_docker_synthetic_provider_not_benchmark_score', live_api_calls=0,
        checks=checks, host_environment=host, model_protocol_sha256=SETTINGS.fingerprint(),
        runtime_path=str(fixture.relative_to(root)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', action='store_true')
    parser.add_argument('--condition', choices=['C0', 'C1', 'C2'], required=True)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    if not args.gateway:
        raise SystemExit('Host qualifier owns execution')
    gateway_fixture(args.condition, args.trial, args.completion_wait_seconds)

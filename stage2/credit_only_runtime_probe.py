"""Full Harbor/Docker lifecycle with a fake provider and no real API credential."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import tempfile
import urllib.request
from unittest.mock import patch


def gateway_fixture(completion_wait_seconds):
    from credit_only_gateway import serve
    from gateway_policy import MODEL, ENDPOINT
    from openrouter_transport import error_diagnostic
    class SyntheticProvider:
        calls = 0
        def complete(self, request, *, on_response_headers=None):
            if (request['provider'] != dict(only=[ENDPOINT], order=[ENDPOINT], allow_fallbacks=False,
                    require_parameters=True, quantizations=['fp8'])
                    or request['max_tokens'] != 8192 or request['temperature'] != 1.
                    or request['reasoning'] != {'effort': 'high'}):
                raise ValueError('Frozen nonfinancial protocol changed')
            self.calls += 1
            on_response_headers(error_diagnostic(status=200))
            return dict(id='gen-synthetic-passive-' + str(self.calls), model=MODEL, provider='DeepInfra',
                object='chat.completion', created=1,
                choices=[dict(index=0, finish_reason='stop', message=dict(role='assistant', content='UTS_RUNTIME_OK'))],
                usage=dict(prompt_tokens=10, completion_tokens=4, total_tokens=14))
        def balance(self): raise AssertionError('No balance admission allowed')
        def key_status(self): raise AssertionError('No key allowance admission allowed')
        def metadata(self): raise AssertionError('No pricing admission allowed')
        def generation(self, identifier): raise AssertionError('No receipt admission allowed')
    with patch('credit_only_gateway.OpenRouter', return_value=SyntheticProvider()):
        try:
            serve('/study', 'synthetic-credit-only', 'final', '/run/trial-token', '/run/openrouter.env',
                '/socket/private/model.sock', completion_wait_seconds=completion_wait_seconds)
        except KeyboardInterrupt:
            pass


async def probe(root, gateway_image, guard_image):
    from credit_only_policy import MODE, POLICY, POLICY_FILE
    from credit_only_experiment import sources
    from gateway_policy import MODEL
    from model_protocol import ModelSettings
    from production_compose import compose_runtime
    from scored_gateway import durable_json, private_directory
    from scored_trial import run_trial, docker
    from harbor.models.task.task import Task
    import host_environment
    root = Path(root)
    os.umask(0o077)
    before = sources(root)
    host = host_environment.snapshot()
    runtime = private_directory(root / '.runtime/stage2')
    fixture = Path(tempfile.mkdtemp(prefix='credit-only-synthetic-', dir=runtime))
    (fixture / 'stage2').mkdir(mode=0o700)
    durable_json(fixture / 'stage2/input_manifest.json', {'all_task_ids': ['lifecycle'], 'development_ids': ['lifecycle']})
    (fixture / '.env').write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
    state = private_directory(fixture / '.runtime/stage2')
    durable_json(state / POLICY_FILE, POLICY)
    task = Task(root / 'stage2/fixtures/lifecycle')
    task.config.environment.docker_image = docker('image', 'inspect', 'uts-stage2-egress-fixture:1', '--format', '{{.Id}}')
    observed = {'fake_provider_roundtrips': 0}
    settings = ModelSettings(8192, 1., 'high')
    def compose(**kwargs):
        kwargs['tokenizer_dir'] = root / '.cache/stage2-tokenizer'
        result = compose_runtime(**kwargs)
        gateway = result['services']['model-gateway']
        gateway['entrypoint'] = ['python', '/study/stage2/credit_only_runtime_probe.py']
        gateway['command'] = ['--gateway', '--completion-wait-seconds', str(kwargs['completion_wait_seconds'])]
        gateway.pop('networks')
        gateway['network_mode'] = 'none'  # Even the fake gateway cannot reach OpenRouter.
        return result
    def factory(**kwargs):
        class MarkerAgent:
            async def setup(self, environment): pass
            async def run(self, instruction, environment, context):
                payload = dict(model=MODEL, max_tokens=8192, temperature=1., reasoning={'effort': 'high'},
                    messages=[dict(role='user', content=instruction)])
                def request():
                    req = urllib.request.Request(kwargs['host_api_base'] + '/chat/completions',
                        data=json.dumps(payload).encode(), headers={'Authorization': 'Bearer ' + kwargs['trial_token']})
                    with urllib.request.urlopen(req, timeout=kwargs['completion_wait_seconds']) as response:
                        return json.load(response)
                for _ in range(3):
                    response = await asyncio.to_thread(request)
                    if response['choices'][0]['message']['content'] != 'UTS_RUNTIME_OK':
                        raise ValueError('Fixture response mismatch')
                    observed['fake_provider_roundtrips'] += 1
                result = await environment.exec('printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result', timeout_sec=10)
                if result.return_code != 0:
                    raise RuntimeError('Fixture marker write failed')
        return MarkerAgent()
    factory.harness = 'terminus-2'  # Trace identity only; this is not a native baseline score.
    with patch('scored_trial.frozen_dataset', return_value=root / 'stage2/fixtures'), \
         patch('harbor.models.task.task.Task', return_value=task), \
         patch('scored_trial.compose_runtime', side_effect=compose):
        result = await run_trial(root=fixture, trial_id='synthetic-credit-only', task_id='lifecycle', stage='final',
            agent_factory=factory, model_settings=settings, gateway_image=gateway_image, guard_image=guard_image,
            setup_timeout_seconds=30, accounting_mode=MODE)
    billing = result.get('billing', {})
    checks = dict(verifier_reward_one=(result.get('verifier_result') or {}).get('rewards', {}).get('reward') == 1,
        model_revoked=result.get('model_revoked') is True, clean_status=result['status'] == 'verified',
        three_usable_responses_without_costs=observed['fake_provider_roundtrips'] == 3,
        unknown_costs_retained=billing.get('unknown_cost_requests') == 3 and billing.get('charged_usd') is None,
        no_receipt_or_credit_block=billing.get('provider_stop') is None,
        traces_recorded=result.get('trace', {}).get('generations') == 3,
        containers_removed=result.get('containers_removed') is True,
        networks_removed=result.get('networks_removed') is True, volumes_removed=result.get('volumes_removed') is True,
        sources_unchanged=sources(root) == before, host_unchanged=host_environment.snapshot() == host,
        images_unchanged=all(docker('image', 'inspect', image, '--format', '{{.Id}}') == image for image in (gateway_image, guard_image)))
    proof = dict(status='passed' if all(checks.values()) else 'failed',
        kind='synthetic_full_runner_not_benchmark_score', live_api_calls=0, checks=checks,
        sources=before, host_environment=host, gateway_image=gateway_image, guard_image=guard_image,
        model_protocol_sha256=settings.fingerprint(), runtime_path=str(fixture.relative_to(root)))
    durable_json(runtime / 'credit-only-synthetic.json', proof)
    return proof


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gateway', action='store_true')
    parser.add_argument('--completion-wait-seconds', type=float, required=True)
    args = parser.parse_args()
    if not args.gateway:
        raise SystemExit('Host qualification owns the probe and shared execution locks')
    gateway_fixture(args.completion_wait_seconds)

"""Real full runner + Docker + HTTP + Harbor verifier; synthetic provider only.

Uses a separate fake credential and fake billing database. This is a tiny
infrastructure fixture, never added to the frozen Terminal-Bench dataset.
Refuses to overlap the real oracle/scored host lock.
"""
import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import tempfile
import subprocess
import urllib.request
from unittest.mock import patch

from production_compose import compose_runtime
from scored_gateway import durable_json, private_directory
from scored_trial import run_trial, docker
from gateway_policy import MODEL
from model_protocol import ModelSettings
from scoring_admission import source_hashes

LOADED_SOURCE_HASHES = source_hashes(Path(__file__).resolve().parents[1])


async def probe(label, *, wait=False, rebuild_gateway=False, harness='marker', full_install=False):
    if not label.isalnum():
        raise ValueError('Alphanumeric unique evidence label required')
    if harness not in {'marker', 'openhands'}:
        raise ValueError('Unknown infrastructure probe harness')
    if full_install and harness != 'openhands':
        raise ValueError('Full installation qualification is OpenHands-only')
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    runtime = private_directory(root / '.runtime/stage2')
    output = root / 'stage2' / ('scored_runtime_probe_' + label + '.json')
    if output.exists():
        raise ValueError('Preserve previous probe evidence')
    with (runtime / 'scored.lock').open('a+') as owner:
        announced = False
        while True:
            try:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not wait:
                    raise
                if not announced:
                    print('Waiting for the existing task owner; no containers or model calls started.', flush=True)
                    announced = True
                await asyncio.sleep(5)
        # Recheck after acquiring: another queued invocation may have finished.
        if output.exists():
            raise ValueError('Preserve previous probe evidence')
        from qualify_oracle import check_host
        check_host()
        if source_hashes(root) != LOADED_SOURCE_HASHES:
            raise ValueError('Runtime sources changed while probe waited; restart the unstarted probe')
        if rebuild_gateway:
            print('Task owner released; rebuilding the gateway for the synthetic runtime check.', flush=True)
            await asyncio.to_thread(subprocess.run, ['docker', 'build', '--quiet',
                '-f', str(root / 'stage2/fixtures/Dockerfile.gateway'),
                '-t', 'uts-stage2-gateway:1', str(root / 'stage2')],
                check=True, timeout=600)
        fixture_root = Path(tempfile.mkdtemp(prefix='scored-runtime-', dir=runtime))
        (fixture_root / 'stage2').mkdir(mode=0o700)
        durable_json(fixture_root / 'stage2/input_manifest.json', {'development_ids': ['lifecycle']})
        (fixture_root / '.env').write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
        gateway_image = docker('image', 'inspect', 'uts-stage2-gateway:1', '--format', '{{.Id}}')
        guard_image = docker('image', 'inspect', 'uts-stage2-egress-fixture:1', '--format', '{{.Id}}')
        from harbor.models.task.task import Task
        task = Task(root / 'stage2/fixtures/lifecycle')
        task.config.environment.docker_image = guard_image
        if harness == 'openhands':
            task.config.environment.docker_image = docker('image', 'inspect', 'uts-stage2-openhands-fixture:1', '--format', '{{.Id}}')
            task.config.environment.cpus = 2
            task.config.environment.memory_mb = 4096
            task.config.agent.timeout_sec = 180
        observed = {}
        settings = ModelSettings(8192 if harness == 'openhands' else 64, 1., 'high')
        def compose(**kwargs):
            kwargs['tokenizer_dir'] = root / '.cache/stage2-tokenizer'
            result = compose_runtime(**kwargs)
            result['services']['model-gateway']['entrypoint'] = ['python', '/study/stage2/production_runtime_probe.py']
            result['services']['model-gateway']['command'] = ['--gateway']
            if harness == 'openhands':
                result['services']['model-gateway']['command'].append('--native-openhands')
            return result
        def factory(**kwargs):
            if harness == 'openhands':
                import types
                from native_agents import agent_factory, ModelSettings
                agent = agent_factory('openhands', ModelSettings(8192, 1., 'high'))(**kwargs)
                if full_install:
                    # Exercise the real production installer, including hash
                    # enforcement, instead of trusting the prepared fixture.
                    return agent
                async def prepared_install(self, environment):
                    version = await environment.exec(self.get_version_command(), timeout_sec=30)
                    if version.return_code != 0:
                        raise RuntimeError('Prepared native installation is not usable')
                # Only the fixture has a preinstalled dependency environment.
                # The production factory still installs into official images.
                agent.install = types.MethodType(prepared_install, agent)
                return agent
            class ProbeAgent:
                async def setup(self, env): pass
                async def run(self, instruction, env, context):
                    payload = {'model': MODEL, 'max_tokens': 64, 'temperature': 1., 'reasoning': {'effort': 'high'},
                               'messages': [{'role': 'user', 'content': instruction}]}
                    def request():
                        req = urllib.request.Request(kwargs['host_api_base'] + '/chat/completions',
                            data=json.dumps(payload).encode(), headers={
                                'Authorization': 'Bearer ' + kwargs['trial_token'], 'Content-Type': 'application/json'})
                        with urllib.request.urlopen(req, timeout=60) as response:
                            return json.load(response)
                    response = await asyncio.to_thread(request)
                    observed['real_host_bridge_roundtrip'] = response['choices'][0]['message']['content'] == 'UTS_RUNTIME_OK'
                    if not observed['real_host_bridge_roundtrip']:
                        raise RuntimeError('Synthetic provider response mismatch')
                    result = await env.exec('printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result', timeout_sec=10)
                    if result.return_code != 0:
                        raise RuntimeError('Fixture write failed')
            return ProbeAgent()
        try:
            # The real dataset is not edited. These substitutions are confined
            # to this explicit fixture entry point, never a scoring CLI.
            with patch('scored_trial.frozen_dataset', return_value=root / 'stage2/fixtures'), \
                 patch('harbor.models.task.task.Task', return_value=task), \
                 patch('scored_trial.compose_runtime', side_effect=compose):
                result = await run_trial(root=fixture_root, trial_id='synthetic-runtime',
                    task_id='lifecycle', stage='development', agent_factory=factory,
                    model_settings=settings,
                    gateway_image=gateway_image, guard_image=guard_image,
                    setup_timeout_seconds=900 if full_install else 30)
            checks = dict(observed, verifier_reward_one=result.get('verifier_result', {}).get('rewards', {}).get('reward') == 1,
                model_revoked=result.get('model_revoked') is True,
                clean_status=result['status'] == 'verified',
                billing_verified=result.get('billing', {}).get('billing_verified') is True,
                containers_removed=result['containers_removed'], networks_removed=result['networks_removed'],
                volumes_removed=result['volumes_removed'])
            receipts = list((fixture_root / '.runtime/stage2/scored-attempts/synthetic-runtime').glob('*.receipt.json'))
            checks['expected_reconciled_synthetic_receipts'] = len(receipts) == (2 if harness == 'openhands' else 1)
            checks['runtime_sources_unchanged'] = source_hashes(root) == LOADED_SOURCE_HASHES
            evidence = {'kind': 'synthetic_full_runner_not_benchmark_score', 'live_api_calls': 0,
                'gateway_image': gateway_image, 'guard_image': guard_image,
                'harness': harness, 'task_image': task.config.environment.docker_image,
                'installation_mode': 'production_hash_locked' if full_install else 'prepared_fixture',
                'model_protocol_sha256': settings.fingerprint(), 'source_hashes': LOADED_SOURCE_HASHES,
                'runtime_path': str(fixture_root.relative_to(root)), 'checks': checks,
                'status': 'passed' if all(checks.values()) else 'failed'}
        except Exception as exc:
            evidence = {'kind': 'synthetic_full_runner_not_benchmark_score', 'live_api_calls': 0,
                'status': 'failed', 'error_type': type(exc).__name__,
                'runtime_path': str(fixture_root.relative_to(root))}
            (fixture_root / 'error.txt').write_text(str(exc))
        durable_json(output, evidence)
        print(json.dumps(evidence))
        if evidence['status'] != 'passed':
            raise RuntimeError('Synthetic runtime qualification failed; evidence preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--rebuild-gateway', action='store_true')
    parser.add_argument('--harness', choices=['marker', 'openhands'], default='marker')
    parser.add_argument('--full-install', action='store_true', help='Qualify the production OpenHands installer')
    args = parser.parse_args()
    asyncio.run(probe(args.label, wait=args.wait, rebuild_gateway=args.rebuild_gateway,
                      harness=args.harness, full_install=args.full_install))

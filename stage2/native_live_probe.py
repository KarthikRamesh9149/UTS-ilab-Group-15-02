"""Explicit paid native-harness compatibility check, never benchmark scoring.

Uses the original shared setup ledger and a disposable marker task. No hidden
benchmark material or scored-trial allowance is used. No automatic retries.
"""
import argparse
import asyncio
from dataclasses import asdict
import fcntl
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import patch
import host_environment

from model_protocol import ModelSettings
from native_agents import agent_factory
from native_setup_accounting import audit_setup
from production_compose import compose_runtime
from qualify_oracle import check_host
from scored_gateway import durable_json, private_directory
from scored_trial import run_trial, docker
from scoring_admission import source_hashes
from completion_wait import validate_completion_wait


def native_setup_command(trial_id, config_name, completion_wait_seconds):
    wait_seconds = validate_completion_wait(completion_wait_seconds)
    return ['--root', '/study', '--trial', trial_id,
        '--token-file', '/run/trial-token', '--credential-file', '/run/openrouter.env',
        '--socket', '/socket/private/model.sock', '--settings-file',
        '/study/.runtime/stage2/native-setup-configs/' + config_name,
        '--completion-wait-seconds', str(wait_seconds)]


async def probe(harness, label, settings, *, execute=False, wait=False):
    if not execute:
        raise ValueError('Explicit --execute required for paid compatibility check')
    if harness not in {'terminus-2', 'openhands', 'custom'} or not label.isalnum():
        raise ValueError('Registered harness and unique alphanumeric label required')
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    runtime = private_directory(root / '.runtime/stage2')
    trial_id = f'setup-native-{harness}-{label}'
    output = root / 'stage2' / f'native_live_{harness}_{label}.json'
    loaded = source_hashes(root)
    with (runtime / 'scored.lock').open('a+') as owner:
        while True:
            try:
                fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not wait: raise
                await asyncio.sleep(5)
        check_host()
        host_identity = host_environment.snapshot()
        if output.exists() or (runtime / 'native-setup-configs' / (trial_id + '.json')).exists():
            raise ValueError('Existing compatibility attempt must not be replayed')
        if source_hashes(root) != loaded:
            raise ValueError('Sources changed while waiting; no request sent')
        if not (runtime / 'setup_budget.sqlite').is_file():
            raise ValueError('Original shared setup ledger required')
        config = private_directory(runtime / 'native-setup-configs') / (trial_id + '.json')
        durable_json(config, asdict(settings))
        fixture = Path(tempfile.mkdtemp(prefix='native-live-', dir=runtime))
        private_directory(fixture / 'stage2')
        durable_json(fixture / 'stage2/input_manifest.json', {'development_ids': ['lifecycle']})
        # Qualify the already-built image shared with the synthetic runtime
        # proof. Rebuilding here would invalidate that immutable identity.
        gateway = docker('image', 'inspect', 'uts-stage2-gateway:1', '--format', '{{.Id}}')
        guard = docker('image', 'inspect', 'uts-stage2-egress-fixture:1', '--format', '{{.Id}}')
        from harbor.models.task.task import Task
        task = Task(root / 'stage2/fixtures/lifecycle')
        task.config.environment.docker_image = docker('image', 'inspect', 'uts-stage2-terminus-fixture:1', '--format', '{{.Id}}')
        task.config.environment.cpus = 2
        task.config.environment.memory_mb = 4096
        task.config.agent.timeout_sec = 180
        def compose(**kwargs):
            kwargs.update(state_dir=runtime, credential_file=root / '.env',
                          tokenizer_dir=root / '.cache/stage2-tokenizer')
            value = compose_runtime(**kwargs)
            service = value['services']['model-gateway']
            service['entrypoint'] = ['python', '/study/stage2/native_setup_gateway.py']
            service['command'] = native_setup_command(trial_id, config.name,
                                                      kwargs['completion_wait_seconds'])
            return value
        factory = agent_factory('C0' if harness == 'custom' else harness, settings,
                                **({'custom_max_model_calls': 6} if harness == 'custom' else {}))
        evidence = {'kind': f'actual_{harness.replace("-2", "")}_agent_live_setup_not_scored',
            'harness': harness, 'trial_id': trial_id, 'model_protocol_sha256': settings.fingerprint(),
            'source_hashes': loaded, 'gateway_image': gateway, 'guard_image': guard,
            'runtime_path': str(fixture.relative_to(root)), 'status': 'failed',
            'host_environment': host_identity}
        try:
            with patch('scored_trial.frozen_dataset', return_value=root / 'stage2/fixtures'), \
                 patch('harbor.models.task.task.Task', return_value=task), \
                 patch('scored_trial.compose_runtime', side_effect=compose), \
                 patch('scored_trial.audit_trial', side_effect=lambda *args: audit_setup(runtime, trial_id, settings)):
                result = await run_trial(root=fixture, trial_id=trial_id, task_id='lifecycle',
                    stage='development', agent_factory=factory, model_settings=settings,
                    gateway_image=gateway, guard_image=guard, setup_timeout_seconds=900,
                    billing_runtime=runtime, billing_kind='setup')
            billing = audit_setup(runtime, trial_id, settings)
            logs = fixture / '.runtime/stage2/scored-trials' / trial_id / 'agent'
            trajectory = {'terminus-2': 'trajectory.json', 'openhands': 'openhands.trajectory.json',
                          'custom': 'custom-trajectory.json'}[harness]
            reward = (result.get('verifier_result') or {}).get('rewards', {}).get('reward')
            checks = {'agent_created_file': reward == 1,
                'native_tool_roundtrip': reward == 1 and billing['requests'] >= 2,
                'settings_on_wire': billing['requests'] > 0 and billing['model_protocol_sha256'] == settings.fingerprint(),
                'billing_verified': billing['billing_verified'],
                'cleanup_verified': all(result.get(k) is True for k in ['model_revoked', 'containers_removed', 'networks_removed', 'volumes_removed']),
                'trajectory_written': (logs / trajectory).is_file(),
                'metadata_trace_complete': result.get('trace', {}).get('status') == 'complete_metadata_spool_not_cloud_export',
                'runtime_sources_unchanged': source_hashes(root) == loaded,
                'host_environment_unchanged': host_environment.snapshot() == host_identity,
                'runtime_images_preserved': all(
                    docker('image', 'inspect', image, '--format', '{{.Id}}') == image
                    for image in (gateway, guard))}
            evidence.update(checks=checks, billing=billing, live_api_calls=billing['requests'],
                            status='passed' if all(checks.values()) else 'failed')
        except Exception as exc:
            evidence['error_type'] = type(exc).__name__
            # Unknown dispatch count stays unknown, never invent zero usage.
            evidence['live_api_calls'] = None
            (fixture / 'error.txt').write_text(str(exc))
        durable_json(output, evidence)
        print(json.dumps(evidence), flush=True)
        if evidence['status'] != 'passed':
            raise RuntimeError('Native live check failed; evidence and billing retained')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness', required=True, choices=['terminus-2', 'openhands', 'custom'])
    parser.add_argument('--label', required=True)
    parser.add_argument('--max-output-tokens', type=int, required=True)
    parser.add_argument('--temperature', type=float, required=True)
    parser.add_argument('--reasoning-effort', required=True, choices=['low', 'medium', 'high'])
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--wait', action='store_true')
    args = parser.parse_args()
    asyncio.run(probe(args.harness, args.label,
        ModelSettings(args.max_output_tokens, args.temperature, args.reasoning_effort),
        execute=args.execute, wait=args.wait))

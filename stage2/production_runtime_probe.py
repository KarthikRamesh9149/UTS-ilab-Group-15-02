"""Real runtime wiring with a synthetic provider; never a scored/API result."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import uuid


def gateway_fixture(native_openhands=False, native_custom=False):
    if native_openhands and native_custom:
        raise ValueError('Select only one native fixture harness')
    from gateway_policy import MODEL, ENDPOINT
    from scored_gateway import serve
    from setup_probe import CONTEXT
    from unittest.mock import patch
    from gateway_policy import prepare_request
    from model_protocol import ModelSettings
    original_enforce = ModelSettings.enforce
    def record_rejection(payload, error):
        # Fixture-only diagnostics: no prompt text, tool arguments, headers,
        # credentials or upstream requests are recorded here.
        details = {'error': str(error), 'fields': sorted(payload),
                   'content_types': [type(m.get('content')).__name__ for m in payload.get('messages', [])],
                   'settings': {key: payload.get(key) for key in
                                ['model', 'max_tokens', 'max_completion_tokens', 'temperature', 'top_p', 'reasoning', 'reasoning_effort']}}
        Path('/study/.runtime/stage2/fixture-rejection.json').write_text(json.dumps(details))
    def diagnosed_prepare(payload):
        try:
            return prepare_request(payload)
        except ValueError as exc:
            record_rejection(payload, exc)
            raise
    def diagnosed_enforce(self, payload):
        try:
            return original_enforce(self, payload)
        except ValueError as exc:
            record_rejection(payload, exc)
            raise
    class SyntheticProvider:
        calls = 0
        def metadata(self):
            return {'data': {'id': MODEL, 'endpoints': [{'tag': ENDPOINT,
                'quantization': 'fp8', 'context_length': CONTEXT,
                'pricing': {'prompt': '.00000006', 'completion': '.00000018'}}]}}
        def key_status(self):
            return {'limit_remaining': '25'}
        def balance(self):
            return '25'
        def complete(self, request):
            self.calls += 1
            message = {'role': 'assistant', 'content': 'UTS_RUNTIME_OK'}
            finish = 'stop'
            if native_openhands or native_custom:
                if request.get('reasoning') != {'effort': 'high'} or request.get('temperature') != 1.0 or request.get('max_tokens') != 8192:
                    raise ValueError('Native harness settings not preserved')
                tools = {tool['function']['name'] for tool in request.get('tools', [])}
                names = ('execute', 'complete_task') if native_custom else ('execute_bash', 'finish')
                name = names[0] if self.calls == 1 else names[1]
                if name not in tools or self.calls > 2:
                    raise ValueError('Unexpected native fixture tool sequence')
                args = ({'command': 'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result'}
                        if self.calls == 1 else
                        {'summary': 'Fixture marker written.'} if native_custom else {'message': 'Fixture complete.'})
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'synthetic-call-' + str(self.calls), 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            return {'id': 'synthetic-' + str(self.calls), 'model': MODEL,
                'object': 'chat.completion', 'created': 1,
                'choices': [{'index': 0, 'finish_reason': finish, 'message': message}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 4, 'cost': '.000001'}}
        def generation(self, identifier):
            return {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.000001'}
    with patch('openrouter_transport.OpenRouter', return_value=SyntheticProvider()), \
         patch('gateway_core.prepare_request', side_effect=diagnosed_prepare), \
         patch.object(ModelSettings, 'enforce', diagnosed_enforce):
        try:
            serve('/study', 'synthetic-runtime', 'development', '/run/trial-token',
                  '/run/openrouter.env', '/socket/private/model.sock')
        except KeyboardInterrupt:
            pass


async def probe(label):
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.models.task.config import EnvironmentConfig
    from harbor.models.trial.paths import TrialPaths
    from production_compose import compose_runtime
    from gateway_policy import MODEL
    if not label.isalnum():
        raise ValueError('Alphanumeric label required')
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    output = root / 'stage2' / ('production_runtime_probe_' + label + '.json')
    if output.exists():
        raise ValueError('Preserve previous evidence')
    trial = Path(tempfile.mkdtemp(prefix='production-runtime-', dir=root / '.runtime/stage2'))
    state = trial / 'state'
    state.mkdir(mode=0o700)
    from model_protocol import ModelSettings, freeze_protocol
    freeze_protocol(state, ModelSettings(64, 1., 'high'))
    token = secrets.token_hex(32)
    token_file, credential = trial / 'token', trial / 'credential'
    token_file.write_text(token)
    credential.write_text('OPENROUTER_API_KEY=synthetic-not-a-real-key\n')
    def docker(*args):
        return subprocess.check_output(['docker', *args], text=True, stderr=subprocess.PIPE, timeout=60).strip()
    images = {name: docker('image', 'inspect', tag, '--format', '{{.Id}}') for name, tag in {
        'gateway': 'uts-stage2-gateway:1', 'guard': 'uts-stage2-egress-fixture:1'}.items()}
    compose = compose_runtime(gateway_image=images['gateway'], guard_image=images['guard'],
        state_dir=state, tokenizer_dir=root / '.cache/stage2-tokenizer',
        credential_file=credential, token_file=token_file, trial_id='synthetic-runtime',
        # Colima virtiofs presents these private Mac binds as root-owned.
        # Keep 0700 permissions; do not chown the user's host files.
        stage='development', uid=0, gid=0)
    compose['services']['model-gateway']['entrypoint'] = ['python', '/study/stage2/production_runtime_probe.py']
    compose['services']['model-gateway']['command'] = ['--gateway']
    compose['services']['main']['user'] = '65534:65534'
    override = trial / 'compose.json'
    override.write_text(json.dumps(compose))
    name = 'uts-production-fixture-' + uuid.uuid4().hex[:10]
    paths = TrialPaths(trial_dir=trial)
    env = DockerEnvironment(environment_dir=root / 'stage2/fixtures', environment_name=name,
        session_id=name, trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image=images['guard'], cpus=1, memory_mb=256),
        extra_docker_compose=[override])
    result = {'kind': 'production_wiring_synthetic_provider_not_scored',
        'time_utc': datetime.now(timezone.utc).isoformat(), 'live_api_calls': 0,
        'images': images, 'checks': {}, 'trial_path': str(trial.relative_to(root))}
    checks = result['checks']
    try:
        await env.start(force_build=False)
        ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + name,
                     '--filter', 'label=com.docker.compose.service=main').split()
        if len(ids) != 1:
            raise RuntimeError('Expected one task')
        inspected = json.loads(docker('inspect', ids[0]))[0]
        mounts = [m['Destination'] for m in inspected['Mounts']]
        checks['task_has_no_gateway_mounts'] = not any(p.startswith(('/socket', '/study', '/run/trial-token', '/run/openrouter.env')) for p in mounts)
        checks['task_is_nonroot'] = inspected['Config']['User'] == '65534:65534'
        host = inspected['HostConfig']
        checks['official_fixture_limits_preserved'] = host['NanoCpus'] == 1_000_000_000 and host['Memory'] == 256 * 1024**2
        dropped = {cap.removeprefix('CAP_') for cap in host['CapDrop']}
        checks['task_guarded_namespace'] = host['NetworkMode'].startswith('container:') and {'NET_ADMIN', 'NET_RAW'} <= dropped
        checks['no_host_port_or_privilege'] = not host['PortBindings'] and not host['Privileged'] and not host['CapAdd']
        payload = json.dumps({'model': MODEL, 'messages': [{'role': 'user', 'content': 'Synthetic runtime check'}],
                              'max_tokens': 64, 'temperature': 1., 'reasoning': {'effort': 'high'}})
        code = "import json,urllib.request; r=urllib.request.Request('http://127.0.0.1:8765/v1/chat/completions',data=" + repr(payload.encode()) + ",headers={'Authorization':" + repr('Bearer ' + token) + ",'Content-Type':'application/json'}); print(json.load(urllib.request.urlopen(r,timeout=60))['choices'][0]['message']['content'])"
        import shlex
        response = await env.exec('python -c ' + shlex.quote(code), timeout_sec=70)
        checks['nonroot_model_roundtrip'] = response.return_code == 0 and response.stdout.strip() == 'UTS_RUNTIME_OK'
        public = await env.exec("python -c \"import urllib.request; assert urllib.request.urlopen('https://openrouter.ai/api/v1/models',timeout=20).status==200\"", timeout_sec=30)
        checks['public_metadata_https'] = public.return_code == 0
        proof = await env.exec("python -c \"from pathlib import Path; assert not Path('/socket').exists(); assert not Path('/var/run/docker.sock').exists(); assert not Path('/run/openrouter.env').exists(); Path('/tmp/uts-persistence').write_text('OK')\"", timeout_sec=10)
        checks['private_paths_absent_and_task_writable'] = proof.return_code == 0
        await env.stop_service('model-gateway')
        blocked = await env.exec('python -c ' + shlex.quote(code), timeout_sec=70)
        checks['model_access_revoked_before_verifier'] = blocked.return_code != 0 and '502' in ((blocked.stderr or '') + (blocked.stdout or ''))
        persistence = await env.exec('cat /tmp/uts-persistence', timeout_sec=10)
        checks['task_state_survives_revocation'] = persistence.stdout.strip() == 'OK'
        receipts = list((state / 'scored-attempts/synthetic-runtime').glob('*.receipt.json'))
        checks['one_durable_reconciled_receipt'] = len(receipts) == 1
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        result['error'] = str(exc)[:1200]
        (trial / 'error.txt').write_text(str(exc))
        for service in ['socket-init', 'model-gateway', 'model-relay']:
            found = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + name,
                           '--filter', 'label=com.docker.compose.service=' + service).split()
            if len(found) == 1:
                logs = subprocess.run(['docker', 'logs', found[0]], capture_output=True, text=True, timeout=10)
                (trial / (service + '.log')).write_text(logs.stdout + logs.stderr)
    finally:
        await env.stop(delete=True)
    checks['containers_removed'] = not docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + name)
    checks['networks_removed'] = not docker('network', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + name)
    checks['volumes_removed'] = not docker('volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + name)
    result['status'] = 'passed' if checks and all(checks.values()) and 'error_type' not in result else 'failed'
    with output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))
    if result['status'] != 'passed':
        raise RuntimeError('Production wiring fixture failed; preserve evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gateway', action='store_true')
    parser.add_argument('--native-openhands', action='store_true')
    parser.add_argument('--native-custom', action='store_true')
    parser.add_argument('--label', default='v1')
    args = parser.parse_args()
    if args.gateway:
        gateway_fixture(args.native_openhands, args.native_custom)
    else:
        asyncio.run(probe(args.label))

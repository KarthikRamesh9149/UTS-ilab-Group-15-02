"""Native OpenHands fixture via private gateway socket. Scripted model only."""
import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import tempfile
import uuid

TOKEN = 'synthetic-openhands-fixture'
SOCKET = '/socket/private/model.sock'


def serve_gateway():
    from budget_ledger import Ledger
    from gateway_core import Gateway, Trial, token_digest
    from gateway_http import make_unix_server
    from gateway_policy import MODEL
    Path('/socket/private').mkdir(mode=0o700)
    calls = []
    requests = []
    def factory():
        ledger = Ledger('/evidence/synthetic.sqlite', '.1', '.055')
        def upstream(request):
            calls.append(request)
            tools = {t['function']['name']: t['function'] for t in request.get('tools', [])}
            name = 'execute_bash' if len(calls) == 1 else 'finish'
            if name not in tools or len(calls) > 4:
                raise ValueError('Unexpected tool schema or excess calls')
            args = {'command': 'printf UTS_OPENHANDS_OK > /tmp/uts-openhands-result.txt'} if name == 'execute_bash' else {'message': 'Fixture complete.'}
            return {'id': 'synthetic-openhands-' + str(len(calls)), 'object': 'chat.completion',
                'created': 1, 'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'tool_calls',
                    'message': {'role': 'assistant', 'content': None, 'tool_calls': [{
                        'id': 'call_' + str(len(calls)), 'type': 'function',
                        'function': {'name': name, 'arguments': json.dumps(args)}}]}}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150, 'cost': '.001'}}
        core = Gateway(ledger, Trial('openhands-fixture', 'development', token_digest(TOKEN)),
            lambda: '25', lambda request: '.01', upstream,
            lambda identifier: {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.001'})
        class Recorder:
            def complete(self, token, payload):
                requests.append(payload)
                with Path('/evidence/request-' + str(len(requests)) + '.json').open('x') as handle:
                    json.dump(payload, handle)
                return core.complete(token, payload)
        return Recorder()
    with make_unix_server(factory, SOCKET) as server:
        server.serve_forever()


async def main(label):
    os.umask(0o077)
    from harbor.agents.installed.openhands import OpenHands
    from harbor.environments.docker.docker import DockerEnvironment
    from harbor.models.agent.context import AgentContext
    from harbor.models.task.config import EnvironmentConfig
    from harbor.models.trial.paths import TrialPaths
    from gateway_policy import MODEL
    root = Path(__file__).resolve().parents[1]
    if not label.isalnum():
        raise ValueError('Alphanumeric evidence label required')
    output = root / 'stage2' / ('openhands_agent_probe_' + label + '.json')
    if output.exists():
        raise ValueError('Preserve prior evidence')
    trial = Path(tempfile.mkdtemp(prefix='openhands-agent-', dir=root / '.runtime' / 'stage2'))
    gateway_dir = trial / 'gateway'
    gateway_dir.mkdir(mode=0o700)
    paths = TrialPaths(trial_dir=trial)
    paths.agent_dir.mkdir(parents=True, exist_ok=True)
    name = 'uts-openhands-fixture-' + uuid.uuid4().hex[:10]
    image = subprocess.check_output(['docker', 'image', 'inspect', 'uts-stage2-openhands-fixture:1', '--format', '{{.Id}}'], text=True).strip()
    compose = {'services': {
        'main': {'network_mode': 'none', 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'volumes': ['model-socket:/socket:ro', str(root / 'stage2') + ':/code:ro'],
            'depends_on': {'model-gateway': {'condition': 'service_healthy'}}},
        'model-gateway': {'image': 'sha256:b6007a73910218ab068c7a9a7fb91e68f97017ab486af0ecd00403561a64e573',
            'network_mode': 'none', 'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
            'entrypoint': ['python', '/code/openhands_agent_probe.py', '--gateway'],
            'volumes': ['model-socket:/socket', str(root / 'stage2') + ':/code:ro', str(gateway_dir) + ':/evidence'],
            'healthcheck': {'test': ['CMD', 'test', '-S', SOCKET], 'interval': '1s', 'timeout': '2s', 'retries': 20},
            'cpus': 1, 'mem_limit': '256m'}}, 'volumes': {'model-socket': {}}}
    override = trial / 'fixture-compose.json'
    override.write_text(json.dumps(compose))
    environment = DockerEnvironment(environment_dir=root / 'stage2' / 'fixtures', environment_name=name,
        session_id=name, trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image=image, cpus=2, memory_mb=4096),
        extra_docker_compose=[override])
    class PreparedOpenHands(OpenHands):
        async def install(self, environment):
            result = await environment.exec(self.get_version_command(), timeout_sec=30)
            if result.return_code != 0:
                raise RuntimeError('Pinned OpenHands installation not usable')
    evidence = {'kind': 'actual_openhands_scripted_model_not_scored', 'live_api_calls': 0,
        'time_utc': datetime.now(timezone.utc).isoformat(), 'image_id': image,
        'trial_path': str(trial.relative_to(root)), 'checks': {}}
    try:
        await environment.start(force_build=False)
        await environment.ensure_dirs(['/logs/agent'])
        await environment.exec('python /code/container_model_relay.py --socket /socket/private/model.sock --port 8765 >/tmp/model-relay.log 2>&1 &', timeout_sec=10)
        await asyncio.sleep(.5)
        agent = PreparedOpenHands(logs_dir=paths.agent_dir, model_name='openai/' + MODEL,
            version='0.62.0', python_version='3.12', api_base='http://127.0.0.1:8765/v1',
            extra_env={'LLM_API_KEY': TOKEN}, num_retries=0, max_iterations=4,
            model_info={'max_input_tokens': 1048576, 'max_output_tokens': 2048})
        await asyncio.wait_for(agent.setup(environment), timeout=60)
        context = AgentContext()
        await asyncio.wait_for(agent.run('Create /tmp/uts-openhands-result.txt containing exactly UTS_OPENHANDS_OK.', environment, context), timeout=180)
        result = await environment.exec('cat /tmp/uts-openhands-result.txt', timeout_sec=10)
        evidence['checks']['agent_created_file'] = result.return_code == 0 and result.stdout == 'UTS_OPENHANDS_OK'
        evidence['context'] = context.model_dump(exclude={'rollout_details'})
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    except Exception as exc:
        evidence.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1000])
    finally:
        try:
            await environment.download_dir('/logs/agent', paths.agent_dir)
        finally:
            await environment.stop(delete=True)
    evidence['recorded_requests'] = len(list(gateway_dir.glob('request-*.json')))
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2, default=str)
        handle.write('\n')
    print(json.dumps(evidence, indent=2, default=str))
    if evidence['status'] != 'passed':
        raise RuntimeError('OpenHands integration fixture failed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gateway', action='store_true')
    parser.add_argument('--label', default='v1')
    args = parser.parse_args()
    if args.gateway:
        serve_gateway()
    else:
        asyncio.run(main(args.label))

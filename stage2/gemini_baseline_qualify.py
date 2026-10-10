"""Native Terminus/OpenHands scripted Docker lifecycles; never paid inference.

Run in a key-free Linux controller with Docker access and a native evidence
volume. Task/controller share only an internal Docker network during the agent
phase. The HTTP responder validates the real client payload with frozen wire().
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import uuid
from aiohttp import ClientSession, web
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from gemini_baseline_agents import ActivatedBaseline, native_agent, bundle_digest
from gemini_laptop_policy import MODEL, wire, atomic_json
from gemini_laptop_run import environment_for, audit
from gemini_laptop_logs import PrivateLog, LoggedEnvironment
from local_trace import PhaseRecorder, TraceSpool
from trial_execution import execute_phases


def docker(*arguments):
    return subprocess.check_output(['docker', *arguments], text=True).strip()


class ScriptedGateway:
    """No upstream URL, client or credential; authenticated synthetic replies only."""
    def __init__(self, harness, directory, recorder):
        self.harness, self.directory, self.recorder = harness, directory, recorder
        self.token = secrets.token_hex(32)
        self.active = None
        self.revoked = False
        self.calls = 0
        self.invalid_requests = 0
        self.errors = []

    async def start(self):
        app = web.Application(client_max_size=16 * 1024**2)
        app.router.add_post('/v1/chat/completions', self.handle)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner, '0.0.0.0', 0)
        await self.site.start()
        self.port = self.site._server.sockets[0].getsockname()[1]
        self.url = f'http://127.0.0.1:{self.port}/v1'

    def activate(self, trial_id, deadline):
        if self.active is not None or self.revoked:
            raise RuntimeError('Synthetic trial already active or revoked')
        self.active = (trial_id, deadline)

    async def revoke(self):
        self.active = None
        self.revoked = True

    async def close(self):
        await self.revoke()
        await self.runner.cleanup()

    async def handle(self, request):
        if (request.headers.get('Authorization') != 'Bearer ' + self.token
                or not self.active or time.monotonic() >= self.active[1]):
            return web.json_response({'error': {'message': 'Synthetic trial revoked'}}, status=403)
        started = time.time_ns()
        try:
            raw = await request.json()
            atomic_json(self.directory / f'client-request-{self.calls + self.invalid_requests + 1:02d}.json', raw)
            body = wire(raw)
            atomic_json(self.directory / f'canonical-request-{self.calls + 1:02d}.json', body)
            if self.calls >= 8:
                raise ValueError('Synthetic responder turn guard reached')
            self.calls += 1
            if self.harness == 'terminus-2':
                answer = {'analysis': 'Synthetic lifecycle qualification.',
                    'plan': 'Write the marker and complete.',
                    'commands': [{'keystrokes': 'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result\n',
                                  'duration': 0.1}] if self.calls == 1 else [],
                    'task_complete': self.calls > 1}
                message = {'role': 'assistant', 'content': json.dumps(answer)}
                finish_reason = 'stop'
            else:
                name = 'execute_bash' if self.calls == 1 else 'finish'
                names = {tool['function']['name'] for tool in body.get('tools', [])}
                if name not in names:
                    raise ValueError('Native OpenHands tool schema differs')
                arguments = ({'command': 'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result'}
                             if self.calls == 1 else {'message': 'Synthetic fixture complete.'})
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': f'synthetic-{self.calls}', 'type': 'function',
                    'function': {'name': name, 'arguments': json.dumps(arguments)}}]}
                finish_reason = 'tool_calls'
            response = {'id': f'synthetic-{self.harness}-{self.calls}', 'object': 'chat.completion',
                'created': 1, 'model': MODEL, 'provider': 'Google AI Studio',
                'choices': [{'index': 0, 'message': message, 'finish_reason': finish_reason}],
                'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150, 'cost': 0}}
            atomic_json(self.directory / f'scripted-response-{self.calls:02d}.json', response)
            return web.json_response(response)
        except Exception as error:
            self.invalid_requests += 1
            self.errors.append(type(error).__name__ + ': ' + str(error))
            return web.json_response({'error': {'message': 'Synthetic protocol check failed'}}, status=400)
        finally:
            ended = time.time_ns()
            self.recorder(kind='generation', started_ns=started, ended_ns=ended,
                seconds=(ended - started) / 1e9, status='error' if self.errors else 'ok',
                metrics={'requests': 1, 'charged_nanodollars': 0})


class TracedEnvironment(LoggedEnvironment):
    def __init__(self, environment, log, recorder):
        super().__init__(environment, log)
        self.recorder = recorder

    async def exec(self, command, **kwargs):
        started, status = time.time_ns(), 'error'
        try:
            result = await super().exec(command, **kwargs)
            status = 'ok' if result.return_code == 0 else 'error'
            return result
        finally:
            ended = time.time_ns()
            self.recorder(kind='tool', started_ns=started, ended_ns=ended,
                seconds=(ended - started) / 1e9, status=status, metrics={'tool_calls': 1})


async def fixture(root, private, harness, task_image, bundle, bundle_sha256, protocol_sha256):
    name = 'uts-gemini-baseline-fixture-' + uuid.uuid4().hex[:12]
    task = Task(root / 'stage2/fixtures/lifecycle')
    task.config.environment.docker_image = task_image
    task.config.environment.memory_mb = 2048 if harness == 'openhands' else 1024
    task.config.agent.timeout_sec = 180  # Synthetic limits, never benchmark limits.
    task.config.verifier.timeout_sec = 30
    paths = TrialPaths(private / f'{harness}-{time.time_ns()}')
    paths.trial_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    env = environment_for(task, paths, name)
    override = paths.trial_dir / 'internal-network.json'
    atomic_json(override, {'networks': {'default': {'internal': True}}})
    env.extra_docker_compose_paths = [override]
    recorder = PhaseRecorder(TraceSpool(paths.trial_dir / 'traces'), trial_id=paths.trial_dir.name,
        task_id='synthetic-lifecycle', harness=harness, protocol_sha256=protocol_sha256)
    def observe(**fields):
        # The fixture verifier checks a marker; its reward is not a benchmark score.
        fields['reward'] = None
        recorder(**fields)
    gateway = ScriptedGateway(harness, paths.trial_dir, observe)
    attached = None
    result = None
    await gateway.start()
    try:
        await asyncio.wait_for(env.start(force_build=False), 120)
        inspected = audit(env, task)
        task_ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + name).split()
        container = json.loads(docker('inspect', task_ids[0]))[0]
        networks = list(container['NetworkSettings']['Networks'])
        if len(networks) != 1 or not json.loads(docker('network', 'inspect', networks[0]))[0]['Internal']:
            raise RuntimeError('Internal fixture network required')
        docker('network', 'connect', networks[0], os.environ['HOSTNAME'])
        attached = networks[0]
        controller = json.loads(docker('inspect', os.environ['HOSTNAME']))[0]
        address = controller['NetworkSettings']['Networks'][attached]['IPAddress']
        container_base = f'http://{address}:{gateway.port}/v1'
        async def revoke():
            nonlocal attached
            await gateway.revoke()
            async with ClientSession() as client:
                response = await client.post(gateway.url + '/chat/completions',
                    headers={'Authorization': 'Bearer ' + gateway.token}, json={})
                if response.status != 403:
                    raise RuntimeError('Synthetic endpoint accepted a revoked request')
            if attached:
                docker('network', 'disconnect', attached, os.environ['HOSTNAME'])
                attached = None
        agent = native_agent(harness, logs_dir=paths.agent_dir,
            api_base=gateway.url if harness == 'terminus-2' else container_base,
            token=gateway.token, timeout=task.config.agent.timeout_sec,
            bundle=bundle, bundle_sha256=bundle_sha256)
        agent = ActivatedBaseline(agent, gateway, paths.trial_dir.name, task.config.agent.timeout_sec)
        log = PrivateLog(paths.trial_dir / 'activity.jsonl')
        result = await execute_phases(agent=agent, environment=TracedEnvironment(env, log, observe),
            task=task, paths=paths, revoke_model=revoke, setup_timeout_seconds=180, phase_observer=observe)
        remaining = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + name)
        passed = (result['status'] == 'verified' and not result['agent_error_type']
            and result['verifier_result']['rewards']['reward'] == 1
            and not result['cleanup_errors'] and not result.get('trace_errors')
            and gateway.revoked and 2 <= gateway.calls <= 8 and gateway.invalid_requests == 0 and not remaining)
        evidence = {'harness': harness, 'passed': passed, 'paid_generations': 0,
            'scope': 'synthetic_native_lifecycle_not_benchmark', 'scripted_requests': gateway.calls,
            'invalid_requests': gateway.invalid_requests, 'model_revoked': gateway.revoked,
            'task_containers_removed': not bool(remaining), 'internal_network': True,
            'resource_audit': inspected, 'lifecycle_status': result['status'],
            'agent_error_type': result['agent_error_type'], 'verifier_error_type': result['verifier_error_type'],
            'cleanup_errors': result['cleanup_errors'], 'trace_errors': result.get('trace_errors', [])}
        atomic_json(paths.trial_dir / 'private-lifecycle.json', result)
        atomic_json(paths.trial_dir / 'private-protocol-errors.json', gateway.errors)
        return evidence
    finally:
        try:
            await gateway.close()
        finally:
            try:
                if attached:
                    docker('network', 'disconnect', attached, os.environ['HOSTNAME'])
            finally:
                await env.stop(delete=True)


async def run(root, private, task_image):
    # The qualification controller must not receive an upstream credential.
    if Path('/run/openrouter-key').exists() or os.getenv('OPENROUTER_API_KEY'):
        raise RuntimeError('Key-free synthetic controller required')
    controller = json.loads(docker('inspect', os.environ['HOSTNAME']))[0]
    networks = controller['NetworkSettings']['Networks']
    if not networks or any(not json.loads(docker('network', 'inspect', network))[0]['Internal']
                           for network in networks):
        raise RuntimeError('Controller must start on internal networks only')
    bundle = Path('/opt/uts-openhands-bundle.tar.gz')
    source_hashes = {name: hashlib.sha256((root / 'stage2' / name).read_bytes()).hexdigest()
        for name in ('gemini_baseline_agents.py', 'gemini_baseline_budget.py', 'gemini_baseline_qualify.py',
                     'native_agents.py', 'gemini_laptop_policy.py', 'trial_execution.py',
                     'gemini_laptop_logs.py', 'gemini_laptop_run.py', 'openhands-requirements.lock',
                     'Dockerfile.gemini-baselines')}
    protocol_sha256 = hashlib.sha256(json.dumps(source_hashes, sort_keys=True).encode()).hexdigest()
    bundle_sha256 = bundle_digest(bundle)
    result = {'scope': 'synthetic_native_qualification_not_benchmark', 'paid_generations': 0,
        'new_model_spending_usd': '0', 'source_hashes': source_hashes,
        'bundle_sha256': bundle_sha256, 'task_image': task_image,
        'controller_image': docker('inspect', os.environ['HOSTNAME'], '--format', '{{.Image}}'),
        'fixtures': []}
    for harness in ('terminus-2', 'openhands'):
        result['fixtures'].append(await fixture(root, private, harness, task_image,
                                               bundle, bundle_sha256, protocol_sha256))
        atomic_json(private / 'qualification.json', result)
    result['passed'] = all(row['passed'] for row in result['fixtures'])
    atomic_json(private / 'qualification.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'source_hashes'}), flush=True)
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--task-image', required=True)
    args = parser.parse_args()
    os.umask(0o077)
    args.private.mkdir(parents=True, mode=0o700, exist_ok=False)
    return asyncio.run(run(Path.cwd(), args.private, args.task_image))


if __name__ == '__main__':
    raise SystemExit(main())

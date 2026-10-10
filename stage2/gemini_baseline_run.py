"""Authorized native dev20 comparison; shared original US$20 ledger, no replay.

The same run_cell path is exercised by key-free fake-provider qualification.
Raw native logs and exchanges stay in the private Linux evidence volume.
"""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import time
import uuid
from aiohttp import ClientSession, web
from harbor.models.task.task import Task
from harbor.models.trial.paths import TrialPaths
from gemini_baseline_agents import ActivatedBaseline, native_agent, bundle_digest
from gemini_baseline_gateway import BaselineGateway
from gemini_baseline_qualify import TracedEnvironment, docker
from gemini_laptop_logs import PrivateLog
from gemini_laptop_policy import (MODEL, SNAPSHOT, PROVIDER, CONTEXT, MAX_OUTPUT,
    INPUT_PRICE, OUTPUT_PRICE, RESERVATION, CAP, credential, atomic_json, money)
from gemini_laptop_run import environment_for, audit
from local_trace import PhaseRecorder, TraceSpool
from trial_execution import execute_phases

STUDY = 'gemini-native-dev20-laptop-20261010'
BUNDLE_SHA = 'd35faf2393bb4f0ee8cc4470c7d7f6b7adb029d843a3b8728e9a8b7ad1126758'


def source_hashes(root):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted((root / 'stage2').glob('*.py')) if not p.name.startswith('test_')}


def frozen_inputs(prior_root, proposal):
    prior = prior_root / '.runtime/gemini-dev20-laptop-20260930'
    prep = json.loads((prior / 'preparation.json').read_text())
    suffix = Path(prep['tasks_path'].split('/repo/', 1)[1])
    if suffix.is_absolute() or '..' in suffix.parts:
        raise ValueError('Unsafe frozen path')
    tasks = prior_root / suffix
    provenance = json.loads((prior_root / 'stage2/dataset_provenance.json').read_text())
    expected = provenance['canonical']['file_hashes']
    if {p.relative_to(tasks).as_posix() for p in tasks.rglob('*') if p.is_file()} != {r['path'] for r in expected}:
        raise ValueError('Frozen inventory changed')
    for row in expected:
        path = tasks / row['path']
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('Frozen source changed')
    manifest = json.loads((prior_root / 'stage2/input_manifest.json').read_text())
    if manifest['development_ids'] != proposal['frozen_dataset']['task_ids']:
        raise ValueError('Frozen order changed')
    if hashlib.sha256((prior / 'ledger.json').read_bytes()).hexdigest() != proposal['prior_ledger_sha256']:
        raise ValueError('Inherited spending changed')
    for row in proposal['frozen_dataset']['tasks']:
        image = json.loads(docker('image', 'inspect', row['docker_image']))[0]
        if image['Id'] != row['cached_image']['id']:
            raise ValueError('Official image changed')
    return tasks, prior / 'ledger.json'


def classify(result, stop):
    if result.get('cleanup_errors') or result.get('status') != 'verified':
        return 'infrastructure_failure'
    if stop == 'budget_stop':
        return 'budget_stop'
    if stop or result.get('agent_error_type') not in {None, 'TimeoutError'}:
        return 'infrastructure_failure'
    reward = ((result.get('verifier_result') or {}).get('rewards') or {}).get('reward')
    return 'pass' if reward == 1 else 'verifier_failure'


async def run_cell(root, private, gateway, cell, task, protocol_sha, *, fixture=False):
    trial_id = cell['trial_id']
    paths = TrialPaths(private / 'trials' / trial_id)
    paths.trial_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    project = 'uts-gemini-native-' + uuid.uuid4().hex[:12]
    env = environment_for(task, paths, project)
    if fixture:
        override = paths.trial_dir / 'internal-network.json'
        atomic_json(override, {'networks': {'default': {'internal': True}}})
        env.extra_docker_compose_paths = [override]
    recorder = PhaseRecorder(TraceSpool(private / 'traces' / trial_id),
        trial_id=trial_id, task_id=cell['task_id'], harness=cell['harness'], protocol_sha256=protocol_sha)
    def observe(**fields):
        if fixture:
            fields['reward'] = None
        recorder(**fields)
    gateway.recorder = observe
    gateway.trace_errors = []
    gateway.token = secrets.token_hex(32)
    attached = None
    result = {}
    row = {**cell, 'agent_timeout_seconds': task.config.agent.timeout_sec,
        'verifier_timeout_seconds': task.config.verifier.timeout_sec,
        'classification': 'infrastructure_failure'}
    before = len(gateway.ledger.data['requests'])
    started = time.monotonic()
    started_ns = time.time_ns()
    async def revoke():
        nonlocal attached
        await gateway.revoke()
        async with ClientSession() as client:
            async with client.post(gateway.url + '/chat/completions', json={},
                    headers={'Authorization': 'Bearer ' + gateway.token}) as response:
                if response.status != 403:
                    raise RuntimeError('Revoked endpoint accepted a request')
        if attached:
            docker('network', 'disconnect', attached, os.environ['HOSTNAME'])
            attached = None
    try:
        await asyncio.wait_for(env.start(force_build=False), task.config.environment.build_timeout_sec)
        row['environment'] = audit(env, task)
        base = gateway.url
        if cell['harness'] == 'openhands':
            task_ids = docker('ps', '-q', '--filter', 'label=com.docker.compose.project=' + project).split()
            container = json.loads(docker('inspect', task_ids[0]))[0]
            networks = list(container['NetworkSettings']['Networks'])
            if len(networks) != 1:
                raise RuntimeError('Single task network required')
            attached = networks[0]
            docker('network', 'connect', attached, os.environ['HOSTNAME'])
            controller = json.loads(docker('inspect', os.environ['HOSTNAME']))[0]
            address = controller['NetworkSettings']['Networks'][attached]['IPAddress']
            base = await gateway.attach_interface(address)
        agent = native_agent(cell['harness'], logs_dir=paths.agent_dir, api_base=base,
            token=gateway.token, timeout=task.config.agent.timeout_sec,
            bundle=Path('/opt/uts-openhands-bundle.tar.gz'), bundle_sha256=BUNDLE_SHA)
        agent = ActivatedBaseline(agent, gateway, trial_id, task.config.agent.timeout_sec)
        result = await execute_phases(agent=agent, environment=TracedEnvironment(
            env, PrivateLog(paths.trial_dir / 'activity.jsonl'), observe),
            task=task, paths=paths, revoke_model=revoke, setup_timeout_seconds=180,
            phase_observer=observe, retained_result=result)
        row.update(classification=classify(result, gateway.stop_reason),
            reward=((result.get('verifier_result') or {}).get('rewards') or {}).get('reward'),
            status=result.get('status'), agent_error_type=result.get('agent_error_type'),
            verifier_error_type=result.get('verifier_error_type'), cleanup_errors=result.get('cleanup_errors'),
            model_revoked=result.get('model_revoked'), phase_seconds=result.get('phase_seconds'),
            trace_errors=gateway.trace_errors + result.get('trace_errors', []))
    except BaseException as error:
        row.update(status='orchestrator_failed', error_type=type(error).__name__)
        atomic_json(paths.trial_dir / 'private-error.json', {'type': type(error).__name__, 'message': str(error)})
        gateway.stop_reason = gateway.stop_reason or 'orchestrator_failure'
        if isinstance(error, asyncio.CancelledError):
            gateway.stop_reason = 'interrupted'
    finally:
        try:
            await revoke()
            await asyncio.wait_for(env.stop(delete=True), 60)
        except Exception as error:
            row.setdefault('cleanup_errors', []).append(type(error).__name__)
            gateway.stop_reason = gateway.stop_reason or 'cleanup_failure'
        gateway.recorder = None
        remaining = docker('ps', '-aq', '--filter', 'label=com.docker.compose.project=' + project)
        row['task_containers_removed'] = not bool(remaining)
        if remaining:
            gateway.stop_reason = 'cleanup_failure'
        if not recorder.closed:
            try:
                observe(kind='cleanup', started_ns=started_ns, ended_ns=time.time_ns(),
                    seconds=time.monotonic() - started, status='error')
                observe(kind='trial', started_ns=started_ns, ended_ns=time.time_ns(),
                    seconds=time.monotonic() - started, status='error')
            except Exception as error:
                row.setdefault('trace_errors', []).append(type(error).__name__)
        requests = gateway.ledger.data['requests'][before:]
        row.update(duration_seconds=time.monotonic() - started, physical_requests=len(requests),
            known_spending_usd=str(sum((money(r['cost_usd']) for r in requests if r.get('cost_usd') is not None), Decimal(0))),
            unresolved_requests=sum(r.get('cost_usd') is None for r in requests),
            gateway_stop=gateway.stop_reason)
        atomic_json(paths.trial_dir / 'private-result.json', result)
        atomic_json(paths.trial_dir / 'outcome.json', row)
    return row


def report(public, registration, rows, gateway):
    by_harness = {}
    for harness in ('terminus-2', 'openhands'):
        selected = [r for r in rows if r['harness'] == harness]
        counts = Counter(r['classification'] for r in selected)
        by_harness[harness] = {'planned': 20, 'started': len(selected),
            'official_scores': sum(r.get('reward') in {0, 1} for r in selected),
            **{key: counts[key] for key in ('pass', 'verifier_failure', 'infrastructure_failure', 'budget_stop')},
            'unstarted': 20 - len(selected)}
    budget = gateway.ledger.report()
    new = gateway.ledger.data['requests'][len(gateway.ledger.prior['requests']):]
    budget.update(comparison_known_spending_usd=str(sum((money(r['cost_usd']) for r in new if r.get('cost_usd') is not None), Decimal(0))),
        comparison_physical_requests=len(new),
        remaining_conservative_usd=str(CAP - gateway.ledger.known - gateway.ledger.unresolved))
    summary = {'experiment': STUDY, 'model': MODEL, 'scope': 'native Gemini baseline comparison; separate from DeepSeek and original custom run',
        'by_harness': by_harness, 'budget': budget,
        'stop_reason': gateway.stop_reason or ('forty_attempts_complete' if len(rows) == 40 else 'running'),
        'unstarted_cells': registration['cells'][len(rows):],
        'langfuse': {'status': 'private_spool_retained_export_after_batch'},
        'updated_utc': datetime.now(timezone.utc).isoformat()}
    atomic_json(public / 'summary.json', summary)
    atomic_json(public / 'tasks.json', rows)
    # No raw response, task solutions or original private exchanges.
    atomic_json(public / 'request-metadata.json', new)
    return summary


class FakeProvider:
    """Local scripted upstream, including metadata/receipts. No outside network."""
    def __init__(self, private):
        self.private, self.harness, self.calls = private, None, 0
    async def handle(self, request):
        if request.method == 'GET':
            if request.path.endswith('/key'):
                data = dict(limit=100, limit_remaining=100, usage=0)
            elif request.path.endswith('/credits'):
                data = dict(total_credits=100, total_usage=0)
            elif request.path.endswith('/generation'):
                data = dict(total_cost=0, model=MODEL, provider_name='Google AI Studio')
            else:
                data = {'endpoints': [dict(tag=PROVIDER, context_length=CONTEXT,
                    max_completion_tokens=MAX_OUTPUT, pricing=dict(prompt=str(INPUT_PRICE), completion=str(OUTPUT_PRICE)), name=SNAPSHOT)]}
            return web.json_response({'data': data})
        body = await request.json()
        if body['model'] != MODEL or body['provider']['only'] != [PROVIDER] or body['reasoning'] != {'effort': 'high'}:
            raise RuntimeError('Fake upstream route mismatch')
        self.calls += 1
        if self.calls > 8:
            return web.json_response({'error': 'fixture turn limit'}, status=400)
        if self.harness == 'terminus-2':
            message = {'role': 'assistant', 'content': json.dumps({'analysis': 'Synthetic only.',
                'plan': 'Write the marker and complete.', 'commands': [{'keystrokes':
                'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result\n', 'duration': 0.1}] if self.calls == 1 else [],
                'task_complete': self.calls > 1})}
            finish = 'stop'
        else:
            name = 'execute_bash' if self.calls == 1 else 'finish'
            args = {'command': 'printf UTS_LIFECYCLE_OK > /tmp/uts-lifecycle-result'} if self.calls == 1 else {'message': 'Synthetic complete.'}
            message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'fake-' + str(self.calls),
                'type': 'function', 'function': {'name': name, 'arguments': json.dumps(args)}}]}
            finish = 'tool_calls'
        return web.json_response({'id': 'synthetic-' + self.harness + '-' + str(self.calls),
            'object': 'chat.completion', 'created': 1, 'model': MODEL, 'provider': 'Google AI Studio',
            'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150, 'cost': 0}})
    async def start(self):
        app = web.Application(client_max_size=16 * 1024**2)
        app.router.add_route('*', '/{path:.*}', self.handle)
        self.runner = web.AppRunner(app, access_log=None)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        return 'http://127.0.0.1:' + str(site._server.sockets[0].getsockname()[1]) + '/v1'


async def run(args):
    root = Path.cwd()
    private = args.private
    private.mkdir(parents=True, mode=0o700, exist_ok=False)
    proposal = json.loads((root / 'stage2/results/gemini-baseline-qualification-20261010/comparison-proposal.json').read_text())
    tasks_path, prior_path = frozen_inputs(args.prior_root, proposal)
    source = source_hashes(root)
    protocol_sha = hashlib.sha256(json.dumps({'source': source, 'model': proposal['model_protocol'],
        'cells': proposal['proposed_cells']}, sort_keys=True).encode()).hexdigest()
    if bundle_digest('/opt/uts-openhands-bundle.tar.gz') != BUNDLE_SHA:
        raise ValueError('Qualified native bundle differs')
    cells = [{**cell, 'trial_id': f'gemini-native-{cell["order"]:02d}-{cell["harness"]}-{cell["task_id"]}'}
             for cell in proposal['proposed_cells']]
    provider = None
    if args.qualify:
        if Path('/run/openrouter-key').exists() or os.getenv('OPENROUTER_API_KEY'):
            raise ValueError('Qualification must be key-free')
        networks = json.loads(docker('inspect', os.environ['HOSTNAME']))[0]['NetworkSettings']['Networks']
        if not networks or any(not json.loads(docker('network', 'inspect', n))[0]['Internal'] for n in networks):
            raise ValueError('Qualification requires only internal networks')
        cells = [{'order': i + 1, 'trial_id': 'launcher-synthetic-' + h,
            'task_id': 'synthetic-lifecycle', 'harness': h} for i, h in enumerate(('terminus-2', 'openhands'))]
        provider = FakeProvider(private)
        origin = await provider.start()
    else:
        qual = json.loads(args.qualification.read_text())
        if qual.get('passed') is not True or qual['source_hashes'] != source or qual['bundle_sha256'] != BUNDLE_SHA:
            raise ValueError('Successful current-source launcher qualification required')
        info = json.loads(docker('info', '--format', '{{json .}}'))
        controller = json.loads(docker('inspect', os.environ['HOSTNAME']))[0]
        limit = controller['HostConfig']['Memory']
        maximum = max(r['memory_mb'] for r in proposal['frozen_dataset']['tasks']) * 1024**2
        if not 1024**3 <= limit <= 1536 * 1024**2 or info['MemTotal'] < maximum + limit + 1024**3:
            raise ValueError('Insufficient Docker capacity for official resources and controller')
        active = docker('ps', '-q', '--no-trunc').split()
        if active != [controller['Id']]:
            raise ValueError('Other Docker workloads must be stopped for this laptop batch')
        capacity = {'docker_memory_bytes': info['MemTotal'], 'docker_cpus': info['NCPU'],
            'controller_memory_limit_bytes': limit, 'maximum_official_task_memory_bytes': maximum,
            'daemon_memory_margin_bytes': 1024**3, 'other_docker_workloads_running': False}
    gateway = BaselineGateway('synthetic-key' if args.qualify else credential(args.key_file), private,
        prior_path=prior_path, prior_sha256=proposal['prior_ledger_sha256'],
        cells={c['trial_id']: c['harness'] for c in cells})
    if provider:
        gateway.origin = origin
    rows = []
    registration = {'experiment': STUDY, 'scope': 'synthetic' if args.qualify else 'paid_native_baselines',
        'user_authorization': 'Option 2: up to twenty Terminus and twenty OpenHands attempts under original shared US$20 cap',
        'cells': cells, 'source_hashes': source, 'protocol_sha256': protocol_sha,
        'model_protocol': proposal['model_protocol'], 'frozen_dataset': proposal['frozen_dataset'],
        'prior_ledger_sha256': proposal['prior_ledger_sha256'], 'bundle_sha256': BUNDLE_SHA,
        'controller_image': docker('inspect', os.environ['HOSTNAME'], '--format', '{{.Image}}'),
        'setup_timeout_seconds': 180, 'replays': 0, 'automatic_retries': 0,
        'started_utc': datetime.now(timezone.utc).isoformat()}
    if not args.qualify:
        registration['capacity_admission'] = capacity
    public = root / 'stage2/results' / STUDY
    try:
        registration['initial_credit'] = await gateway.start()
        if not args.qualify:
            if public.exists():
                raise ValueError('Study results already exist; no replay')
            public.mkdir(parents=True, exist_ok=False)
            atomic_json(public / 'registration.json', registration)
            atomic_json(public / 'launcher-qualification.json', qual)
        atomic_json(private / 'registration.json', registration)
        for cell in cells:
            await gateway.reconcile()
            credit = await gateway.credit()
            if (gateway.stop_reason or gateway.ledger.known + gateway.ledger.unresolved + RESERVATION > CAP
                    or gateway.ledger.unresolved + RESERVATION > money(credit['available_usd'])):
                gateway.stop_reason = gateway.stop_reason or 'budget_stop'
                break
            if args.qualify:
                task = Task(root / 'stage2/fixtures/lifecycle')
                task.config.environment.docker_image = args.fixture_image
                task.config.environment.memory_mb = 2048 if cell['harness'] == 'openhands' else 1024
                task.config.agent.timeout_sec, task.config.verifier.timeout_sec = 180, 30
                provider.harness, provider.calls = cell['harness'], 0
            else:
                task = Task(tasks_path / cell['task_id'])
                if task.has_steps or task.config.verifier.environment is not None:
                    raise ValueError('Unsupported official task topology')
            row = await run_cell(root, private, gateway, cell, task, protocol_sha, fixture=args.qualify)
            rows.append(row)
            atomic_json(private / 'tasks.json', rows)
            if not args.qualify:
                report(public, registration, rows, gateway)
            print(json.dumps(row), flush=True)
            if gateway.stop_reason or row.get('cleanup_errors') or not row['task_containers_removed'] or row.get('trace_errors'):
                gateway.stop_reason = gateway.stop_reason or 'evidence_or_cleanup_failure'
                break
        registration['final_credit'] = await gateway.credit()
        if args.qualify:
            result = {'scope': 'fake_provider_launcher_not_benchmark', 'paid_generations': 0,
                'passed': len(rows) == 2 and all(r['classification'] == 'pass' and r.get('model_revoked')
                    and r['task_containers_removed'] and not r.get('trace_errors') and not r.get('gateway_stop') for r in rows),
                'source_hashes': source, 'bundle_sha256': BUNDLE_SHA,
                'controller_image': registration['controller_image'], 'fixture_image': args.fixture_image,
                'fixtures': [{k: v for k, v in r.items() if k != 'reward'} for r in rows],
                'inherited_budget_preserved': gateway.ledger.data['requests'][:len(gateway.ledger.prior['requests'])] == gateway.ledger.prior['requests']}
            atomic_json(private / 'qualification.json', result)
            print(json.dumps({'qualification_passed': result['passed'], 'paid_generations': 0}), flush=True)
            return 0 if result['passed'] else 1
        final = report(public, registration, rows, gateway)
        atomic_json(public / 'credit-checks.json', {'initial': registration['initial_credit'], 'final': registration['final_credit']})
        print(json.dumps(final), flush=True)
        return 0
    finally:
        if hasattr(gateway, 'runner'):
            await gateway.close()
        elif hasattr(gateway, 'session'):
            await gateway.session.close()
        if provider:
            await provider.runner.cleanup()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--private', type=Path, required=True)
    parser.add_argument('--prior-root', type=Path, required=True)
    parser.add_argument('--qualification', type=Path)
    parser.add_argument('--key-file', type=Path, default=Path('/run/openrouter-key'))
    parser.add_argument('--qualify', action='store_true')
    parser.add_argument('--fixture-image', default='uts-gemini-baseline-task-fixture:20261010')
    args = parser.parse_args()
    os.umask(0o077)
    lock_path = args.private.parent / 'comparison.lock'
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        async def bounded():
            loop, current = asyncio.get_running_loop(), asyncio.current_task()
            for signum in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(signum, current.cancel)
            return await run(args)
        return asyncio.run(bounded())


if __name__ == '__main__':
    raise SystemExit(main())

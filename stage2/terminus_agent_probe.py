"""Actual Terminus-2 agent and Docker with scripted model replies; not scored."""
import asyncio
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
import secrets
from pathlib import Path
import subprocess
import tempfile
import threading
import types
import uuid

os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
from harbor.agents.terminus_2.terminus_2 import Terminus2
from harbor.environments.docker.docker import DockerEnvironment
from harbor.models.agent.context import AgentContext
from harbor.models.task.config import EnvironmentConfig
from harbor.models.trial.paths import TrialPaths
from budget_ledger import Ledger
from gateway_core import Gateway, Trial, token_digest
from gateway_http import make_server
from gateway_policy import MODEL
from openrouter_transport import OpenRouter, load_key
from receipt_polling import read_receipt
from setup_probe import full_context_bound, validate_metadata
from live_harbor_probe import save_new


class FixtureTerminus(Terminus2):
    """Connection-only fixture adjustment; preserve native agent prompt/loop."""
    def _init_llm(self, *args, **kwargs):
        client = super()._init_llm(*args, **kwargs)
        client.call = types.MethodType(type(client).call.__wrapped__, client)
        return client


async def main(live=False):
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    output = root / 'stage2' / ('terminus_agent_live_result.json' if live else 'terminus_agent_probe_result.json')
    if output.exists():
        raise ValueError('Refusing to overwrite agent fixture evidence')
    trial = Path(tempfile.mkdtemp(prefix='terminus-agent-', dir=root / '.runtime' / 'stage2'))
    paths = TrialPaths(trial_dir=trial)
    paths.agent_dir.mkdir(parents=True, exist_ok=True)
    name = 'uts-terminus-fixture-' + uuid.uuid4().hex[:10]
    image = subprocess.check_output(['docker', 'image', 'inspect', 'uts-stage2-terminus-fixture:1',
                                     '--format', '{{.Id}}'], text=True).strip()
    environment = DockerEnvironment(environment_dir=root / 'stage2' / 'fixtures',
        environment_name=name, session_id=name, trial_paths=paths,
        task_env_config=EnvironmentConfig(docker_image=image, cpus=1, memory_mb=1024),
        extra_docker_compose=[root / 'stage2' / 'fixtures' / 'docker-compose-isolation.yaml'])
    calls, ledgers = [], []
    trial_token = secrets.token_hex(32) if live else 'fixture'
    api = None
    if live:
        api = OpenRouter(load_key(root / '.env'), generation_enabled=True)
        validate_metadata(api.metadata())
        allowance = api.key_status()['limit_remaining']
        if allowance is None or Decimal(str(allowance)) < Decimal('.43'):
            raise ValueError('Insufficient known key allowance')
        preflight = Ledger(root / '.runtime' / 'stage2' / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        try:
            if preflight.pending():
                raise ValueError('Resolve pending requests before execution')
        finally:
            preflight.close()
        save_new(root / '.runtime' / 'stage2' / 'terminus-agent-live-v1.started',
                 {'trial': str(trial.relative_to(root)), 'time_utc': datetime.now(timezone.utc).isoformat()})
    def upstream(request):
        calls.append(request)
        if live:
            save_new(trial / ('request-' + str(len(calls)) + '.json'), request)
            response = api.complete(request)
            save_new(trial / ('response-' + str(len(calls)) + '.json'), response)
            return response
        commands = [{'keystrokes': 'printf UTS_AGENT_OK > /tmp/uts-agent-result.txt\n', 'duration': .1}] if len(calls) == 1 else []
        answer = {'analysis': 'Synthetic integration fixture.', 'plan': 'Write the marker, then finish.',
                  'commands': commands, 'task_complete': len(calls) > 1}
        return {'id': 'synthetic-terminus-' + str(len(calls)), 'object': 'chat.completion',
            'created': 1, 'model': MODEL, 'choices': [{'index': 0, 'finish_reason': 'stop',
              'message': {'role': 'assistant', 'content': json.dumps(answer)}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50, 'total_tokens': 150, 'cost': Decimal('.001')}}
    def factory():
        ledger = (Ledger(root / '.runtime' / 'stage2' / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
                  if live else Ledger(trial / 'synthetic-ledger.sqlite', '.1', '.055'))
        ledgers.append(ledger)
        def bound(request):
            if len(calls) >= 4:
                raise ValueError('Setup dispatch limit reached before reservation')
            return full_context_bound(request) if live else '.01'
        def receipt(identifier):
            if not live:
                return {'id': identifier, 'model': MODEL, 'provider_name': 'DeepInfra', 'total_cost': '.001'}
            value = read_receipt(api.generation, identifier)
            save_new(trial / ('receipt-' + str(len(calls)) + '.json'), value)
            return value
        return Gateway(ledger, Trial(name, 'setup' if live else 'development', token_digest(trial_token)),
            api.balance if live else lambda: '25', bound, upstream, receipt)
    server = make_server(factory)
    def serve():
        try:
            server.serve_forever()
        finally:
            for ledger in ledgers:
                ledger.close()
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    evidence = {'kind': 'actual_terminus_agent_live_setup_not_scored' if live else 'actual_terminus_agent_scripted_model_not_scored', 'live_api_calls': 0,
        'time_utc': datetime.now(timezone.utc).isoformat(), 'image_id': image,
        'trial_path': str(trial.relative_to(root)), 'checks': {}}
    try:
        await environment.start(force_build=False)
        agent = FixtureTerminus(logs_dir=paths.agent_dir, model_name='openai/' + MODEL,
            max_turns=4, api_base=f'http://127.0.0.1:{server.server_address[1]}/v1',
            llm_kwargs={'api_key': trial_token, 'num_retries': 0, 'timeout': 120 if live else 10},
            llm_call_kwargs={'max_tokens': 2048, **({'extra_body': {'reasoning': {'enabled': False}}} if live else {})},
            model_info={'max_input_tokens': 1048576, 'max_output_tokens': 2048,
                'input_cost_per_token': .00000006, 'output_cost_per_token': .00000018,
                'cache_read_input_token_cost': .000000015, 'cache_creation_input_token_cost': 0})
        evidence['native_prompt_sha256'] = hashlib.sha256(agent._get_prompt_template_path().read_bytes()).hexdigest()
        await asyncio.wait_for(agent.setup(environment), timeout=60)
        context = AgentContext()
        await asyncio.wait_for(agent.run('Create /tmp/uts-agent-result.txt containing exactly UTS_AGENT_OK.', environment, context), timeout=480 if live else 120)
        result = await environment.exec('cat /tmp/uts-agent-result.txt', timeout_sec=10)
        isolation = await environment.exec('test ! -e /Users/karthikramesh && test ! -e /var/run/docker.sock && test -z "$OPENROUTER_API_KEY"', timeout_sec=10)
        evidence['checks'] = {'agent_created_file': result.return_code == 0 and result.stdout == 'UTS_AGENT_OK',
            'at_least_two_native_model_turns': len(calls) >= 2,
            'host_secrets_not_visible': isolation.return_code == 0,
            'trajectory_written': any(paths.agent_dir.rglob('*.json'))}
        evidence['upstream_scripted_calls'] = len(calls)
        evidence['context'] = context.model_dump(exclude={'rollout_details'})
        evidence['status'] = 'passed' if all(evidence['checks'].values()) else 'failed'
    except Exception as exc:
        evidence.update(status='failed', error_type=type(exc).__name__, error=str(exc)[:1200])
    finally:
        await environment.stop(delete=True)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    if live:
        evidence['live_api_calls'] = len(calls)
        evidence.pop('upstream_scripted_calls', None)
        ledger = Ledger(root / '.runtime' / 'stage2' / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
        try:
            evidence['pending_requests'] = ledger.pending()
            evidence['total_setup_exposure_usd'] = str(Decimal(ledger.exposure()) / 1000000000)
            rows = ledger.db.execute('SELECT charged FROM requests WHERE trial=?', (name,)).fetchall()
            evidence['trial_reconciled_cost_usd'] = str(Decimal(sum(r[0] or 0 for r in rows)) / 1000000000)
            if evidence['pending_requests']:
                evidence['status'] = 'requires_reconciliation'
        finally:
            ledger.close()
    with output.open('x') as handle:
        json.dump(evidence, handle, indent=2, default=str)
        handle.write('\n')
    print(json.dumps(evidence, indent=2, default=str))
    if evidence['status'] != 'passed':
        raise RuntimeError('Actual agent fixture failed; preserve evidence')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Authorised one-shot paid setup fixture, at most four dispatches')
    args = parser.parse_args()
    asyncio.run(main(args.live))

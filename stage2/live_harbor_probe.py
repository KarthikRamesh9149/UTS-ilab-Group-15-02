"""One-shot paid setup: real Harbor client -> HTTP gateway -> pinned model.

Not an agent/task run. Uses only the existing aggregate $1 setup ledger and
reserves the full model input context. No generation retry is allowed.
"""
import argparse
import asyncio
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets
import threading

os.environ.setdefault('LITELLM_LOCAL_MODEL_COST_MAP', 'True')
from harbor.llms.lite_llm import LiteLLM
from budget_ledger import Ledger, UNIT
from gateway_core import Gateway, Trial, token_digest, reconcile_receipt
from gateway_http import make_server
from gateway_policy import MODEL
from openrouter_transport import OpenRouter, load_key
from receipt_polling import read_receipt
from setup_probe import full_context_bound, validate_metadata

FIXTURE = 'harbor-http-live-v1'


def save_new(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, default=str, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


async def execute(root):
    os.umask(0o077)
    runtime = root / '.runtime' / 'stage2'
    api = OpenRouter(load_key(root / '.env'), generation_enabled=True)
    validate_metadata(api.metadata())
    allowance = api.key_status()['limit_remaining']
    if allowance is None or Decimal(str(allowance)) < Decimal('.11'):
        raise ValueError('Insufficient known key allowance')
    ledger_path = runtime / 'setup_budget.sqlite'
    preflight = Ledger(ledger_path, '1', '1', {'setup': '1'})
    try:
        if preflight.pending():
            raise ValueError('Resolve existing pending requests first')
    finally:
        preflight.close()
    save_new(runtime / (FIXTURE + '.started'), {'time_utc': datetime.now(timezone.utc).isoformat()})
    token = secrets.token_hex(32)
    ledgers, calls = [], []
    def upstream(request):
        calls.append(True)
        response = api.complete(request)
        save_new(runtime / (FIXTURE + '.response.json'), response)
        return response
    def receipt(identifier):
        value = read_receipt(api.generation, identifier)
        save_new(runtime / (FIXTURE + '.receipt.json'), value)
        return value
    def factory():
        ledger = Ledger(ledger_path, '1', '1', {'setup': '1'})
        ledgers.append(ledger)
        return Gateway(ledger, Trial(FIXTURE, 'setup', token_digest(token)),
                       api.balance, full_context_bound, upstream, receipt)
    server = make_server(factory)
    def serve():
        try:
            server.serve_forever()
        finally:
            for ledger in ledgers:
                ledger.close()
    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    evidence = {'kind': 'real_harbor_http_provider_setup_not_scored', 'model': MODEL,
                'maximum_reserved_usd': str(full_context_bound({'max_tokens': 64})),
                'time_utc': datetime.now(timezone.utc).isoformat()}
    try:
        client = LiteLLM('openai/' + MODEL, temperature=0,
            api_base='http://127.0.0.1:' + str(server.server_address[1]) + '/v1',
            api_key=token, num_retries=0, timeout=120,
            model_info={'max_input_tokens': 1048576, 'max_output_tokens': 64,
                        'input_cost_per_token': .00000006, 'output_cost_per_token': .00000018,
                        'cache_read_input_token_cost': .000000015, 'cache_creation_input_token_cost': 0})
        response = await client.call.__wrapped__(client,
            'Reply with exactly UTS_OK and nothing else.', max_tokens=64,
            extra_body={'reasoning': {'enabled': False}})
        evidence.update(status='completed', client_text=response.content,
                        exact_text=response.content.strip() == 'UTS_OK')
    except Exception as exc:
        evidence.update(status='stopped_no_replay', error_type=type(exc).__name__)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=90)
    evidence['upstream_dispatches'] = len(calls)
    ledger = Ledger(ledger_path, '1', '1', {'setup': '1'})
    try:
        evidence['pending_requests'] = ledger.pending()
        evidence['total_setup_exposure_usd'] = str(Decimal(ledger.exposure()) / UNIT)
    finally:
        ledger.close()
    response_file = runtime / (FIXTURE + '.response.json')
    if response_file.exists():
        recorded = json.loads(response_file.read_text(), parse_float=Decimal)
        evidence.update(generation_id=recorded['id'], usage=recorded['usage'])
    save_new(root / 'stage2' / 'live_harbor_probe_result.json', evidence)
    print(json.dumps(evidence, default=str, indent=2))


def reconcile(root):
    os.umask(0o077)
    runtime = root / '.runtime' / 'stage2'
    recorded = json.loads((runtime / (FIXTURE + '.response.json')).read_text(), parse_float=Decimal)
    api = OpenRouter(load_key(root / '.env'))
    receipt = read_receipt(api.generation, recorded['id'])
    cost = reconcile_receipt(recorded, receipt)
    ledger = Ledger(runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
    try:
        pending = [p for p in ledger.pending() if p[1] == FIXTURE and p[3] == recorded['id']]
        if len(pending) != 1:
            raise ValueError('Expected one matching pending request')
        ledger.settle(pending[0][0], cost)
        evidence = {'status': 'reconciled_without_replay', 'generation_id': recorded['id'],
                    'actual_cost_usd': str(cost), 'total_setup_exposure_usd': str(Decimal(ledger.exposure()) / UNIT),
                    'remaining_credit_usd': str(api.balance())}
    finally:
        ledger.close()
    save_new(root / 'stage2' / 'live_harbor_probe_reconciled.json', evidence)
    print(json.dumps(evidence, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--execute', action='store_true')
    group.add_argument('--reconcile', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.execute:
        asyncio.run(execute(root))
    else:
        reconcile(root)

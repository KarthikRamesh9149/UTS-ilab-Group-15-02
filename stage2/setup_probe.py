"""One-shot real-model setup probe; not a scored trial or task execution.

Reserves the ENTIRE model input context at the routing price ceiling, plus
the requested maximum output, so this fixture needs no heuristic tokenizer.
All setup probes must share setup_budget.sqlite and its $1 aggregate ceiling.
This intentionally over-large bound cannot serve $0.055 scored trials.
"""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import secrets

from budget_ledger import Ledger, UNIT
from gateway_core import Gateway, Trial, token_digest, reconcile_receipt
from gateway_policy import MODEL, ENDPOINT
from openrouter_transport import OpenRouter, load_key

CONTEXT = 1048576
INPUT_PRICE = Decimal('0.00000010')
OUTPUT_PRICE = Decimal('0.00000020')


def validate_metadata(metadata):
    data = metadata['data']
    if data.get('id') != MODEL:
        raise ValueError('Model changed')
    endpoints = [e for e in data['endpoints'] if e.get('tag') == ENDPOINT]
    if len(endpoints) != 1:
        raise ValueError('Expected exactly the selected endpoint')
    endpoint = endpoints[0]
    if endpoint.get('quantization') != 'fp8' or endpoint.get('context_length') != CONTEXT:
        raise ValueError('Endpoint configuration changed')
    prices = endpoint['pricing']
    for name, ceiling in [('prompt', INPUT_PRICE), ('completion', OUTPUT_PRICE)]:
        price = Decimal(str(prices[name]))
        if not price.is_finite() or not 0 <= price <= ceiling:
            raise ValueError('Price outside frozen ceiling')
    for name, value in prices.items():
        if name not in {'prompt', 'completion', 'input_cache_read', 'discount'} and value is not None and Decimal(str(value)) != 0:
            raise ValueError('Unbudgeted billing category')
    if 'input_cache_read' in prices and Decimal(str(prices['input_cache_read'])) > INPUT_PRICE:
        raise ValueError('Cache read exceeds input ceiling')
    return endpoint


def full_context_bound(request):
    maximum = request['max_tokens']
    if type(maximum) is not int or not 0 < maximum <= 384000:
        raise ValueError('Invalid output limit')
    return CONTEXT * INPUT_PRICE + maximum * OUTPUT_PRICE


def main(execute):
    if not execute:
        raise SystemExit('Pass --execute to run this paid setup fixture')
    os.umask(0o077)
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime' / 'stage2'
    runtime.mkdir(parents=True, exist_ok=True)
    client = OpenRouter(load_key(root / '.env'), generation_enabled=True)
    endpoint = validate_metadata(client.metadata())
    key = client.key_status()
    if key['limit_remaining'] is None or Decimal(str(key['limit_remaining'])) < Decimal('0.11'):
        raise ValueError('Insufficient known key allowance')
    ledger = Ledger(runtime / 'setup_budget.sqlite', '1', '1', {'setup':'1'})
    marker = runtime / 'compatibility-plain-v1.started'
    # This persisted marker forbids accidental replay even after settlement.
    with marker.open('x') as handle:
        handle.write(datetime.now(timezone.utc).isoformat())
        handle.flush()
        os.fsync(handle.fileno())
    token = secrets.token_hex(32)
    response_path = runtime / 'compatibility-plain-v1.response.json'
    receipt_path = runtime / 'compatibility-plain-v1.receipt.json'
    def generate(request):
        response = client.complete(request)
        with response_path.open('x') as handle:
            json.dump(response, handle, default=str, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        return response
    def receipt(identifier):
        result = client.generation(identifier)
        with receipt_path.open('x') as handle:
            json.dump(result, handle, default=str, indent=2)
            handle.flush(); os.fsync(handle.fileno())
        return result
    gateway = Gateway(ledger, Trial('compatibility-plain-v1', 'setup', token_digest(token)),
                      client.balance, full_context_bound, generate, receipt)
    request = {'model': MODEL, 'messages':[{'role':'user','content':'Reply with exactly UTS_OK and nothing else.'}],
               'max_tokens':64, 'temperature':0, 'reasoning':{'enabled':False}}
    summary = {'kind':'setup_compatibility_not_scored', 'model':MODEL,
               'endpoint':ENDPOINT, 'maximum_reserved_usd':str(full_context_bound(request)),
               'time_utc':datetime.now(timezone.utc).isoformat()}
    try:
        response = gateway.complete(token, request)
        summary.update(status='billing_reconciled', generation_id=response['id'], usage=response['usage'],
                       text=response['choices'][0]['message'].get('content'),
                       finish_reason=response['choices'][0].get('finish_reason'))
    except Exception as exc:
        summary.update(status='stopped_requires_reconciliation', error_type=type(exc).__name__,
                       pending_requests=ledger.pending())
    finally:
        summary['ledger_exposure_usd'] = str(Decimal(ledger.exposure()) / UNIT)
        ledger.close()
    output = root / 'stage2' / 'setup_probe_result.json'
    with output.open('x') as handle:
        json.dump(summary, handle, default=str, indent=2)
        handle.write('\n')
    print(json.dumps(summary, default=str, indent=2))


def reconcile_existing():
    root = Path(__file__).resolve().parents[1]
    runtime = root / '.runtime' / 'stage2'
    response = json.loads((runtime / 'compatibility-plain-v1.response.json').read_text(), parse_float=Decimal)
    client = OpenRouter(load_key(root / '.env'))  # Generation disabled.
    receipt = client.generation(response['id'])
    actual = reconcile_receipt(response, receipt)
    ledger = Ledger(runtime / 'setup_budget.sqlite', '1', '1', {'setup':'1'})
    try:
        pending = ledger.pending()
        matches = [r for r in pending if r[3] == response['id'] and r[1] == 'compatibility-plain-v1']
        if len(matches) != 1:
            raise ValueError('Expected one matching unresolved request; refusing changes')
        ledger.settle(matches[0][0], actual)
        summary = {'kind':'setup_compatibility_not_scored', 'status':'reconciled_without_replay',
                   'generation_id':response['id'], 'model':response['model'],
                   'receipt_model':receipt['model'], 'provider':receipt['provider_name'],
                   'actual_cost_usd':str(actual), 'usage':response['usage'],
                   'text':response['choices'][0]['message']['content'],
                   'ledger_exposure_usd':str(Decimal(ledger.exposure()) / UNIT),
                   'remaining_credit_usd':str(client.balance()), 'key':client.key_status(),
                   'time_utc':datetime.now(timezone.utc).isoformat()}
    finally:
        ledger.close()
    with (root / 'stage2' / 'setup_probe_reconciled.json').open('x') as output:
        json.dump(summary, output, default=str, indent=2)
        output.write('\n')
    print(json.dumps(summary, default=str, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--reconcile', action='store_true')
    args = parser.parse_args()
    if args.execute and args.reconcile:
        parser.error('Choose execution or read-only reconciliation, not both')
    if args.reconcile:
        reconcile_existing()
    else:
        main(args.execute)

"""One-shot bounded setup calibration. Never used as a scored cost estimator."""
import argparse
import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets

from tokenizers import Tokenizer
from budget_ledger import Ledger, UNIT
from calibrate_tokenizer import HASHES, REVISION
from gateway_core import Gateway, Trial, token_digest
from gateway_policy import MODEL
from openrouter_transport import OpenRouter, load_key
from receipt_polling import read_receipt
from setup_probe import full_context_bound, validate_metadata


def save_new(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, default=str, indent=2, ensure_ascii=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())


def token_candidates(root, request):
    cache = root / '.cache/stage2-tokenizer'
    for name, expected in HASHES.items():
        if hashlib.sha256((cache / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Unreviewed tokenizer asset')
    spec = importlib.util.spec_from_file_location('pinned_dsv4_calibration', cache / 'encoding_dsv4.py')
    encoder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(encoder)
    tokenizer = Tokenizer.from_file(str(cache / 'tokenizer.json'))
    candidates = {}
    for layout in ['prepend_system', 'merge_first_system']:
        messages = copy.deepcopy(request['messages'])
        if request.get('tools'):
            if layout == 'merge_first_system' and messages[0]['role'] == 'system':
                messages[0]['tools'] = copy.deepcopy(request['tools'])
            else:
                messages.insert(0, {'role': 'system', 'content': '', 'tools': copy.deepcopy(request['tools'])})
        for mode, effort in [('chat', 'low'), ('thinking', 'low'), ('thinking', 'high'), ('thinking', 'max')]:
            rendered = encoder.encode_messages(copy.deepcopy(messages), thinking_mode=mode, reasoning_effort=effort)
            name = '/'.join([layout, mode, effort])
            candidates[name] = {'tokens': len(tokenizer.encode(rendered, add_special_tokens=False).ids),
                                'rendered_utf8_bytes': len(rendered.encode('utf-8'))}
    return candidates


def fixtures(root):
    unicode_history = {'model': MODEL, 'max_tokens': 64, 'temperature': 0,
        'reasoning': {'enabled': False}, 'messages': [
            {'role': 'system', 'content': 'Synthetic accounting test. Return only OK; never execute commands.'},
            {'role': 'user', 'content': 'Unicode and escaped text: café 東京 🧪\nJSON: {"a":"b\\c"}'},
            {'role': 'assistant', 'content': 'Acknowledged.'},
            {'role': 'user', 'content': 'Reply OK.'}]}
    prior = json.loads((root / 'stage2/openhands_agent_probe_v2.json').read_text())
    native = json.loads((root / prior['trial_path'] / 'gateway/request-2.json').read_text())
    native.pop('max_completion_tokens', None)
    native['max_tokens'] = 64
    # Exact saved native history/tool schemas; output reduced for accounting
    # calibration only. Returned tool calls are never executed.
    native_chat = copy.deepcopy(native)
    native_chat['reasoning'] = {'enabled': False}
    return [('unicode-history', unicode_history), ('openhands-tool-history-chat', native_chat),
            ('openhands-tool-history-default', native)]


def main(root, execute):
    if not execute:
        raise ValueError('Explicit --execute required for paid setup calibration')
    os.umask(0o077)
    cases = fixtures(root)
    prepared = [(name, request, token_candidates(root, request)) for name, request in cases]
    runtime = root / '.runtime/stage2'
    api = OpenRouter(load_key(root / '.env'), generation_enabled=True)
    validate_metadata(api.metadata())
    if Decimal(str(api.key_status()['limit_remaining'])) < Decimal('.11'):
        raise ValueError('Insufficient key allowance')
    ledger = Ledger(runtime / 'setup_budget.sqlite', '1', '1', {'setup': '1'})
    report = {'kind': 'real_provider_token_calibration_not_scored', 'revision': REVISION,
              'time_utc': datetime.now(timezone.utc).isoformat(), 'cases': [],
              'qualified_for_scored_reservations': False}
    try:
        if ledger.pending():
            raise ValueError('Resolve outstanding requests first')
        for name, request, candidates in prepared:
            trial = 'token-calibration-' + name + '-v1'
            save_new(runtime / (trial + '.started'), {'trial': trial, 'time_utc': report['time_utc']})
            save_new(runtime / (trial + '.request.json'), request)
            token = secrets.token_hex(32)
            def upstream(payload):
                response = api.complete(payload)
                save_new(runtime / (trial + '.response.json'), response)
                return response
            def receipt(identifier):
                value = read_receipt(api.generation, identifier)
                save_new(runtime / (trial + '.receipt.json'), value)
                return value
            gateway = Gateway(ledger, Trial(trial, 'setup', token_digest(token)),
                              api.balance, full_context_bound, upstream, receipt)
            response = gateway.complete(token, request)
            actual = response['usage']['prompt_tokens']
            row = {'fixture': name, 'generation_id': response['id'], 'usage': response['usage'],
                   'reserved_usd': str(full_context_bound(request)), 'local_candidates': candidates,
                   'matching_candidates': [k for k, v in candidates.items() if v['tokens'] == actual]}
            report['cases'].append(row)
            print(json.dumps({'fixture': name, 'actual_prompt_tokens': actual,
                              'matching_candidates': row['matching_candidates'], 'cost': response['usage']['cost']}, default=str))
        report['status'] = 'calibration_completed_not_qualified'
    except Exception as exc:
        report.update(status='stopped_no_replay', error_type=type(exc).__name__)
        raise
    finally:
        report['pending_requests'] = len(ledger.pending())
        report['total_setup_exposure_usd'] = str(Decimal(ledger.exposure()) / UNIT)
        ledger.close()
        save_new(root / 'stage2/extended_token_calibration_result.json', report)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--execute', action='store_true')
    main(Path(__file__).resolve().parents[1], parser.parse_args().execute)

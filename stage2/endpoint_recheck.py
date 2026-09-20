"""Explicit one-call endpoint diagnostic; never a benchmark retry or admission.

Uses the original setup allowance and accounts for existing scored liabilities.
Does not settle, rewrite or replay any previous scored request or result.
"""
import argparse
from contextlib import ExitStack, closing
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3

from gateway_policy import MODEL, ENDPOINT
from model_protocol import read_protocol
from native_setup_accounting import audit_setup
from native_setup_gateway import NativeSetupSession
from openrouter_transport import OpenRouter, load_key
from post_trial_receipts import collect_receipts
from scored_gateway import durable_json, private_directory


def scored_state(runtime):
    path = runtime / 'scored_budget.sqlite'
    if path.is_symlink() or not path.is_file():
        raise ValueError('Original scored ledger required')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Scored ledger integrity failure')
        pending = db.execute("SELECT reserved FROM requests WHERE state='pending'").fetchall()
        if any(type(row[0]) is not int or row[0] < 0 for row in pending):
            raise ValueError('Invalid outstanding reservation')
    hashes = {str(path.relative_to(runtime)): hashlib.sha256(path.read_bytes()).hexdigest()}
    for result in sorted((runtime / 'scored-trials').glob('*/result.json')):
        if result.is_symlink() or result.parent.is_symlink():
            raise ValueError('Unsafe scored evidence')
        hashes[str(result.relative_to(runtime))] = hashlib.sha256(result.read_bytes()).hexdigest()
    return Decimal(sum(row[0] for row in pending)) / 1_000_000_000, hashes


class ReservedClient:
    def __init__(self, client, liability):
        self.client, self.liability, self.calls = client, liability, 0

    def metadata(self): return self.client.metadata()
    def generation(self, identifier): return self.client.generation(identifier)

    def balance(self):
        return Decimal(str(self.client.balance())) - self.liability

    def key_status(self):
        result = dict(self.client.key_status())
        if result['limit_remaining'] is not None:
            result['limit_remaining'] = Decimal(str(result['limit_remaining'])) - self.liability
        return result

    def complete(self, request):
        if self.calls:
            raise ValueError('Diagnostic permits exactly one upstream dispatch')
        self.calls += 1
        return self.client.complete(request)


def run(root, label, *, execute=False, client=None):
    if execute is not True or not isinstance(label, str) or not re.fullmatch(r'[a-zA-Z0-9]{1,32}', label):
        raise ValueError('Explicit execution and a unique bounded label required')
    root = Path(root).resolve()
    runtime = private_directory(root / '.runtime/stage2')
    identifier = 'setup-native-endpoint-recheck-' + label
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock'):
            fd = os.open(runtime / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            lock = stack.enter_context(os.fdopen(fd, 'r+'))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        attempts = runtime / 'native-setup-attempts' / identifier
        if attempts.exists() or attempts.is_symlink():
            raise ValueError('Existing diagnostic cannot be replayed')
        settings = read_protocol(runtime)
        liability, before = scored_state(runtime)
        original = client or OpenRouter(load_key(root / '.env'), generation_enabled=True)
        guarded = ReservedClient(original, liability)
        token = secrets.token_hex(32)
        summary = {'kind': 'endpoint_connectivity_diagnostic_not_harness_qualification_or_score',
            'time_utc': datetime.now(timezone.utc).isoformat(), 'model': MODEL, 'endpoint': ENDPOINT,
            'trial_id': identifier, 'model_protocol_sha256': settings.fingerprint(),
            'prior_scored_reservation_retained_usd': str(liability),
            'old_failed_request_replayed': False, 'benchmark_resumption_authorized': False}
        try:
            with NativeSetupSession(root, identifier, token, guarded, settings=settings) as session:
                # The shared gateway session is infrastructure reuse only:
                # this request does not invoke Harbor or a native agent loop.
                durable_json(attempts / 'diagnostic-purpose.json', summary)
                response = session.complete(token, {'model': MODEL,
                    'messages': [{'role': 'user', 'content': 'Reply with exactly UTS_OK and nothing else.'}],
                    'max_tokens': settings.max_output_tokens, 'temperature': settings.temperature,
                    'reasoning': {'effort': settings.reasoning_effort}})
                summary['generation_id'] = response['id']
                choices = response.get('choices')
                choice = choices[0] if isinstance(choices, list) and choices else None
                message = choice.get('message') if isinstance(choice, dict) else None
                message = message.get('content') if isinstance(message, dict) else None
                summary['expected_reply_received'] = isinstance(message, str) and message.strip() == 'UTS_OK'
            collect_receipts(runtime, identifier, kind='setup', client=original)
            summary['billing'] = audit_setup(runtime, identifier, settings)
            summary['status'] = 'reply_and_billing_verified' if summary['expected_reply_received'] else 'response_received_fixture_not_matched'
        except Exception as exc:
            summary.update(status='diagnostic_failed_no_replay', error_type=type(exc).__name__)
            if attempts.exists():
                diagnostic = attempts / '000001.transport-error.json'
                if diagnostic.is_file() and not diagnostic.is_symlink():
                    summary['transport_diagnostic'] = json.loads(diagnostic.read_text())
        summary['upstream_generation_calls'] = guarded.calls
        _, after = scored_state(runtime)
        if after != before:
            raise RuntimeError('Scored evidence changed during diagnostic')
        summary['original_scored_ledger_and_results_unchanged'] = True
        summary['original_scored_ledger_and_results_sha256'] = after
        if attempts.exists():
            durable_json(attempts / 'endpoint-diagnostic-result.json', summary)
        return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[1], args.label, execute=args.execute)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['status'] == 'reply_and_billing_verified' else 1)

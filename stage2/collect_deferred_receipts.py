"""Stage delayed receipts without altering frozen billing or benchmark evidence.

This is host maintenance, NOT an admission or settlement path. It performs only
historical generation GETs, never completions. Every original ledger, result,
deferral and attempt artifact remains unchanged. A qualified additive settlement
consumer is still required before any reservation can be reduced.
"""
import argparse
from contextlib import ExitStack, closing
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from budget_ledger import dollars
from deferred_billing import _encoded, _json, _read, _write, validate_deferrals
from gateway_core import reconcile_receipt
from openrouter_transport import OpenRouter, TransportError, load_key

DIRECTORY = 'deferred-receipt-recovery-v1'
RECEIPT_FIELDS = ('id', 'model', 'provider_name', 'total_cost', 'is_byok',
                  'cancelled', 'native_tokens_prompt', 'native_tokens_completion')


def _private_directory(path):
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Private owned recovery directory required')


def _document(runtime, entry, request_id, receipt):
    """Validate an existing settled response, never invent a missing response."""
    if (not isinstance(request_id, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}', request_id)
            or request_id not in entry['unverified_receipt_request_ids']):
        raise ValueError('Only a registered settled missing-receipt request may be collected')
    rows = [row for row in entry['ledger_rows'] if row[0] == request_id]
    if len(rows) != 1:
        raise ValueError('Unique original request row required')
    row = rows[0]
    _, trial, maximum, charge, state, generation, receipt_state, estimate = row
    if state != 'settled' or receipt_state != 'pending' or charge is None or not generation:
        raise ValueError('Original settled charge and pending receipt required')
    attempts = 'native-setup-attempts' if entry['kind'] == 'setup' else 'scored-attempts'
    evidence = runtime / attempts / trial
    matches = []
    for name, expected_hash in entry['evidence_sha256'].items():
        if not name.endswith('.reservation.json'):
            continue
        raw = _read(evidence / name, runtime)
        if hashlib.sha256(raw).hexdigest() != expected_hash:
            raise ValueError('Original reservation evidence changed')
        if _json(raw).get('reservation_id') == request_id:
            matches.append(name.removesuffix('.reservation.json') + '.response.json')
    if len(matches) != 1:
        raise ValueError('Unique original response association required')
    response_raw = _read(evidence / matches[0], runtime)
    response_hash = hashlib.sha256(response_raw).hexdigest()
    if entry['evidence_sha256'].get(matches[0]) != response_hash:
        raise ValueError('Original response evidence changed')
    response = _json(response_raw, billing=True)
    if (not isinstance(receipt, dict) or receipt.get('cancelled') is not False
            or receipt.get('is_byok') is not False
            or response.get('provider') != 'DeepInfra'
            or response.get('usage', {}).get('is_byok') is not False
            or response.get('id') != generation):
        raise ValueError('Exact uncancelled non-BYOK response and receipt required')
    actual = dollars(reconcile_receipt(response, receipt))
    if actual != charge or actual > maximum or (estimate is not None and actual > estimate):
        raise ValueError('Receipt differs from bounded original charge')
    for key in ('prompt', 'completion'):
        native = receipt.get('native_tokens_' + key)
        original = response['usage'].get(key + '_tokens')
        if type(native) is not int or native < 0 or type(original) is not int or native != original:
            raise ValueError('Provider-native token counts differ from original usage')
    # Preserve exact cost while retaining only documented billing metadata.
    selected = {key: receipt[key] for key in RECEIPT_FIELDS}
    selected['total_cost'] = str(Decimal(str(selected['total_cost'])))
    return {'schema_version': 1, 'kind': entry['kind'], 'trial_id': trial,
            'request_id': request_id, 'generation_id': generation,
            'deferral_sha256': entry['sidecar_sha256'],
            'original_response_sha256': response_hash,
            'original_ledger_row': row, 'receipt': selected,
            'matched_charge_nanodollars': actual,
            'potential_hold_reduction_nanodollars': maximum - charge,
            'status': 'receipt_matched_not_applied', 'generation_calls': 0,
            'original_evidence_changed': False, 'reservation_released': False,
            'continuation_authorised': False}


def collect(runtime, *, kind='scored', reader, maximum_receipts=64):
    """One GET per missing receipt at most; no automatic retries or settlement."""
    if kind not in {'setup', 'scored'} or not callable(reader):
        raise ValueError('Explicit ledger kind and read-only receipt reader required')
    if type(maximum_receipts) is not int or not 1 <= maximum_receipts <= 64:
        raise ValueError('Receipt collection must be bounded to 1..64 requests')
    runtime = Path(runtime).absolute()
    _private_directory(runtime)
    summary = {'generation_calls': 0, 'receipt_gets': 0, 'staged': 0,
               'already_staged': 0, 'unavailable': 0,
               'potential_hold_reduction_nanodollars': 0,
               'reservation_released': False, 'continuation_authorised': False}
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            fd = os.open(runtime / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('Private owned execution lock required')
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        database = runtime / (kind + '_budget.sqlite')
        _read(database, runtime)
        db = stack.enter_context(closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)))
        db.execute('BEGIN')
        entries = validate_deferrals(runtime, db, kind=kind)
        folder = runtime / DIRECTORY
        if not folder.exists() and not folder.is_symlink():
            folder.mkdir(mode=0o700)
        _private_directory(folder)
        candidates = [(entry, identifier) for entry in entries
                      for identifier in entry['unverified_receipt_request_ids']]
        summary['eligible'] = len(candidates)
        summary['unexamined'] = 0
        for entry, identifier in candidates:
            if not isinstance(identifier, str) or not re.fullmatch(r'[A-Za-z0-9-]{1,100}', identifier):
                raise ValueError('Safe original request identifier required')
            path = folder / (kind + '--' + identifier + '.json')
            if path.exists() or path.is_symlink():
                stored = _json(_read(path, runtime))
                expected = _document(runtime, entry, identifier, stored['receipt'])
                if _encoded(stored) != _encoded(expected):
                    raise ValueError('Staged receipt or original binding changed')
                summary['already_staged'] += 1
            else:
                if summary['receipt_gets'] >= maximum_receipts:
                    summary['unexamined'] += 1
                    continue
                summary['receipt_gets'] += 1
                try:
                    receipt = reader(next(row[5] for row in entry['ledger_rows'] if row[0] == identifier))
                except TransportError:
                    summary['unavailable'] += 1
                    continue
                expected = _document(runtime, entry, identifier, receipt)
                _write(path, expected)
                summary['staged'] += 1
            summary['potential_hold_reduction_nanodollars'] += expected['potential_hold_reduction_nanodollars']
        # Recheck all immutable bindings after collection inside the same read transaction.
        if validate_deferrals(runtime, db, kind=kind) != entries:
            raise ValueError('Original deferrals changed during receipt collection')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--credential-file', type=Path, required=True)
    parser.add_argument('--kind', choices=('setup', 'scored'), default='scored')
    parser.add_argument('--maximum-receipts', type=int, default=64)
    args = parser.parse_args()
    client = OpenRouter(load_key(args.credential_file))  # generation disabled
    print(json.dumps(collect(args.runtime, kind=args.kind, reader=client.generation,
                             maximum_receipts=args.maximum_receipts), sort_keys=True))

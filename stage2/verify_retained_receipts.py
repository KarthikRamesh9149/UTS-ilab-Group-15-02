"""Verify named, already-settled receipts offline, without admitting new work.

Unlike whole-trial collection this maintenance operation can record known
receipts in a trial which also contains an unknown dispatch. It cannot settle
that dispatch, change a charge, release a reservation or approve continuation.
"""
import argparse
from contextlib import ExitStack, closing
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from budget_ledger import dollars
from gateway_core import reconcile_receipt
from model_protocol import read_protocol
from scored_accounting import read_json
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS


def _private(path, *, directory=False):
    info = path.lstat()
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Existing private owned regular evidence required')


def verify_retained_receipts(runtime, *, trial_id, request_ids):
    """All-or-nothing verification of explicit settled requests; zero API calls."""
    if not isinstance(trial_id, str) or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
        raise ValueError('Explicit trial identity required')
    if (not isinstance(request_ids, (tuple, list)) or not request_ids
            or any(not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,100}', value)
                   for value in request_ids) or len(set(request_ids)) != len(request_ids)):
        raise ValueError('Unique explicit request identities required')
    runtime = Path(runtime)
    _private(runtime, directory=True)
    runtime = runtime.resolve()
    database = runtime / 'scored_budget.sqlite'
    attempts = runtime / 'scored-attempts'
    evidence = attempts / trial_id
    for path in (attempts, evidence):
        _private(path, directory=True)
    _private(database)
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            fd = os.open(runtime / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
                raise ValueError('Private owned runner lock required')
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        settings = read_protocol(runtime)
        started = read_json(evidence / 'started.json')
        if (started.get('trial_id') != trial_id or started.get('stage') != 'development'
                or started.get('model_protocol_sha256') != settings.fingerprint()):
            raise ValueError('Original development trial and protocol required')
        responses = {}
        for path in evidence.glob('*.response.json'):
            _private(path)
            response = read_json(path)
            identifier = response.get('id')
            if not isinstance(identifier, str) or not identifier or identifier in responses:
                raise ValueError('Durable response identities must be unique')
            responses[identifier] = (path, response)
        db = stack.enter_context(closing(sqlite3.connect(database.as_uri() + '?mode=rw', uri=True)))
        db.execute('PRAGMA synchronous=FULL')
        with db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                raise ValueError('Original ledger integrity failure')
            if (db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone()
                    != (dollars(SCORED_CEILING), dollars(TRIAL_CAP))
                    or dict(db.execute('SELECT name,cap FROM stages'))
                    != {name: dollars(cap) for name, cap in STAGE_CAPS.items()}
                    or db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone() != (1,)
                    or db.execute('SELECT stage FROM trial_stages WHERE trial=?', (trial_id,)).fetchone()
                    != ('development',)):
                raise ValueError('Original accounting policy required')
            if db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
                raise ValueError('Billing incident requires separate investigation')
            verified = []
            for request_id in request_ids:
                row = db.execute('''SELECT r.trial,r.state,r.charged,g.generation_id,c.state
                    FROM requests r LEFT JOIN generations g ON g.request_id=r.id
                    LEFT JOIN receipt_checks c ON c.request_id=r.id WHERE r.id=?''', (request_id,)).fetchone()
                if (row is None or row[0] != trial_id or row[1] != 'settled'
                        or type(row[2]) is not int or row[2] < 0 or row[4] not in {'pending', 'verified'}):
                    raise ValueError('Only existing settled receipt-check rows may be verified')
                if row[3] not in responses:
                    raise ValueError('Exact retained generation response required')
                response_path, response = responses[row[3]]
                receipt_path = response_path.with_name(response_path.name.replace('.response.json', '.receipt.json'))
                _private(receipt_path)
                receipt = read_json(receipt_path)
                if response.get('provider') != 'DeepInfra' or response.get('usage', {}).get('is_byok') is not False:
                    raise ValueError('Original response provider identity required')
                if receipt.get('is_byok') is not False or receipt.get('cancelled') is not False:
                    raise ValueError('Uncancelled non-BYOK receipt required')
                # OpenRouter's normalised token fields can legitimately differ.
                # The provider-native receipt counts must match response usage.
                for key in ('prompt', 'completion'):
                    usage = response['usage'].get(key + '_tokens')
                    native = receipt.get('native_tokens_' + key)
                    if type(usage) is not int or usage < 0 or type(native) is not int or native != usage:
                        raise ValueError('Provider-native receipt token counts differ')
                if dollars(reconcile_receipt(response, receipt)) != row[2]:
                    raise ValueError('Receipt differs from settled charge')
                verified.append({'request_id': request_id, 'generation_id': row[3],
                    'charged_nanodollars': row[2], 'previous_receipt_state': row[4],
                    'response_sha256': hashlib.sha256(response_path.read_bytes()).hexdigest(),
                    'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()})
            # No mutation occurs until EVERY selected row and receipt has passed.
            db.executemany("UPDATE receipt_checks SET state='verified' WHERE request_id=?",
                           [(item['request_id'],) for item in verified])
        return {'status': 'named_settled_receipts_verified_only', 'trial_id': trial_id,
                'receipts': verified, 'generation_calls': 0, 'network_calls': 0,
                'charges_changed': False, 'reservations_released': False,
                'continuation_authorised': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--trial', required=True)
    parser.add_argument('--request', action='append', required=True)
    args = parser.parse_args()
    print(json.dumps(verify_retained_receipts(args.runtime, trial_id=args.trial,
                                            request_ids=args.request), sort_keys=True))

"""Settle a known pending receipt; never replay generation or change scores."""
import argparse
from contextlib import ExitStack
import fcntl
import hashlib
from pathlib import Path
import os
import re

from budget_ledger import Ledger
from gateway_core import reconcile_receipt
from openrouter_transport import OpenRouter, load_key
from receipt_polling import read_receipt
from scored_accounting import read_json
from scored_gateway import durable_json, private_directory
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS


def reconcile(root, *, kind, trial_id, client):
    if kind not in {'setup', 'scored'} or not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,119}', trial_id):
        raise ValueError('Explicit existing ledger and trial required')
    runtime = private_directory(Path(root) / '.runtime/stage2')
    database = runtime / (kind + '_budget.sqlite')
    if database.is_symlink() or not database.is_file():
        raise ValueError('Original ledger required; never create a substitute')
    attempts = runtime / ('native-setup-attempts' if kind == 'setup' else 'scored-attempts') / trial_id
    if attempts.is_symlink() or not attempts.is_dir():
        raise ValueError('Original attempt evidence required')
    with ExitStack() as stack:
        for name in ('matrix.lock', 'scored.lock', 'gateway.lock'):
            fd = os.open(runtime / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            handle = stack.enter_context(os.fdopen(fd, 'r+'))
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ledger = (Ledger(database, '1', '1', {'setup': '1'}) if kind == 'setup' else
                  Ledger(database, SCORED_CEILING, TRIAL_CAP, STAGE_CAPS, allow_estimated_trials=True))
        stack.callback(ledger.close)
        pending = [row for row in ledger.pending() if row[1] == trial_id]
        if len(pending) != 1 or not pending[0][3]:
            raise ValueError('Exactly one pending request with known generation identity required')
        request_id, _, _, generation_id = pending[0]
        matches = [(p, read_json(p)) for p in attempts.glob('*.response.json')]
        matches = [(p, value) for p, value in matches if value.get('id') == generation_id]
        if len(matches) != 1:
            raise ValueError('Exactly one durable matching response required')
        response_path, response = matches[0]
        receipt_path = response_path.with_name(response_path.name.replace('.response.json', '.receipt.json'))
        receipt = read_json(receipt_path) if receipt_path.exists() else read_receipt(client.generation, generation_id)
        charged = reconcile_receipt(response, receipt)
        # Preserve the fetched evidence before settling the durable reservation.
        if not receipt_path.exists():
            durable_json(receipt_path, receipt)
        ledger.settle(request_id, charged)
        report = {'status': 'reconciled_without_generation_replay', 'kind': kind,
                  'trial_id': trial_id, 'charged_usd': str(charged),
                  'generation_id': generation_id, 'score_unchanged': True,
                  'receipt_sha256': hashlib.sha256(receipt_path.read_bytes()).hexdigest()}
        marker = attempts / 'manual-reconciliation.json'
        if not marker.exists():
            durable_json(marker, report)
        return report


if __name__ == '__main__':
    import json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=('setup', 'scored'), required=True)
    parser.add_argument('--trial', required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    print(json.dumps(reconcile(root, kind=args.kind, trial_id=args.trial,
                              client=OpenRouter(load_key(root / '.env')))))

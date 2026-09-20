"""Cross-check settled response charges after revocation, outside agent time.

No generation calls, score changes, allowance changes or automatic replay.
An unavailable receipt blocks admission to the next trial. Conflicting billing
persists an incident, so restarting a runner cannot ignore the discrepancy.
"""
from decimal import Decimal
from pathlib import Path
import time

from budget_ledger import Ledger, dollars
from gateway_core import reconcile_receipt
from openrouter_transport import OpenRouter, TransportError, load_key
from scored_accounting import read_json
from scored_gateway import durable_json
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS


def collect_receipts(runtime, trial_id, *, kind='scored', client=None,
                     deadline_seconds=180, clock=time.monotonic, sleep=time.sleep):
    if kind not in {'setup', 'scored'} or not 0 < deadline_seconds <= 300:
        raise ValueError('Bounded registered receipt collection required')
    runtime = Path(runtime)
    database = runtime / (kind + '_budget.sqlite')
    if database.is_symlink() or not database.is_file():
        raise ValueError('Original ledger required')
    evidence = runtime / ('native-setup-attempts' if kind == 'setup' else 'scored-attempts') / trial_id
    ledger = (Ledger(database, '1', '1', {'setup': '1'}) if kind == 'setup' else
              Ledger(database, SCORED_CEILING, TRIAL_CAP, STAGE_CAPS, allow_estimated_trials=True,
                     historical_hold_runtime=runtime))
    try:
        if ledger.blocking_pending(trial=trial_id):
            raise ValueError('Unknown dispatch outcome requires explicit reconciliation')
        rows = ledger.db.execute('''SELECT r.id,g.generation_id,r.charged FROM requests r
            LEFT JOIN generations g ON r.id=g.request_id WHERE r.trial=?''', (trial_id,)).fetchall()
        if any(not generation or charge is None for _, generation, charge in rows):
            raise ValueError('Every trial request requires settled cost and generation identity')
        requests = dict((generation, (request, cost)) for request, generation, cost in rows)
        paths = list(evidence.glob('*.response.json'))
        responses = {read_json(path)['id']: path for path in paths}
        if len(paths) != len(responses) or len(responses) != len(rows) or set(responses) != set(requests):
            raise ValueError('Response identities differ from settled ledger')
        deadline = clock() + deadline_seconds
        remaining = dict(responses)
        while remaining:
            for identifier, response_path in list(remaining.items()):
                receipt_path = response_path.with_name(response_path.name.replace('.response.json', '.receipt.json'))
                response = read_json(response_path)
                if receipt_path.exists():
                    receipt = read_json(receipt_path)
                else:
                    if clock() >= deadline:
                        raise TransportError('Post-trial receipts unavailable; next trial blocked')
                    if client is None:
                        client = OpenRouter(load_key(Path(__file__).resolve().parents[1] / '.env'))
                    try:
                        receipt = client.generation(identifier)
                    except TransportError:
                        continue
                    durable_json(receipt_path, receipt)
                request_id, charge = requests[identifier]
                try:
                    if dollars(reconcile_receipt(response, receipt)) != charge:
                        raise ValueError('Receipt differs from settled charge')
                except (ValueError, KeyError, TypeError):
                    # The raw response and conflicting receipt remain retained.
                    try:
                        actual = receipt['total_cost']
                        dollars(actual)
                    except (KeyError, ValueError, TypeError, ArithmeticError):
                        actual = Decimal(charge) / 1_000_000_000
                    ledger.record_receipt_incident(request_id, actual)
                    raise ValueError('Post-trial billing mismatch; ledger halted') from None
                ledger.verify_receipt(request_id, receipt['total_cost'])
                remaining.pop(identifier)
            if not remaining:
                break
            if clock() >= deadline:
                raise TransportError('Post-trial receipts unavailable; next trial blocked')
            sleep(min(5, deadline - clock()))
        return {'receipts_verified': len(rows), 'generation_calls': 0}
    finally:
        ledger.close()

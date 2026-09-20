"""Cross-check settled response charges after revocation, outside agent time.

No generation calls, score changes, allowance changes or automatic replay.
An unavailable receipt blocks admission to the next trial. Conflicting billing
persists an incident, so restarting a runner cannot ignore the discrepancy.
"""
from decimal import Decimal
from pathlib import Path
import time

from budget_ledger import Ledger, BudgetExceeded, dollars
from gateway_core import reconcile_receipt
from openrouter_transport import OpenRouter, TransportError, load_key
from scored_accounting import read_json
from scored_gateway import durable_json
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS
from deferred_billing import validate_deferrals


def collect_receipts(runtime, trial_id, *, kind='scored', client=None,
                     deadline_seconds=180, clock=time.monotonic, sleep=time.sleep):
    if kind not in {'setup', 'scored'} or not 0 < deadline_seconds <= 300:
        raise ValueError('Bounded registered receipt collection required')
    runtime = Path(runtime)
    database = runtime / (kind + '_budget.sqlite')
    if database.is_symlink() or not database.is_file():
        raise ValueError('Original ledger required')
    evidence = runtime / ('native-setup-attempts' if kind == 'setup' else 'scored-attempts') / trial_id
    ledger = (Ledger(database, '1', '1', {'setup': '1'}, deferred_billing_runtime=runtime,
                     deferred_billing_kind='setup') if kind == 'setup' else
              Ledger(database, SCORED_CEILING, TRIAL_CAP, STAGE_CAPS, allow_estimated_trials=True,
                     historical_hold_runtime=runtime, deferred_billing_runtime=runtime))
    try:
        if kind == 'scored':
            from historical_hold import TRIAL_ID, SECOND_TRIAL_ID, SIDECAR, SIDECAR_V2
            if trial_id in {TRIAL_ID, SECOND_TRIAL_ID} and any((runtime / name).exists() for name in (SIDECAR, SIDECAR_V2)):
                raise BudgetExceeded('Original historical held trial is immutable and cannot be collected again')
        entries = ledger.deferred_entries()
        if any(entry['trial_id'] == trial_id for entry in entries):
            return {'receipts_verified': None, 'billing_deferred': True, 'generation_calls': 0}
        if ledger.db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
            raise ValueError('Actual billing incident requires review')
        all_rows = ledger.db.execute('''SELECT r.id,g.generation_id,r.charged,r.state FROM requests r
            LEFT JOIN generations g ON r.id=g.request_id WHERE r.trial=?''', (trial_id,)).fetchall()
        rows = [(request, generation, charge) for request, generation, charge, state in all_rows if state == 'settled']
        unknown = [(request, generation) for request, generation, charge, state in all_rows if state != 'settled' or charge is None]
        if any(not generation or charge is None for _, generation, charge in rows):
            raise ValueError('Every trial request requires settled cost and generation identity')
        requests = dict((generation, (request, cost)) for request, generation, cost in rows)
        paths = list(evidence.glob('*.response.json'))
        responses = {read_json(path)['id']: path for path in paths}
        if (len(paths) != len(responses) or not set(requests) <= set(responses)
                or not set(responses) <= set(requests) | {generation for _, generation in unknown if generation}):
            raise ValueError('Response identities differ from settled ledger')
        deadline = clock() + deadline_seconds
        remaining = {identifier: responses[identifier] for identifier in requests}
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
        if unknown:
            raise ValueError('Unknown dispatch outcome retains reservation after settled receipts were checked')
        return {'receipts_verified': len(rows), 'generation_calls': 0}
    finally:
        ledger.close()

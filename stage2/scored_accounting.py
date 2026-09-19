"""Read-only post-teardown reconciliation. Never releases or retries a request."""
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from budget_ledger import UNIT, dollars
from gateway_core import reconcile_receipt
from gateway_policy import MODEL, ENDPOINT
from model_protocol import read_protocol
from study_budget import SCORED_CEILING, TRIAL_CAP, STAGE_CAPS


def read_json(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing or unsafe billing artifact')
    return json.loads(path.read_text(), parse_float=Decimal)


def audit_trial(runtime, trial_id, stage):
    runtime = Path(runtime)
    database = runtime / 'scored_budget.sqlite'
    if not database.is_file() or database.is_symlink():
        raise ValueError('Canonical scored ledger missing')
    settings = read_protocol(runtime)
    # mode=ro prevents accidental creation of an empty substitute ledger.
    db = sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('BEGIN')
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Ledger integrity failure')
        if db.execute("SELECT COUNT(*) FROM receipt_checks WHERE state='pending'").fetchone()[0]:
            raise ValueError('Post-trial receipt cross-check incomplete')
        if db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone() != (dollars(SCORED_CEILING), dollars(TRIAL_CAP)):
            raise ValueError('Scored budget policy drift')
        caps = dict(db.execute('SELECT name,cap FROM stages'))
        if caps != {name: dollars(cap) for name, cap in STAGE_CAPS.items()}:
            raise ValueError('Stage allocation drift')
        if stage not in caps:
            raise ValueError('Unknown stage')
        if db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone() != (1,):
            raise ValueError('Estimated admission policy drift')
        if db.execute("SELECT COUNT(*) FROM requests WHERE state!='settled' OR charged IS NULL").fetchone()[0]:
            raise ValueError('Unresolved request; retain reservation and halt')
        if db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
            raise ValueError('Billing incident; halt')
        total = db.execute('SELECT COALESCE(SUM(charged),0) FROM requests').fetchone()[0]
        if total > dollars(SCORED_CEILING):
            raise ValueError('Aggregate ceiling exceeded')
        for name, cap in caps.items():
            amount = db.execute('''SELECT COALESCE(SUM(r.charged),0) FROM requests r
                JOIN trial_stages s ON s.trial=r.trial WHERE s.stage=?''', (name,)).fetchone()[0]
            if amount > cap:
                raise ValueError('Stage ceiling exceeded')
        rows = db.execute('''SELECT r.id,r.charged,g.generation_id FROM requests r
            LEFT JOIN generations g ON g.request_id=r.id WHERE r.trial=?''', (trial_id,)).fetchall()
        if rows and db.execute('SELECT stage FROM trial_stages WHERE trial=?', (trial_id,)).fetchone() != (stage,):
            raise ValueError('Trial stage mismatch')
        if any(not row[2] for row in rows):
            raise ValueError('Settled request lacks generation identity')
        by_generation = {row[2]: row[1] for row in rows}
        if len(by_generation) != len(rows):
            raise ValueError('Duplicate trial generation')
        evidence = runtime / 'scored-attempts' / trial_id
        started = read_json(evidence / 'started.json')
        if started.get('trial_id') != trial_id or started.get('stage') != stage:
            raise ValueError('Gateway attempt identity mismatch')
        if started.get('model_protocol_sha256') != settings.fingerprint():
            raise ValueError('Gateway model protocol identity mismatch')
        stops = list(evidence.glob('*.budget-stop.json'))
        for path in stops:
            stop = read_json(path)
            if stop.get('trial_id') != trial_id or stop.get('stage') != stage or stop.get('kind') != 'budget_stop':
                raise ValueError('Invalid budget stop evidence')
        requests = sorted(evidence.glob('*.request.json'))
        responses = sorted(evidence.glob('*.response.json'))
        receipts = sorted(evidence.glob('*.receipt.json'))
        if not len(requests) == len(responses) == len(receipts) == len(rows):
            raise ValueError('Request, response, receipt and ledger counts differ')
        seen = set()
        usage = {'prompt_tokens': [], 'completion_tokens': []}
        for request_path in requests:
            prefix = request_path.name.removesuffix('.request.json')
            request = read_json(request_path)
            # JSON decimals are preserved for money, but sampling values must
            # be numeric floats for the same wire-contract validator.
            sampled = dict(request)
            for key in ['temperature', 'top_p']:
                if isinstance(sampled.get(key), Decimal): sampled[key] = float(sampled[key])
            settings.enforce(sampled)
            response = read_json(evidence / (prefix + '.response.json'))
            receipt = read_json(evidence / (prefix + '.receipt.json'))
            cost = dollars(reconcile_receipt(response, receipt))
            generation = response['id']
            if generation in seen or by_generation.get(generation) != cost:
                raise ValueError('Artifact charge does not match unique ledger generation')
            provider = request.get('provider', {})
            if request.get('model') != MODEL or provider.get('only') != [ENDPOINT] or provider.get('allow_fallbacks') is not False:
                raise ValueError('Artifact routing drift')
            seen.add(generation)
            for key in usage:
                value = response.get('usage', {}).get(key)
                usage[key].append(value if type(value) is int and value >= 0 else None)
        charged = sum(by_generation.values())
        if charged > dollars(TRIAL_CAP):
            raise ValueError('Trial charge exceeded approved estimated admission cap')
        return {'billing_verified': True, 'requests': len(rows),
                'budget_stop_count': len(stops),
                'model_protocol_sha256': settings.fingerprint(),
                'charged_usd': str(Decimal(charged) / UNIT),
                'aggregate_charged_usd': str(Decimal(total) / UNIT),
                **{key: None if any(v is None for v in values) else sum(values)
                   for key, values in usage.items()}}
    finally:
        db.close()

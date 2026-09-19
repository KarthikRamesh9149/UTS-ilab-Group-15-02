"""Read-only reconciliation of native compatibility calls, not scored trials."""
from decimal import Decimal
from pathlib import Path
import sqlite3

from budget_ledger import dollars, UNIT
from gateway_core import reconcile_receipt
from gateway_policy import MODEL, ENDPOINT
from scored_accounting import read_json


def audit_setup(runtime, trial_id, settings):
    runtime = Path(runtime)
    path = runtime / 'setup_budget.sqlite'
    if not path.is_file() or path.is_symlink():
        raise ValueError('Existing setup ledger required')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('BEGIN')
        if db.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Ledger integrity failure')
        if db.execute("SELECT COUNT(*) FROM receipt_checks WHERE state='pending'").fetchone()[0]:
            raise ValueError('Post-trial receipt cross-check incomplete')
        if db.execute('SELECT ceiling,trial_cap FROM policy WHERE id=1').fetchone() != (dollars('1'), dollars('1')):
            raise ValueError('Setup allowance changed')
        if dict(db.execute('SELECT name,cap FROM stages')) != {'setup': dollars('1')}:
            raise ValueError('Setup stage changed')
        if db.execute('SELECT enabled FROM estimation_policy WHERE id=1').fetchone() != (0,):
            raise ValueError('Setup requires hard reservations')
        if db.execute("SELECT COUNT(*) FROM requests WHERE state!='settled' OR charged IS NULL").fetchone()[0] or db.execute('SELECT COUNT(*) FROM incidents').fetchone()[0]:
            raise ValueError('Unresolved billing; retain reservations')
        total = db.execute('SELECT COALESCE(SUM(charged),0) FROM requests').fetchone()[0]
        if not 0 <= total <= dollars('1'):
            raise ValueError('Setup ceiling exceeded')
        rows = db.execute('''SELECT g.generation_id,r.charged FROM requests r
            LEFT JOIN generations g ON g.request_id=r.id WHERE r.trial=?''', (trial_id,)).fetchall()
        charges = dict(rows)
        if len(charges) != len(rows) or None in charges:
            raise ValueError('Missing or duplicate generation identity')
        if rows and db.execute('SELECT stage FROM trial_stages WHERE trial=?', (trial_id,)).fetchone() != ('setup',):
            raise ValueError('Wrong billing stage')
        evidence = runtime / 'native-setup-attempts' / trial_id
        started = read_json(evidence / 'started.json')
        if started.get('trial_id') != trial_id or started.get('stage') != 'setup' or started.get('model_protocol_sha256') != settings.fingerprint():
            raise ValueError('Setup identity mismatch')
        requests = sorted(evidence.glob('*.request.json'))
        if not len(requests) == len(list(evidence.glob('*.response.json'))) == len(list(evidence.glob('*.receipt.json'))) == len(rows):
            raise ValueError('Artifact and ledger counts differ')
        seen = set()
        usage = {'prompt_tokens': 0, 'completion_tokens': 0}
        for request_path in requests:
            prefix = request_path.name.removesuffix('.request.json')
            request = read_json(request_path)
            for key in ('temperature', 'top_p'):
                if isinstance(request.get(key), Decimal): request[key] = float(request[key])
            settings.enforce(request)
            provider = request.get('provider', {})
            if request.get('model') != MODEL or provider.get('only') != [ENDPOINT] or provider.get('allow_fallbacks') is not False:
                raise ValueError('Provider routing changed')
            response = read_json(evidence / (prefix + '.response.json'))
            receipt = read_json(evidence / (prefix + '.receipt.json'))
            amount = dollars(reconcile_receipt(response, receipt))
            identifier = response['id']
            if identifier in seen or charges.get(identifier) != amount:
                raise ValueError('Receipt does not match ledger')
            seen.add(identifier)
            for key in usage:
                value = response.get('usage', {}).get(key)
                if type(value) is not int or value < 0:
                    raise ValueError('Usage evidence missing')
                usage[key] += value
        return {'billing_verified': True, 'requests': len(rows),
                'model_protocol_sha256': settings.fingerprint(),
                'charged_usd': str(Decimal(sum(charges.values())) / UNIT),
                'aggregate_setup_charged_usd': str(Decimal(total) / UNIT), **usage}
    finally:
        db.close()
